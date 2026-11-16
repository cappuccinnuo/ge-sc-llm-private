"""Binding of statement accesses to contract state variables, shared by L2 and L3."""
from dataclasses import dataclass

from dfg.analysis.access import prefix_access_shape
from dfg.analysis.frontend import effective_interval, mode_for, span, text, walk
from dfg.analysis.ir import Unsupported
from dfg.analysis.state import ClosedScopeJ
from dfg.analysis.symbols import CONTAINERS, key


# ----------------------------------------------------------------------
# dfg_v2/state_binding
# L2 declaration binding and flow-insensitive storage aliases.
#
# This is deliberately independent of L1 lexical SymbolTable/CFG support. A
# callable-wide local declaration masks the same state name even before the
# declaration. State identity is the AST declaration, never the spelling alone.
# No labels, node features, compiler invocation or callee summaries are used.
CALLABLE_TYPES = frozenset(("function_definition", "constructor_definition",
                           "fallback_receive_definition", "modifier_definition"))

def unwrap(node):
    while node is not None and node.type == "parenthesized_expression":
        children = [x for x in node.named_children if "comment" not in x.type]
        if len(children) != 1:
            return None
        node = children[0]
    return node

def chain_root(node):
    node = unwrap(node)
    while node is not None and node.type in ("member_expression", "array_access"):
        field = "object" if node.type == "member_expression" else "base"
        node = unwrap(node.child_by_field_name(field))
    return node if node is not None and node.type == "identifier" else None

@dataclass(frozen=True)
class StateBinding:
    declarations: tuple = ()
    via_alias: bool = False
    classification: str = "unresolved"
    reason: str = ""

