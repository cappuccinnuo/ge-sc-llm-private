"""L3 source-only environment occurrences in statement-owned AST regions.

Keys represent values, not syntax spellings. The extractor does not inspect
HCG attributes, labels or features, and does not claim compilation or runtime
path feasibility. Deprecated spellings follow the explicit Prompt 4 table.
"""
from dataclasses import asdict, dataclass

from ..frontend import span, text
from .state_binding import unwrap


ENV_KEYS = (
    "msg.sender", "msg.value", "msg.data", "msg.sig",
    "tx.origin", "tx.gasprice",
    "block.timestamp", "block.number", "block.difficulty", "block.coinbase",
    "block.gaslimit", "blockhash", "gasleft", "this.balance",
)

SPELLINGS = {
    "msg.sender": "msg.sender",
    "msg.value": "msg.value",
    "msg.data": "msg.data",
    "msg.sig": "msg.sig",
    "tx.origin": "tx.origin",
    "tx.gasprice": "tx.gasprice",
    "block.timestamp": "block.timestamp",
    "block.number": "block.number",
    "block.difficulty": "block.difficulty",
    "block.coinbase": "block.coinbase",
    "block.gaslimit": "block.gaslimit",
    "blockhash(...)": "blockhash",
    "gasleft()": "gasleft",
    "this.balance": "this.balance",
    "now": "block.timestamp",
    "msg.gas": "gasleft",
    "block.blockhash(...)": "blockhash",
    "address(this).balance": "this.balance",
}

_ASSEMBLY = frozenset(("assembly_statement", "inline_assembly_statement"))
_NON_REGIONS = frozenset((
    "function_body", "block_statement", "block", "if_statement",
    "for_statement", "while_statement", "do_while_statement", "try_statement",
    "function_definition", "constructor_definition", "modifier_definition",
    "fallback_receive_definition",
))
_NON_EXPRESSIONS = frozenset((
    "variable_declaration", "variable_declaration_tuple", "parameter",
    "type_name", "primitive_type", "user_defined_type", "struct_declaration",
    "struct_member", "visibility", "string_literal", "string",
    "hex_string_literal", "number_literal", "boolean_literal",
    "throw_statement", "break_statement", "continue_statement",
))


@dataclass(frozen=True)
class EnvOccurrence:
    key: str
    spelling: str
    span: object


def _top_level_names(view):
    """Known file-level names, including syntactically explicit imports only."""
    result = set()
    for node in view.tree.root_node.named_children:
        name = node.child_by_field_name("name")
        if name is not None:
            result.add(text(view.source, name))
        if node.type != "import_directive":
            continue
        pending = None
        for index, child in enumerate(node.children):
            field = node.field_name_for_child(index)
            if field == "import_name":
                if pending is not None:
                    result.add(pending)
                pending = text(view.source, child)
            elif field == "alias":
                # Alias replaces the imported source name; * as X and
                # import "file" as X have no preceding import_name.
                result.add(text(view.source, child))
                pending = None
            elif child.type in (",", "}", ";"):
                if pending is not None:
                    result.add(pending)
                    pending = None
        if pending is not None:
            result.add(pending)
    return result


