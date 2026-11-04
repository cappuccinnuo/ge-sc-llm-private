"""Aggregate local symbols; lexical identity remains the scalar implementation.

The fallback registration block mirrors scripts/DFG/symbol_table.py::_add,
SHA256 ce57e804d684da00792ff954e53c71a55254214b2e1ef3163025aa66d8c31566.
Only accepted type classification is extended; scope/visibility/identity and
the original frozen Symbol are unchanged.
"""
import re

from ..models import Span, Symbol, Unsupported
from ..symbol_table import SymbolTable, _same, _scalar_type, _walk


def _scalar_name(name):
    integer = re.fullmatch(r"(u?int)([0-9]+)", name)
    fixed = re.fullmatch(r"bytes([0-9]+)", name)
    return bool(name in ("bool", "address", "address payable", "uint", "int")
                or (integer and 8 <= int(integer.group(2)) <= 256
                    and int(integer.group(2)) % 8 == 0)
                or (fixed and 1 <= int(fixed.group(1)) <= 32))


def _extended_type(node, mode):
    """Check grammar structure; never infer the pointee type or storage slot."""
    if node is None:
        raise Unsupported("V2: declaration has no recognizable type")
    name = " ".join(node.text.decode("utf8").split())
    if any(item.type in ("function", "function_type") for item in _walk(node)):
        raise Unsupported("V2: function type remains unsupported")
    # Function is an unnamed grammar child and is not included by _walk.
    if any(child.type == "function" for child in node.children):
        raise Unsupported("V2: function type remains unsupported")
    children = [child for child in node.named_children if "comment" not in child.type]
    if node.type == "type_name":
        if any(child.type == "function" for child in node.children):
            raise Unsupported("V2: function type remains unsupported")
        if any(child.type == "[" for child in node.children):
            bases = [child for child in children if child.type == "type_name"]
            if len(bases) != 1:
                raise Unsupported("V2: ambiguous array element type")
            _extended_type(bases[0], mode)
            return True
        if any(child.type == "mapping" for child in node.children):
            key = node.child_by_field_name("key_type")
            value = node.child_by_field_name("value_type")
            if key is None or value is None:
                raise Unsupported("V2: mapping lacks key/value type")
            _extended_type(key, mode)
            _extended_type(value, mode)
            return True
        if len(children) == 1 and children[0].type in ("primitive_type", "user_defined_type"):
            return _extended_type(children[0], mode)
        raise Unsupported("V2: unsupported aggregate type shape: " + name)
    if node.type == "user_defined_type":
        # Includes contract/enum names, conservatively represented as aggregates.
        return True
    if node.type == "primitive_type":
        if name == "var":
            if mode != "legacy":
                raise Unsupported("V2: inferred var is only allowed in legacy mode")
            return True
        if name in ("string", "bytes"):
            return True
        if _scalar_name(name):
            return False
    raise Unsupported("V2: unsupported type: " + name)


class ExtendedSymbolTable(SymbolTable):
    def __init__(self, source, file, function, mode):
        self.aggregate_info = {}
        super().__init__(source, file, function, mode)

    def _add(self, declaration, kind, scope, visible):
        try:
            type_name = _scalar_type(declaration)
        except Unsupported:
            node = declaration.child_by_field_name("type")
            aggregate = _extended_type(node, self.mode)
            type_name = " ".join(node.text.decode("utf8").split())
            location = declaration.child_by_field_name("location")
            location = location.text.decode("utf8") if location is not None else None
            if location not in (None, "memory", "storage", "calldata"):
                raise Unsupported("V2: unknown data location: " + location)
            name_node = declaration.child_by_field_name("name")
            if name_node is None:
                if kind in ("parameter", "return"):
                    return
                raise Unsupported("Local declaration is missing a name")
            name = name_node.text.decode("utf8")
            # The identity and duplicate/scope checks below are copied verbatim
            # from the original registration path cited above.
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
        else:
            # Exact existing scalar registration and its validation.
            super()._add(declaration, kind, scope, visible)
            symbol = self.declarations.get(declaration.start_byte)
            if symbol is None:  # An unnamed parameter/return is not a symbol.
                return
            aggregate, location = False, None
        self.aggregate_info[symbol.id] = {
            "aggregate": aggregate, "location": location, "type": type_name,
        }