class StateBinder:
    def __init__(self, view, callable_node, metadata=None, include_constants=False):
        self.view, self.context = view, callable_node
        self.include_constants = include_constants
        self.callable_id = "{}:{}".format(view.file, callable_node.start_byte)
        self.diagnostics = []
        self.locals, self.local_declarations = set(), {}
        self.aliases, self.alias_bindings = {}, []
        self.alias_types = {}
        self.contract = callable_node.parent
        while self.contract is not None and self.contract.type not in CONTAINERS:
            self.contract = self.contract.parent
        self.closed_scope, self.scope_fallback = None, None
        try:
            self.closed_scope = ClosedScopeJ(view, callable_node)
            self.members = self.closed_scope.members
        except Unsupported as exc:
            self.scope_fallback = str(exc)
            self.members = {}
            body = self.contract.child_by_field_name("body") if self.contract else None
            if body is not None:
                for node in body.named_children:
                    name = node.child_by_field_name("name")
                    if name is not None:
                        self.members.setdefault(text(view.source, name), []).append(node)
            self.diagnostics.append(self._diagnostic(
                callable_node, "state_scope_fallback", "current_contract_only",
                detail=str(exc)))
        self.mode, self.version_evidence = None, None
        try:
            interval, evidence = effective_interval(view.source, view.tree.root_node, metadata)
            self.mode = mode_for(view.source, view.tree.root_node, interval)
            self.version_evidence = evidence
        except (Unsupported, OSError) as exc:
            self.version_evidence = {"verified": False, "reason": str(exc)}
        if callable_node.type in CALLABLE_TYPES:
            self._collect_locals()
            self._collect_aliases()

    def _diagnostic(self, node, kind, reason, **extra):
        return dict({"kind": kind, "reason": reason, "file": self.view.file,
                     "callable": self.callable_id, "start": node.start_byte,
                     "end": node.end_byte, "ast_type": node.type}, **extra)

    def _record(self, node, decision):
        kind = ("state_binding_unresolved" if decision.classification == "unresolved"
                else "state_binding_excluded")
        if not decision.declarations:
            self.diagnostics.append(self._diagnostic(
                node, kind, decision.reason, name=text(self.view.source, node),
                classification=decision.classification))

    def _collect_locals(self):
        for node in walk(self.context):
            if node.type in ("parameter", "variable_declaration"):
                name = node.child_by_field_name("name")
                if name is not None:
                    spelling = text(self.view.source, name)
                    self.locals.add(spelling)
                    self.local_declarations.setdefault(spelling, []).append(node)
            elif node.type == "variable_declaration_tuple":
                # Legacy var (a,b) has identifiers, not variable_declaration
                # children. Mask these names, without inventing inferred types.
                for name in node.named_children:
                    if name.type == "identifier":
                        spelling = text(self.view.source, name)
                        self.locals.add(spelling)
                        self.local_declarations.setdefault(spelling, []).append(node)

    def _state(self, name):
        if name in self.locals:
            return StateBinding(reason="callable_local_shadows_state", classification="local")
        nodes = self.members.get(name, ())
        if len(nodes) != 1:
            return StateBinding(reason="state_name_missing" if not nodes else "state_name_ambiguous")
        node = nodes[0]
        if node.type != "state_variable_declaration":
            return StateBinding(reason="unique_non_state_member", classification="non_state")
        if not self.include_constants and any(child.type == "constant" for child in node.children):
            return StateBinding(reason="constant_excluded", classification="constant")
        return StateBinding((node,), False, "state", "unique_state_declaration")

    def resolve(self, node, allow_alias=True, chain=False):
        if node is None or node.type != "identifier":
            return StateBinding(reason="not_a_bare_chain_root", classification="excluded")
        name = text(self.view.source, node)
        if name in ("this", "super"):
            decision = StateBinding(reason="qualified_namespace_excluded", classification="non_state")
        elif name in self.locals:
            if allow_alias and chain and name in self.aliases:
                decision = StateBinding(self.aliases[name], True, "alias",
                                        "flow_insensitive_storage_alias_union")
            else:
                decision = StateBinding(reason="callable_local_shadows_state", classification="local")
        else:
            decision = self._state(name)
            if not decision.declarations and decision.reason == "state_name_missing":
                # Builtin environment namespaces are not state declarations.
                if name in ("msg", "tx", "block", "_"):
                    decision = StateBinding(reason="non_state_namespace", classification="non_state")
                elif any(n.type in CONTAINERS and n.child_by_field_name("name") is not None
                         and text(self.view.source, n.child_by_field_name("name")) == name
                         for n in self.view.tree.root_node.named_children):
                    decision = StateBinding(reason="contract_qualification_excluded",
                                            classification="non_state")
        self._record(node, decision)
        return decision

    def _struct(self, type_node):
        if type_node is None:
            return None
        name = text(self.view.source, type_node)
        nodes = self.members.get(name, ())
        return nodes[0] if len(nodes) == 1 and nodes[0].type == "struct_declaration" else None

    def _reference_type(self, node):
        if node is None:
            return False
        if any(child.type in ("[", "mapping") for child in node.children):
            return True
        # Legacy local string/bytes references have the same storage default
        # as arrays. Exact spelling excludes fixed-size bytes1 ... bytes32.
        if node.type == "type_name" and text(self.view.source, node) in ("string", "bytes"):
            return True
        return self._struct(node) is not None

    def _alias_kind(self, declaration):
        location = declaration.child_by_field_name("location")
        location = text(self.view.source, location) if location is not None else None
        if location in ("memory", "calldata"):
            return None
        if location == "storage":
            return "explicit_storage"
        # Legacy reference parameters/returns default to memory, unlike local
        # reference declarations. Explicit storage above remains supported.
        if declaration.type != "variable_declaration":
            return None
        type_node = declaration.child_by_field_name("type")
        if type_node is None:
            return None
        spelling = text(self.view.source, type_node)
        if self.mode != "legacy":
            if self.mode is None and (spelling == "var" or self._reference_type(type_node)):
                self.diagnostics.append(self._diagnostic(
                    declaration, "state_alias_unresolved", "legacy_alias_version_unconfirmed",
                    version_evidence=self.version_evidence))
            return None
        if spelling == "var":
            return "legacy_inferred"
        if self._reference_type(type_node):
            return "legacy_reference"
        return None

    def _selected_type(self, expression, declaration):
        return self._access_type(expression, declaration.child_by_field_name("type"))

    def _access_type(self, expression, typ):
        """Follow only confirmed array/mapping/struct fields from a root type."""
        expression = unwrap(expression)
        root = chain_root(expression)
        if root is None:
            return None
        chain, cursor = [], expression
        while cursor is not None and cursor.type in ("member_expression", "array_access"):
            chain.append(cursor)
            cursor = unwrap(cursor.child_by_field_name(
                "object" if cursor.type == "member_expression" else "base"))
        for operation in reversed(chain):
            if typ is None:
                return None
            if operation.type == "array_access":
                if any(c.type == "mapping" for c in typ.children):
                    typ = typ.child_by_field_name("value_type")
                elif any(c.type == "[" for c in typ.children):
                    bases = [c for c in typ.named_children if c.type == "type_name"]
                    typ = bases[0] if len(bases) == 1 else None
                else:
                    return None
            else:
                struct = self._struct(typ)
                prop = operation.child_by_field_name("property")
                if struct is None or prop is None:
                    return None
                fields = [n for n in struct.named_children
                          if n.type == "struct_member" and n.child_by_field_name("name") is not None
                          and text(self.view.source, n.child_by_field_name("name")) == text(self.view.source, prop)]
                typ = fields[0].child_by_field_name("type") if len(fields) == 1 else None
        return typ

    def array_receiver(self, expression):
        """Prove push/pop receiver is a dynamic storage array (including bytes).

        Alias roots use the type selected by their initializer/rebindings,
        rather than the root state's type. Every possible selected target must
        have a supported type; this proves no overload/call or runtime behavior.
        """
        root = chain_root(expression)
        if root is None:
            return False, "receiver_root_unresolved"
        name = text(self.view.source, root)
        if name in self.locals:
            if name not in self.aliases:
                return False, "receiver_local_not_state_alias"
            roots = self.alias_types.get(name, ())
            if not roots:
                return False, "alias_pointee_type_unresolved"
            types = [self._access_type(expression, typ) for typ in roots]
        else:
            binding = self._state(name)
            if not binding.declarations:
                return False, "receiver_" + binding.reason
            types = [self._selected_type(expression, state)
                     for state in binding.declarations]
        for typ in types:
            if typ is None:
                return False, "receiver_selected_type_unresolved"
            if text(self.view.source, typ).strip() == "bytes":
                continue
            children = [c for c in typ.children if "comment" not in c.type]
            openings = [i for i, c in enumerate(children) if c.type == "["]
            if len(openings) == 1:
                index = openings[0]
                if index + 1 < len(children) and children[index + 1].type == "]":
                    continue
                return False, "receiver_fixed_array"
            return False, "receiver_not_dynamic_array"
        return bool(types), "confirmed_dynamic_storage_array"

    def _collect_aliases(self):
        candidates = {}
        for name, declarations in self.local_declarations.items():
            if len(declarations) != 1:
                self.diagnostics.append(self._diagnostic(
                    declarations[0], "state_alias_unresolved", "ambiguous_local_declaration",
                    name=name, declaration_count=len(declarations)))
                continue
            kind = self._alias_kind(declarations[0])
            if kind is not None:
                candidates[name] = (declarations[0], kind)
        roots = {name: {} for name in candidates}
        alias_types = {name: [] for name in candidates}
        sources = {name: [] for name in candidates}
        for name, (declaration, _) in candidates.items():
            parent = declaration.parent
            if parent is not None and parent.type == "variable_declaration_statement":
                declarators = [n for n in parent.named_children if n.type == "variable_declaration"]
                rhs = parent.child_by_field_name("value")
                if len(declarators) == 1 and rhs is not None:
                    sources[name].append(rhs)
        for node in walk(self.context):
            if node.type != "assignment_expression":
                continue
            lhs = unwrap(node.child_by_field_name("left"))
            rhs = node.child_by_field_name("right")
            if lhs is not None and lhs.type == "identifier":
                name = text(self.view.source, lhs)
                if name in candidates and rhs is not None:
                    sources[name].append(rhs)
        for name, expressions in sources.items():
            declaration, kind = candidates[name]
            for expression in expressions:
                root = chain_root(expression)
                if root is None:
                    self.diagnostics.append(self._diagnostic(
                        expression, "state_alias_unresolved", "alias_rhs_not_state_access_chain",
                        name=name))
                    continue
                decision = self._state(text(self.view.source, root))
                if not decision.declarations:
                    self.diagnostics.append(self._diagnostic(
                        expression, "state_alias_unresolved", "alias_rhs_" + decision.reason,
                        name=name))
                    continue
                for state in decision.declarations:
                    selected_type = self._selected_type(expression, state)
                    if kind == "legacy_inferred" and not self._reference_type(selected_type):
                        self.diagnostics.append(self._diagnostic(
                            expression, "state_alias_unresolved", "legacy_var_not_proven_reference",
                            name=name))
                        continue
                    roots[name][key(state)] = state
                    alias_types[name].append(selected_type)
                    self.alias_bindings.append({
                        "name": name, "local_start": declaration.start_byte,
                        "local_end": declaration.end_byte, "kind": kind,
                        "state_name": text(self.view.source, state.child_by_field_name("name")),
                        "state_start": state.start_byte, "state_end": state.end_byte,
                        "source_start": expression.start_byte, "source_end": expression.end_byte,
                        "flow_sensitive": False,
                        "selected_type": text(self.view.source, selected_type)
                            if selected_type is not None else None,
                    })
        self.alias_types = {name: tuple(values) for name, values in alias_types.items() if values}
        self.aliases = {name: tuple(values[k] for k in sorted(values))
                        for name, values in roots.items() if values}

    def audit(self):
        return {"callable": self.callable_id, "context_type": self.context.type,
                "local_names": sorted(self.locals), "mode_for_implicit_alias": self.mode,
                "version_evidence": self.version_evidence,
                "scope_fallback": self.scope_fallback,
                "aliases": list(self.alias_bindings),
                "diagnostics": list(self.diagnostics)}


