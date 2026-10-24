"""Per-region L2 state READ/WRITE occurrences, without CFG or flow claims.

Diagnostics are cumulative, as are StateBinder diagnostics. extract() returns
only this invocation's occurrences; callers may snapshot diagnostic lengths.
Property names, types and declarations are never identifier reads.
"""
from dataclasses import dataclass

from ..frontend import span, text
from .access_shape import prefix_access_shape
from .state_binding import chain_root, unwrap


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
        if kind == "call_struct_argument":
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