class EnvExtractor:
    """Independent L3 lexical occurrences; diagnostics accumulate per owner."""

    def __init__(self, binder):
        self.binder = binder
        self.view = binder.view
        self.top_level_names = _top_level_names(self.view)
        self.diagnostics = []
        self._events = []
        self._seen = set()
        self._seen_diagnostics = set()

    def _diagnostic(self, node, kind, reason, key=None, spelling=None, **evidence):
        identity = (node.start_byte, node.end_byte, kind, reason, key, spelling)
        if identity in self._seen_diagnostics:
            return
        self._seen_diagnostics.add(identity)
        self.diagnostics.append({
            "kind": kind, "reason": reason, "key": key, "spelling": spelling,
            "file": self.view.file, "callable": self.binder.callable_id,
            "start": node.start_byte, "end": node.end_byte, "ast_type": node.type,
            **evidence,
        })

    def _shadow_reason(self, name):
        if name in self.binder.locals:
            return "callable_local_name"
        if name in self.binder.members:
            return "contract_member_name"
        if name in self.top_level_names:
            return "file_top_level_name"
        return None

    def _emit(self, node, spelling, checked_name=None):
        key = SPELLINGS[spelling]
        reason = self._shadow_reason(checked_name) if checked_name is not None else None
        if reason is not None:
            self._diagnostic(node, "shadowed", reason, key, spelling)
            return
        identity = (node.start_byte, node.end_byte, key, spelling)
        if identity not in self._seen:
            self._seen.add(identity)
            self._events.append(EnvOccurrence(key, spelling, span(self.view.file, node)))

    def _excluded_position(self, node):
        cursor = node
        while cursor is not None:
            if cursor.type in ("type_name", "primitive_type", "user_defined_type"):
                return True
            parent = cursor.parent
            if parent is not None:
                if parent.child_by_field_name("name") == cursor:
                    return True
                if parent.type == "member_expression" and parent.child_by_field_name("property") == cursor:
                    return True
            cursor = parent
        return False

    @staticmethod
    def _assembly_owner(node):
        while node is not None:
            if node.type in _ASSEMBLY:
                return node
            node = node.parent
        return None

    def _this_balance_spelling(self, receiver):
        receiver = unwrap(receiver)
        if receiver is None:
            return None
        if receiver.type == "identifier" and text(self.view.source, receiver) == "this":
            return "this.balance"
        if receiver.type != "type_cast_expression":
            return None
        children = [c for c in receiver.named_children if "comment" not in c.type]
        if len(children) != 2 or children[0].type != "primitive_type":
            return None
        if text(self.view.source, children[0]) != "address":
            return None
        argument = unwrap(children[1])
        if argument is not None and argument.type == "identifier" and text(self.view.source, argument) == "this":
            return "address(this).balance"
        return None

    @staticmethod
    def _postfix_leaf(node):
        """Recover only unparenthesized trailing binary/unary operands.

        The installed grammar can put a + gasleft in call.function and
        a + address(this) in member.object. Solidity postfix operators
        bind more tightly. Explicit parentheses are a hard boundary: never
        reinterpret (a + gasleft)() or (a + msg).sender.
        """
        cursor, steps = node, []
        while cursor is not None and cursor.type in ("binary_expression", "unary_expression"):
            field = "right" if cursor.type == "binary_expression" else "argument"
            child = cursor.child_by_field_name(field)
            if child is None or child.end_byte != cursor.end_byte:
                return None, ()
            steps.append({
                "ast_type": cursor.type, "field": field,
                "start": cursor.start_byte, "end": cursor.end_byte,
            })
            cursor = child
        return (cursor, tuple(steps)) if steps else (None, ())

    def _known_member(self, receiver, property_name):
        receiver = unwrap(receiver)
        if receiver is not None and receiver.type == "identifier":
            root = text(self.view.source, receiver)
            if root in ("msg", "tx", "block"):
                spelling = root + "." + property_name
                if spelling == "block.blockhash":
                    spelling = "block.blockhash(...)"
                if spelling in SPELLINGS:
                    return spelling, root
        if property_name == "balance":
            spelling = self._this_balance_spelling(receiver)
            if spelling is not None:
                return spelling, None
        return None

    def _record_recovery(self, node, leaf, steps, spelling, checked_name):
        self._diagnostic(
            node, "grammar_shape_recovered",
            "postfix_after_unparenthesized_binary_or_unary",
            SPELLINGS[spelling], spelling,
            original_span=asdict(span(self.view.file, node)),
            leaf_span=asdict(span(self.view.file, leaf)),
            leaf_text=text(self.view.source, leaf),
            steps=list(steps), checked_name=checked_name,
            shadow_reason=self._shadow_reason(checked_name) if checked_name else None,
        )

    def _visit(self, node):
        if node is None or "comment" in node.type:
            return
        assembly = self._assembly_owner(node)
        if assembly is not None:
            self._diagnostic(assembly, "assembly_skipped", "assembly_access_not_interpreted")
            return
        if self._excluded_position(node):
            return
        kind = node.type
        if kind in _NON_REGIONS:
            self._diagnostic(node, "region_skipped", "non_expression_region_requires_unit_selection")
            return
        if kind in _NON_EXPRESSIONS:
            return
        if kind == "identifier":
            if text(self.view.source, node) == "now":
                self._emit(node, "now", "now")
            return
        if kind == "member_expression":
            receiver = unwrap(node.child_by_field_name("object"))
            prop = node.child_by_field_name("property")
            property_name = text(self.view.source, prop) if prop is not None else ""
            if receiver is not None and receiver.type == "identifier":
                root = text(self.view.source, receiver)
                if root in ("msg", "tx", "block"):
                    spelling = root + "." + property_name
                    if spelling == "block.blockhash":
                        spelling = "block.blockhash(...)"
                    if spelling in SPELLINGS:
                        self._emit(node, spelling, root)
                    else:
                        reason = self._shadow_reason(root)
                        self._diagnostic(
                            node, "shadowed" if reason else "unknown_env_member",
                            reason or "member_not_in_env_table",
                            "unregistered:" + spelling, spelling,
                        )
                    return
            if property_name == "balance":
                spelling = self._this_balance_spelling(receiver)
                if spelling is not None:
                    # this and the address cast are reserved in the contract
                    # syntax and deliberately not checked against user names.
                    self._emit(node, spelling)
                    return
            # Keep the raw receiver: unwrapping a composite parenthesized
            # receiver here would incorrectly reinterpret (a + msg).sender.
            raw_receiver = node.child_by_field_name("object")
            leaf, steps = self._postfix_leaf(raw_receiver)
            recovered = self._known_member(leaf, property_name) if leaf is not None else None
            if recovered is not None:
                spelling, checked_name = recovered
                self._record_recovery(node, leaf, steps, spelling, checked_name)
                self._emit(node, spelling, checked_name)
            # Retain all reads in left operands and nested receivers; the
            # synthetic postfix match itself is not revisited as an AST node.
            self._visit(raw_receiver)
            return
        if kind == "call_expression":
            callee = node.child_by_field_name("function")
            recognized = False
            if callee is not None and callee.type == "identifier":
                name = text(self.view.source, callee)
                spelling = {"blockhash": "blockhash(...)", "gasleft": "gasleft()"}.get(name)
                if spelling is not None:
                    self._emit(node, spelling, name)
                    recognized = True
            if not recognized:
                leaf, steps = self._postfix_leaf(callee)
                if leaf is not None and leaf.type == "identifier":
                    name = text(self.view.source, leaf)
                    spelling = {"blockhash": "blockhash(...)", "gasleft": "gasleft()"}.get(name)
                    if spelling is not None:
                        self._record_recovery(node, leaf, steps, spelling, name)
                        self._emit(node, spelling, name)
                        # Do not mark the entire binary/unary callee consumed:
                        # its other operands can contain independent ENV uses.
            for child in node.named_children:
                if child == callee and recognized:
                    continue
                self._visit(child)
            return
        if kind in ("variable_declaration_statement", "state_variable_declaration"):
            self._visit(node.child_by_field_name("value"))
            return
        if kind in ("call_struct_argument", "struct_field_assignment"):
            self._visit(node.child_by_field_name("value"))
            return
        if kind == "revert_statement":
            # A custom error's name is not a value occurrence. Arguments
            # survive even though the author HCG normally cannot project it.
            error = node.child_by_field_name("error")
            for child in node.named_children:
                if child != error or child.type == "parenthesized_expression":
                    self._visit(child)
            return
        for child in node.named_children:
            self._visit(child)

    def extract(self, regions):
        """Return only current occurrences, deduplicated by exact AST span."""
        if hasattr(regions, "regions"):
            regions = regions.regions
        if not isinstance(regions, (list, tuple)):
            regions = [regions]
        self._events, self._seen, self._seen_diagnostics = [], set(), set()
        for region in regions:
            self._visit(region)
        return list(self._events)
