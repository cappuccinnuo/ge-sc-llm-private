"""Scalar declaration identities for the statement DDG.

Unsupported reference/inferred types fall back the whole function.
Scope reference: Solidity documentation, Scoping and Declarations.
"""
import re
from .models import Span, Symbol, Unsupported


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
