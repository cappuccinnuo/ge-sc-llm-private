"""Resolve direct declarations and conservative mapping identities; no label inputs."""
import re
from ..frontend import span, text
from ..models import Unsupported
from ..call_binding import CONTAINERS
from .models import DeclarationRef, StateLocation

def scalar_type(name):
    name = " ".join(name.split())
    if name in ("address", "address payable"): return "address"
    if name == "bool": return name
    m = re.fullmatch(r"(u?int)([0-9]*)", name)
    if m:
        bits = int(m.group(2) or 256)
        if 8 <= bits <= 256 and bits % 8 == 0: return m.group(1) + str(bits)
    m = re.fullmatch(r"bytes([0-9]+)", name)
    if m and 1 <= int(m.group(1)) <= 32: return name
    return None

def alias(a, b):
    if a.root.id != b.root.id: return "NO_ALIAS"
    if a.key_kind == b.key_kind == "scalar": return "EXACT"
    if a.certainty == b.certainty == "EXACT" and (a.key_kind, a.key_value, a.key_type) == (b.key_kind, b.key_value, b.key_type):
        return "EXACT"
    if a.key_kind == b.key_kind == "constant" and a.key_type == b.key_type and a.key_value != b.key_value:
        return "NO_ALIAS"
    return "MAY"

class LocationTable:
    def __init__(self, view, function, scalar_table, ir):
        self.view, self.function, self.table, self.ir = view, function, scalar_table, ir
        c = function.parent
        while c is not None and c.type not in CONTAINERS: c = c.parent
        if c is None: raise Unsupported("state: no direct contract/library scope")
        self.contract = c
        if any(n.type == "import_directive" for n in view.tree.root_node.named_children):
            raise Unsupported("state: import binding unsupported")
        if any(n.type in ("is", "inheritance_specifier") for n in c.children):
            raise Unsupported("state: inheritance binding unsupported")
        self.body = c.child_by_field_name("body")
        if self.body is None: raise Unsupported("state: missing contract body")
        self.members = {}
        self.roots, self.locations = {}, {}
        self.written_locals = {s for b in ir.blocks.values() for e in b.events if e.kind != "entry" for s in e.writes}
        for n in self.body.named_children:
            name = n.child_by_field_name("name")
            if name is not None:
                self.members.setdefault(text(view.source, name), []).append(n)
            if n.type != "state_variable_declaration" or name is None: continue
            typ = n.child_by_field_name("type")
            raw = text(view.source, typ) if typ else ""
            kind, keytype = "unsupported", ""
            value_type = scalar_type(raw)
            if value_type: kind = "scalar"
            elif typ and any(x.type == "mapping" for x in typ.children):
                kt, vt = typ.child_by_field_name("key_type"), typ.child_by_field_name("value_type")
                keytype = scalar_type(text(view.source, kt)) if kt else None
                if keytype and vt and scalar_type(text(view.source, vt)): kind = "mapping"
            if any(x.type in ("constant", "immutable") or text(view.source, x) in ("constant", "immutable") for x in n.children):
                kind = "unsupported"
            ident = "{}:{}:{}:{}".format(view.sha256, view.file, c.start_byte, n.start_byte)
            root = DeclarationRef(ident, view.sha256, view.file, span(view.file,c),span(view.file,n),
                                  text(view.source,name),raw,kind,keytype or "")
            if root.name in self.roots: raise Unsupported("state: duplicate declaration name")
            self.roots[root.name] = root

    def bare_root(self, node):
        if node.type != "identifier": return None
        name = text(self.view.source,node)
        if self.table.resolve(name,node) is not None: return None
        root = self.roots.get(name)
        if root is not None and len(self.members.get(name,())) != 1:
            raise Unsupported("state: ambiguous declaration binding")
        return root

    def builtin(self, name, node):
        if self.table.resolve(name,node) is not None or name in self.members: return False
        return not any(n.child_by_field_name("name") is not None and
                       text(self.view.source,n.child_by_field_name("name")) == name
                       for n in self.view.tree.root_node.named_children)

    def _intern(self, root, kind, value, typ, certainty, evidence):
        ident = root.id + ":" + repr((kind,value,typ))
        location = StateLocation(ident,root,kind,value,typ,certainty,tuple(evidence))
        if ident not in self.locations: self.locations[ident] = location
        return self.locations[ident]

    def location(self, node):
        if node.type == "identifier":
            root = self.bare_root(node)
            if root is None: return None
            if root.kind != "scalar": raise Unsupported("state: unsupported whole storage value: " + root.type_name)
            return self._intern(root,"scalar","",root.type_name,"EXACT",["direct declaration and lexical binding"])
        if node.type != "array_access": return None
        base,index = node.child_by_field_name("base"),node.child_by_field_name("index")
        if base is None or index is None: raise Unsupported("state: malformed indexed access")
        root = self.bare_root(base)
        if root is None:
            raise Unsupported("state: indexed base is not a direct mapping declaration")
        if root.kind != "mapping":
            raise Unsupported("state: arrays/nested mapping/references unsupported: " + root.type_name)
        kind,value,certainty,evidence = self.key(index,root.key_type)
        return self._intern(root,kind,value,root.key_type,certainty,evidence)

    def key(self, node, typ):
        raw = text(self.view.source,node).strip()
        if node.type == "number_literal" and re.fullmatch(r"(0[xX][0-9a-fA-F]+|[0-9]+)",raw):
            val = int(raw,16 if raw.lower().startswith("0x") else 10)
            bits = 160 if typ == "address" else int(re.sub(r"^u?int","",typ)) if re.fullmatch(r"u?int[0-9]+",typ) else None
            limit = (1 << (bits - (1 if typ.startswith("int") else 0))) if bits else None
            if limit is not None and 0 <= val < limit:
                return "constant",str(val),"EXACT",["typed in-range constant"]
        if raw in ("true","false") and typ == "bool":
            return "constant",raw,"EXACT",["typed boolean constant"]
        if node.type == "member_expression":
            obj,prop=node.child_by_field_name("object"),node.child_by_field_name("property")
            if obj is not None and prop is not None and text(self.view.source,obj) == "msg" and text(self.view.source,prop) == "sender" and typ == "address" and self.builtin("msg",obj):
                return "frame",self.ir.id+":msg.sender","EXACT",["unshadowed builtin; stable in this invocation"]
        if node.type == "identifier":
            s=self.table.resolve(raw,node)
            if s and s.kind == "parameter" and s.id not in self.written_locals and scalar_type(s.type_name) == typ:
                return "parameter",s.id,"EXACT",["unmodified value parameter within invocation"]
        return "unknown","{}:{}".format(node.start_byte,node.end_byte),"UNKNOWN",["key equality not proved; no strong update"]

    def address_receiver(self,node):
        if node is None:return False
        if node.type == "identifier":
            s=self.table.resolve(text(self.view.source,node),node)
            r=self.bare_root(node)
            return (s is not None and scalar_type(s.type_name)=="address") or (r is not None and scalar_type(r.type_name)=="address")
        if node.type == "member_expression":
            obj,prop=node.child_by_field_name("object"),node.child_by_field_name("property")
            return obj is not None and prop is not None and text(self.view.source,obj)=="msg" and text(self.view.source,prop)=="sender" and self.builtin("msg",obj)
        if node.type == "type_cast_expression":
            return any(text(self.view.source,c) in ("address","address payable") for c in node.named_children)
        return False
