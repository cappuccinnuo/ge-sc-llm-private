"""Symbol tables for contracts and functions, and static call binding."""
import re
from dataclasses import dataclass, field

from dfg.analysis.frontend import solidity_version_interval, text, walk
from dfg.analysis.ir import Span, Symbol, Unsupported


# ----------------------------------------------------------------------
# symbol_table
# Scalar declaration identities for the statement DDG.
#
# Unsupported reference/inferred types fall back the whole function.
# Scope reference: Solidity documentation, Scoping and Declarations.
def _walk(node):
    yield node
    for child in node.named_children:
        for descendant in _walk(child):
            yield descendant

def _same(left, right):
    return (left.start_byte, left.end_byte, left.type) == (
        right.start_byte, right.end_byte, right.type)

def _contains(scope, node):
    return scope.start_byte <= node.start_byte and node.end_byte <= scope.end_byte

def _scalar_type(declaration):
    node = declaration.child_by_field_name("type")
    if node is None:
        raise Unsupported("Declaration has no explicit scalar type")
    name = " ".join(node.text.decode("utf8").split())
    integer = re.fullmatch(r"(u?int)([0-9]+)", name)
    fixed_bytes = re.fullmatch(r"bytes([0-9]+)", name)
    supported = (
        name in ("bool", "address", "address payable", "uint", "int")
        or (integer and 8 <= int(integer.group(2)) <= 256
            and int(integer.group(2)) % 8 == 0)
        or (fixed_bytes and 1 <= int(fixed_bytes.group(1)) <= 32)
    )
    if not supported:
        raise Unsupported("Unsupported non-scalar or inferred type: " + name)
    if declaration.child_by_field_name("location") is not None:
        raise Unsupported("Data-location declaration is outside the scalar scope")
    return name

