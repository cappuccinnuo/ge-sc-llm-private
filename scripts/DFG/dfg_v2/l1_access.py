"""L1 scalar-compatible extraction with conservative aggregate weak writes.

Aggregate arguments to ordinary calls remain reads only (no interprocedural
memory/storage summaries). A member/index write changes a coarse base symbol;
it does not model field-sensitive aliases or storage locations.
"""
from ..access_extractor import AccessExtractor
from ..frontend import span
from ..models import Unsupported
from .l1_models import V2Event
from .access_shape import prefix_access_shape


class ExtendedAccessExtractor(AccessExtractor):
    def _aggregate(self, symbol):
        return bool(symbol and self.table.aggregate_info[symbol].get("aggregate"))

    def _chain_root(self, node):
        while node is not None:
            if node.type in ("member_expression", "array_access"):
                field = "object" if node.type == "member_expression" else "base"
                node = node.child_by_field_name(field)
            elif node.type == "parenthesized_expression":
                children = [child for child in node.named_children if "comment" not in child.type]
                if len(children) != 1:
                    raise Unsupported("V2: ambiguous parenthesized access base")
                node = children[0]
            else:
                break
        return node if node is not None and node.type == "identifier" else None

    def _mutator_base(self, node):
        if node is None or node.type != "call_expression":
            return None
        function = node.child_by_field_name("function")
        if function is None or function.type != "member_expression":
            return None
        prop = function.child_by_field_name("property")
        if prop is None or self._name(prop) not in ("push", "pop"):
            return None
        return function.child_by_field_name("object")

    def reads(self, node):
        # Treat a nested local aggregate mutator as a nested write. Ordinary
        # calls (including aggregate arguments) retain the inherited read rule.
        base = self._mutator_base(node)
        root = self._chain_root(base)
        if root is not None:
            symbol = self.table.resolve(self._name(root), root)
            if symbol is not None and self._aggregate(symbol.id):
                raise Unsupported("V2: nested aggregate mutation / unspecified operand order")
        if node is not None and node.type == "new_expression":
            # P6b approved AST adaptation: the new-expression name is a type,
            # not a value read. Outer call/options nodes read their arguments.
            declared_type = node.child_by_field_name("name")
            if declared_type is None or declared_type.type != "type_name":
                raise Unsupported("V2: unknown new-expression type shape")
            # P6d defensive grammar branch: some supported parser versions
            # allow arguments directly under new_expression. Never traverse
            # the type_name as a value; inherited reads retain nested-write
            # and unknown-expression rejection for each direct argument.
            result = []
            for child in node.named_children:
                if child.type == "call_argument":
                    result += self.reads(child)
            return result
        if node is not None and node.type == "struct_expression":
            # P6b: call options are encoded as a struct-shaped wrapper.
            # Read the callee/base and option values, never the option names.
            # Recursive reads preserve inherited unknown/nested-write fallback.
            result = self.reads(node.child_by_field_name("type"))
            for child in node.named_children:
                if child.type == "struct_field_assignment":
                    result += self.reads(child.child_by_field_name("value"))
            return result
        return super().reads(node)

    def targets(self, node):
        if node.type == "identifier":
            symbol = self._resolve(node)
            return [], [symbol] if symbol else [], []
        if node.type in ("member_expression", "array_access"):
            root = self._chain_root(node)
            symbol = self._resolve(root) if root is not None else None
            # reads traverses every member/base/index and rejects nested writes.
            return self.reads(node), [], [symbol] if self._aggregate(symbol) else []
        if node.type == "tuple_expression":
            reads, writes, weak = [], [], []
            for child in node.named_children:
                if "comment" in child.type:
                    continue
                r, w, ww = self.targets(child)
                reads.extend(r)
                writes.extend(w)
                weak.extend(ww)
            all_targets = writes + weak
            if len(all_targets) != len(set(all_targets)):
                raise Unsupported("Repeated tuple assignment target")
            return reads, writes, weak
        raise Unsupported("Unsupported assignment target: " + node.type)

    def event(self, anchor, reads=(), writes=(), kind="expression", weak_writes=()):
        strong, weak = set(writes), set(weak_writes)
        if strong & weak:
            raise Unsupported("V2: overlapping strong and weak write target")
        result = V2Event(
            id=self.table.function_id + ":e" + str(self.counter),
            function=self.table.function_id,
            anchor=anchor,
            reads=tuple(sorted(set(reads))),
            writes=tuple(sorted(strong)),
            weak_writes=tuple(sorted(weak)),
            kind=kind,
        )
        self.counter += 1
        return result

    def _prefix_access_event(self, node, owner):
        """Adapt only a top-level prefix + access-chain parser precedence shape.

        Installed grammar parses delete a[i] as array_access(unary(delete,a),i).
        Follow AST base/object fields, never text replacement or line proximity.
        Nested operators in indices/arguments still pass through reads() and fail.
        """
        shape = prefix_access_shape(node)
        if shape is None:
            return None
        spelling, argument, indices = shape
        root = self._chain_root(argument)
        symbol = self._resolve(root) if root is not None else None
        reads = self.reads(argument)
        for index in indices:
            reads += self.reads(index)
        weak = [symbol] if self._aggregate(symbol) else []
        self.diagnostics.append({
            "kind": "v2_prefix_access_chain",
            "operator": spelling, "byte": node.start_byte,
            "parser_shape": argument.parent.type, "anchor_preserved": True,
        })
        return self.event(owner, reads, kind="delete" if spelling == "delete" else "update",
                          weak_writes=weak)

    def extract(self, node, anchor=None):
        if node is None:
            return []
        owner = anchor or span(self.table.file, node)
        kind = node.type
        if kind in ("member_expression", "array_access"):
            prefix_event = self._prefix_access_event(node, owner)
            if prefix_event is not None:
                return [prefix_event]
        if kind in ("assignment_expression", "augmented_assignment_expression"):
            left = node.child_by_field_name("left")
            reads, writes, weak = self.targets(left)
            if kind == "augmented_assignment_expression":
                reads += self.reads(left)
            reads += self.reads(node.child_by_field_name("right"))
            return [self.event(owner, reads, writes, "assignment", weak)]
        if kind == "update_expression":
            argument = node.child_by_field_name("argument")
            reads, writes, weak = self.targets(argument)
            return [self.event(owner, reads + self.reads(argument), writes, "update", weak)]
        if kind == "unary_expression":
            operator = node.child_by_field_name("operator")
            if operator is not None and self._name(operator) == "delete":
                reads, writes, weak = self.targets(node.child_by_field_name("argument"))
                return [self.event(owner, reads, writes, "delete", weak)]
        base = self._mutator_base(node)
        if base is not None:
            root = self._chain_root(base)
            symbol = self._resolve(root) if root is not None else None
            reads = self.reads(base)
            for child in node.named_children:
                if child.type in ("call_argument", "call_struct_argument"):
                    reads += self.reads(child)
            weak = [symbol] if self._aggregate(symbol) else []
            return [self.event(owner, reads, kind="expression", weak_writes=weak)]
        # Declaration/return/emit/entry and expression-statement dispatch are
        # inherited, with this event factory returning immutable V2Event.
        return super().extract(node, anchor)