# ----------------------------------------------------------------------
# dfg_v2/state_access
# Per-region L2 state READ/WRITE occurrences, without CFG or flow claims.
#
# Diagnostics are cumulative, as are StateBinder diagnostics. extract() returns
# only this invocation's occurrences; callers may snapshot diagnostic lengths.
# Property names, types and declarations are never identifier reads.
@dataclass(frozen=True)
class StateAccess:
    kind: str
    declaration: object
    occurrence: object
    occurrence_span: object
    via_alias: bool
    reason: str
    state_name: str

class StateAccessExtractor:
    def __init__(self, binder):
        self.binder = binder
        self.view = binder.view
        self.diagnostics = []
        self._events = []

    def _diagnostic(self, node, reason):
        self.diagnostics.append({
            "kind": "state_access_unresolved", "reason": reason,
            "file": self.view.file, "callable": self.binder.callable_id,
            "start": node.start_byte, "end": node.end_byte, "ast_type": node.type,
        })

    def _emit(self, node, root, kind, chain=False):
        decision = self.binder.resolve(root, chain=chain)
        for declaration in decision.declarations:
            self._events.append(StateAccess(
                kind, declaration, node, span(self.view.file, node),
                decision.via_alias, decision.reason,
                text(self.view.source, declaration.child_by_field_name("name"))))

    def _indices(self, node):
        """Only chain bases, never member properties."""
        cursor = unwrap(node)
        indices = []
        while cursor is not None and cursor.type in ("member_expression", "array_access"):
            if cursor.type == "array_access":
                indices.append(cursor.child_by_field_name("index"))
                cursor = unwrap(cursor.child_by_field_name("base"))
            else:
                cursor = unwrap(cursor.child_by_field_name("object"))
        return [x for x in reversed(indices) if x is not None]

    def _access(self, node, kinds, occurrence=None, chain_override=False):
        node = unwrap(node)
        if node is None:
            return
        if node.type == "tuple_expression":
            for child in node.named_children:
                if "comment" not in child.type:
                    self._access(child, kinds)
            return
        root = chain_root(node)
        if root is None:
            self._diagnostic(node, "access_chain_root_not_bare_identifier")
            # A computed receiver may still contain reads of state arguments.
            self._visit(node)
            return
        chain = chain_override or node.type in ("member_expression", "array_access")
        for kind in kinds:
            self._emit(occurrence or node, root, kind, chain)
        for index in self._indices(node):
            self._visit(index)

    def _visit(self, node):
        if node is None:
            return
        kind = node.type
        if "comment" in kind:
            return
        if kind in ("identifier",):
            self._emit(node, node, "READ")
            return
        if kind in ("member_expression", "array_access"):
            shape = prefix_access_shape(node)
            if shape is not None:
                operator, argument, indices = shape
                kinds = ("WRITE",) if operator == "delete" else ("READ", "WRITE")
                self._access(argument, kinds, occurrence=node, chain_override=True)
                for index in indices:
                    self._visit(index)
            else:
                root = chain_root(node)
                if root is not None:
                    self._access(node, ("READ",))
                else:
                    # For foo(state).field, the property is not a variable.
                    self._visit(node.child_by_field_name(
                        "object" if kind == "member_expression" else "base"))
                    if kind == "array_access":
                        self._visit(node.child_by_field_name("index"))
            return
        if kind in ("assignment_expression", "augmented_assignment_expression"):
            self._access(node.child_by_field_name("left"),
                         ("READ", "WRITE") if kind == "augmented_assignment_expression" else ("WRITE",))
            self._visit(node.child_by_field_name("right"))
            return
        if kind == "update_expression":
            self._access(node.child_by_field_name("argument"), ("READ", "WRITE"))
            return
        if kind == "unary_expression":
            operator = node.child_by_field_name("operator")
            if operator is not None and text(self.view.source, operator) == "delete":
                self._access(node.child_by_field_name("argument"), ("WRITE",))
            else:
                self._visit(node.child_by_field_name("argument"))
            return
        if kind == "call_expression":
            callee = node.child_by_field_name("function")
            prop = callee.child_by_field_name("property") if callee is not None and callee.type == "member_expression" else None
            if prop is not None and text(self.view.source, prop) in ("push", "pop"):
                receiver = callee.child_by_field_name("object")
                confirmed, reason = self.binder.array_receiver(receiver)
                if confirmed:
                    self._access(receiver, ("READ", "WRITE"), chain_override=True)
                else:
                    # A user method named push/pop is an ordinary call, not
                    # proof that the state-held receiver itself is mutated.
                    self._diagnostic(node, "push_pop_write_skipped:" + reason)
                    self._visit(callee)
            else:
                self._visit(callee)
            for child in node.named_children:
                if child.type in ("call_argument", "call_struct_argument"):
                    self._visit(child)
            return
        if kind in ("variable_declaration_statement", "state_variable_declaration"):
            self._visit(node.child_by_field_name("value"))
            return
        if kind in ("call_struct_argument", "struct_field_assignment"):
            # Named-call/struct/call-option keys are field names, not reads.
            # The containing struct_expression still visits its type/receiver.
            self._visit(node.child_by_field_name("value"))
            return
        if kind == "emit_statement":
            for child in node.named_children:
                if child.type in ("call_argument", "call_struct_argument"):
                    self._visit(child)
            return
        if kind == "revert_statement":
            for child in node.named_children:
                if child.type in ("call_argument", "call_struct_argument",
                                  "parenthesized_expression", "revert_arguments"):
                    self._visit(child)
                elif child.type == "call_expression":
                    # A custom error's callee name is not a state read.
                    for argument in child.named_children:
                        if argument.type in ("call_argument", "call_struct_argument"):
                            self._visit(argument)
            return
        if kind in ("function_body", "block_statement", "block",
                    "if_statement", "for_statement", "while_statement",
                    "do_while_statement", "function_definition",
                    "constructor_definition", "modifier_definition"):
            self._diagnostic(node, "non_expression_region_requires_unit_selection")
            return
        if kind in ("assembly_statement", "inline_assembly_statement"):
            self._diagnostic(node, "assembly_access_not_interpreted")
            return
        if kind in ("variable_declaration", "variable_declaration_tuple",
                    "parameter", "type_name", "primitive_type", "user_defined_type",
                    "struct_declaration", "struct_member", "visibility",
                    "string_literal", "string", "hex_string_literal",
                    "number_literal", "boolean_literal", "throw_statement",
                    "break_statement", "continue_statement"):
            return
        # Wrappers, operands, returns and conditions are unordered occurrence
        # sets. This deliberately creates no sequencing or call effect summary.
        for child in node.named_children:
            self._visit(child)

    def extract(self, regions):
        if hasattr(regions, "regions"):
            regions = regions.regions
        if not isinstance(regions, (list, tuple)):
            regions = [regions]
        self._events = []
        for region in regions:
            self._visit(region)
        return list(self._events)