class SymbolTable:
    """Resolve scalar declarations; never invent definitions for unknown names."""

    def __init__(self, source, file, function, mode):
        if mode not in ("legacy", "modern"):
            raise ValueError("mode must be legacy or modern")
        if not isinstance(source, str) or not isinstance(file, str):
            raise TypeError("source and file must be strings")
        if function.has_error:
            raise Unsupported("Cannot collect symbols from a malformed function")
        if function.type not in (
            "function_definition", "constructor_definition",
            "modifier_definition", "fallback_receive_definition",
        ):
            raise Unsupported("Expected a callable AST node")
        if source.encode("utf8")[function.start_byte:function.end_byte] != function.text:
            raise ValueError("AST byte coordinates do not refer to supplied source")
        self.source, self.file, self.function, self.mode = source, file, function, mode
        self.function_id = "{}:{}".format(file, function.start_byte)
        self.symbols, self.declarations, self._bindings = {}, {}, {}
        self.entry_symbols = []
        self._body = function.child_by_field_name("body")
        if self._body is None:
            raise Unsupported("Callable without a body")
        for child in function.named_children:
            if child.type == "parameter":
                self._add(child, "parameter", self._body, self._body.start_byte)
        returns = function.child_by_field_name("return_type")
        if returns is not None:
            for child in returns.named_children:
                if child.type == "parameter":
                    self._add(child, "return", self._body, self._body.start_byte)
        for node in _walk(self._body):
            if node.type == "variable_declaration":
                statement = self._statement(node)
                scope = self._body if mode == "legacy" else self._local_scope(statement)
                visible = self._body.start_byte if mode == "legacy" else statement.end_byte
                if mode == "modern":
                    self._check_initializer_reference(node, statement)
                self._add(node, "local", scope, visible)
            elif node.type == "variable_declaration_statement":
                if not any(item.type == "variable_declaration" for item in _walk(node)):
                    raise Unsupported("Declaration without explicit scalar declarators")
        self.entry_symbols = [
            symbol for symbol in self.symbols.values()
            if symbol.kind in ("parameter", "return") or mode == "legacy"
        ]

    def _statement(self, declaration):
        pointer = declaration.parent
        while pointer is not None and pointer.type == "variable_declaration_tuple":
            pointer = pointer.parent
        if pointer is None or pointer.type != "variable_declaration_statement":
            raise Unsupported("Local declaration is not in a supported declaration statement")
        return pointer

    def _check_initializer_reference(self, declaration, statement):
        name_node = declaration.child_by_field_name("name")
        value = statement.child_by_field_name("value")
        if name_node is None or value is None:
            return
        # Deliberately conservative for self/shadow initializer references.
        # Do not assume whether an occurrence binds the new or outer declaration.
        if any(n.type == "identifier" and n.text == name_node.text for n in _walk(value)):
            raise Unsupported("Ambiguous modern initializer binding: " + name_node.text.decode("utf8"))

    def _local_scope(self, statement):
        pointer = statement.parent
        while pointer is not None:
            if pointer.type == "for_statement":
                initial = pointer.child_by_field_name("initial")
                if initial is not None and _contains(initial, statement):
                    return pointer
            if pointer.type in ("block_statement", "function_body"):
                return pointer
            if _same(pointer, self.function):
                break
            pointer = pointer.parent
        raise Unsupported("Local declaration has no supported lexical scope")

    def _add(self, declaration, kind, scope, visible):
        type_name = _scalar_type(declaration)
        name_node = declaration.child_by_field_name("name")
        if name_node is None:
            if kind in ("parameter", "return"):
                return
            raise Unsupported("Local declaration is missing a name")
        name = name_node.text.decode("utf8")
        for old_scope, _, _ in self._bindings.get(name, ()):
            if _same(old_scope, scope):
                raise Unsupported("Duplicate declaration in the same scope: " + name)
        if declaration.start_byte in self.declarations:
            raise Unsupported("Ambiguous declaration byte position")
        identity = "{}:{}:{}".format(self.function_id, declaration.start_byte, name)
        symbol = Symbol(
            identity, name, self.function_id,
            Span(self.file, declaration.start_byte, declaration.end_byte, kind),
            kind, type_name,
        )
        self.symbols[identity] = symbol
        self.declarations[declaration.start_byte] = symbol
        self._bindings.setdefault(name, []).append((scope, visible, symbol))

    def resolve(self, name, node):
        if not _contains(self.function, node):
            return None
        candidates = [
            (scope.end_byte - scope.start_byte, symbol)
            for scope, visible, symbol in self._bindings.get(name, ())
            if _contains(scope, node) and node.start_byte >= visible
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise Unsupported("Ambiguous lexical binding: " + name)
        return candidates[0][1]

    def lookup_decl(self, declaration_node):
        symbol = self.declarations.get(declaration_node.start_byte)
        if symbol is None:
            raise Unsupported("Unknown scalar declaration")
        if symbol.declaration.end != declaration_node.end_byte:
            raise Unsupported("Declaration identity does not match its byte span")
        return symbol


# ----------------------------------------------------------------------
# call_binding
# B1: conservative binding of potentially terminating calls, not a type checker.
#
# Only selfdestruct/revert/suicide candidates are classified here. Ordinary calls
# keep the existing opaque intraprocedural treatment; no function summary or
# storage definition is introduced. Source positions are UTF-8 byte offsets.
BUILTIN = "builtin_terminal"

NON_BUILTIN = "non_builtin"

UNKNOWN = "unknown"

TERMINATORS = frozenset(("selfdestruct", "revert", "suicide"))

CONTAINERS = frozenset(("contract_declaration", "library_declaration", "interface_declaration"))

@dataclass(frozen=True)
class CallBinding:
    classification: str
    name: str
    form: str
    reason: str
    evidence: dict = field(default_factory=dict)

    @property
    def terminates(self):
        return self.classification == BUILTIN

class BindingUncertain(Unsupported):
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        super().__init__(diagnostic["reason"])

def key(node):
    return node.start_byte, node.end_byte, node.type

class CallBindingResolver:
    def __init__(self, view, function, table):
        self.view, self.function, self.table = view, function, table
        self.contract = function.parent
        while self.contract is not None and self.contract.type not in CONTAINERS:
            self.contract = self.contract.parent

    def diagnostic(self, node, decision):
        return {
            "kind": "call_binding", "function": self.table.function_id,
            "function_start": self.function.start_byte, "function_end": self.function.end_byte,
            "file": self.view.file, "start": node.start_byte, "end": node.end_byte,
            "line": node.start_point[0] + 1, "column": node.start_point[1] + 1,
            "call_name": decision.name, "call_form": decision.form,
            "classification": decision.classification,
            "reason": decision.reason, "evidence": decision.evidence,
        }

    def classify(self, node):
        """Return None for calls outside B1; never infer a builtin from absence alone."""
        if node.type == "revert_statement":
            error = node.child_by_field_name("error")
            if error is not None and error.type != "parenthesized_expression":
                # Explicit revert Error(args) is a distinct language form.
                # Resolving custom error declarations/types is outside this MVP.
                return CallBinding(UNKNOWN, text(self.view.source, error),
                                   "custom_error_revert", "custom_error_binding_not_supported",
                                   {"syntax": node.type})
            return self._unqualified("revert", node, "revert_call_statement")
        if node.type != "call_expression":
            return None
        callee = node.child_by_field_name("function")
        if callee is None:
            return None
        if callee.type == "identifier":
            name = text(self.view.source, callee)
            return self._unqualified(name, callee, "identifier_call") if name in TERMINATORS else None
        if callee.type == "member_expression":
            prop = callee.child_by_field_name("property")
            name = text(self.view.source, prop) if prop is not None else ""
            if name in TERMINATORS:
                return CallBinding(NON_BUILTIN, name, "member_call",
                                   "member_syntax_is_not_an_unqualified_builtin",
                                   {"callee": text(self.view.source, callee),
                                    "pointee_resolved": False})
            return None
        # Do not let parentheses/computed callees bypass the terminal guard.
        names = sorted({text(self.view.source, n) for n in walk(callee)
                        if n.type == "identifier" and text(self.view.source, n) in TERMINATORS})
        if names:
            return CallBinding(UNKNOWN, ",".join(names), "computed_call",
                               "computed_terminal_callee_not_supported",
                               {"callee": text(self.view.source, callee)})
        return None

    def _declarations(self, nodes, name):
        # Whole declaration scopes, not only text before this call.
        return [n for n in nodes if n.child_by_field_name("name") is not None
                and text(self.view.source, n.child_by_field_name("name")) == name]

    def _unqualified(self, name, occurrence, form):
        local = self.table.resolve(name, occurrence)
        if local is not None:
            # The unchanged SymbolTable only accepts scalars, not callable refs.
            return CallBinding(UNKNOWN, name, form, "local_scalar_is_not_a_supported_callee",
                               {"symbol": local.id, "declaration_start": local.declaration.start})
        root = self.view.tree.root_node
        imports = [n for n in root.named_children if n.type == "import_directive"]
        if imports:
            return CallBinding(UNKNOWN, name, form, "imports_prevent_closed_scope_binding",
                               {"imports": [{"start": n.start_byte, "text": text(self.view.source, n)}
                                            for n in imports]})
        if self.contract is not None and any(
                c.type in ("is", "inheritance_specifier") for c in self.contract.children):
            return CallBinding(UNKNOWN, name, form, "inheritance_binding_not_supported",
                               {"contract_start": self.contract.start_byte,
                                "bases": [text(self.view.source, c) for c in self.contract.children
                                          if c.type == "inheritance_specifier"]})
        declarations = []
        if self.contract is not None:
            body = self.contract.child_by_field_name("body")
            if body is None:
                return CallBinding(UNKNOWN, name, form, "missing_contract_scope")
            declarations = self._declarations(body.named_children, name)
        if not declarations:
            declarations = self._declarations(root.named_children, name)
        evidence = {"declarations": [{"kind": d.type, "start": d.start_byte,
                                     "end": d.end_byte} for d in declarations]}
        if len(declarations) > 1:
            return CallBinding(UNKNOWN, name, form, "overload_or_duplicate_binding_not_supported",
                               evidence)
        if declarations:
            declaration = declarations[0]
            if declaration.type == "function_definition":
                visibility = [text(self.view.source, c) for c in declaration.named_children
                              if c.type == "visibility"]
                if "external" in visibility:
                    return CallBinding(UNKNOWN, name, form, "external_function_used_unqualified",
                                       evidence)
                return CallBinding(NON_BUILTIN, name, form, "unique_visible_user_function",
                                   evidence)
            if declaration.type == "state_variable_declaration":
                type_node = declaration.child_by_field_name("type")
                if type_node is not None and any(c.type == "function" for c in type_node.children):
                    return CallBinding(NON_BUILTIN, name, form, "unique_state_function_pointer",
                                       dict(evidence, pointee_resolved=False))
            return CallBinding(UNKNOWN, name, form, "shadowing_declaration_not_a_supported_callee",
                               evidence)
        interval = solidity_version_interval(self.view.source, root)
        if interval is None:
            return CallBinding(UNKNOWN, name, form, "pragma_missing_for_builtin_availability")
        lo, hi = interval
        evidence = {"pragma_interval": {"lower_inclusive": list(lo), "upper_exclusive": list(hi)},
                    "closed_scope_checked": True, "scope_mode": self.view.mode}
        # Historical availability only; do not manufacture a chosen solc version.
        lower, upper = {
            "selfdestruct": ((0, 4, 0), (0, 9, 0)),
            "revert": ((0, 4, 10), (0, 9, 0)),
            "suicide": ((0, 4, 0), (0, 5, 0)),
        }[name]
        experimental = any("experimental" in text(self.view.source, n)
                           for n in root.named_children if n.type == "pragma_directive")
        if name == "suicide" and experimental:
            return CallBinding(UNKNOWN, name, form, "experimental_mode_suicide_unverified", evidence)
        if not (lower <= lo and hi <= upper):
            return CallBinding(UNKNOWN, name, form, "builtin_not_guaranteed_over_pragma_interval",
                               evidence)
        return CallBinding(BUILTIN, name, form, "closed_scope_and_version_confirm_builtin", evidence)

    def preflight(self):
        """Classify before any semantic blocks or facts are committed."""
        decisions, diagnostics = {}, []
        for node in walk(self.function):
            decision = self.classify(node)
            if decision is None:
                continue
            diagnostic = self.diagnostic(node, decision)
            if decision.classification == UNKNOWN:
                raise BindingUncertain(diagnostic)
            if decision.terminates and node.type == "call_expression":
                parent = node.parent
                if parent is None or parent.type != "expression_statement":
                    diagnostic = dict(diagnostic, reason="nested_builtin_termination_not_supported")
                    raise BindingUncertain(diagnostic)
            decisions[key(node)] = decision
            diagnostics.append(diagnostic)
        return decisions, diagnostics
