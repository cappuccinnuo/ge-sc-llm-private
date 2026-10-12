"""Scalar def/use extraction. Unknown storage is not promoted to local symbols."""
from .frontend import span, text, walk
from .models import Event, Unsupported

WRITE_TYPES = {"assignment_expression", "augmented_assignment_expression",
               "update_expression"}
PURE_WRAPPERS = {"expression", "parenthesized_expression", "tuple_expression",
                 "binary_expression", "ternary_expression", "call_argument",
                 "revert_arguments"}
LITERALS = {"number_literal", "boolean_literal", "string_literal", "hex_string_literal",
            "unicode_string_literal", "string", "hex_string", "true", "false"}

class AccessExtractor:
    def __init__(self, source, table):
        self.source, self.table = source, table
        self.counter = 0
        self.diagnostics = []

    def _name(self, node):
        return text(self.source, node)

    def _resolve(self, node):
        symbol = self.table.resolve(self._name(node), node)
        if symbol is None:
            self.diagnostics.append({"kind":"unresolved_or_nonlocal",
                                     "name":self._name(node),"byte":node.start_byte})
        return symbol.id if symbol else None

    def reads(self, node):
        if node is None: return []
        t = node.type
        if t == "identifier":
            s = self._resolve(node)
            return [s] if s else []
        if t in LITERALS or "comment" in t: return []
        if t in WRITE_TYPES:
            raise Unsupported("Nested expression write / unspecified operand order")
        if t == "unary_expression":
            op = node.child_by_field_name("operator")
            if op and self._name(op) == "delete":
                raise Unsupported("Nested delete expression")
            return self.reads(node.child_by_field_name("argument"))
        if t == "member_expression":
            self.diagnostics.append({"kind":"opaque_member","byte":node.start_byte})
            return self.reads(node.child_by_field_name("object"))
        if t == "array_access":
            self.diagnostics.append({"kind":"opaque_storage_access","byte":node.start_byte})
            return self.reads(node.child_by_field_name("base")) + self.reads(node.child_by_field_name("index"))
        if t == "call_expression":
            result = []
            fn = node.child_by_field_name("function")
            if fn and fn.type != "identifier": result += self.reads(fn)
            elif fn and self.table.resolve(self._name(fn), fn):
                result += self.reads(fn)
            for c in node.named_children:
                if c.type in ("call_argument","call_struct_argument"):
                    result += self.reads(c)
            return result
        if t == "call_struct_argument":
            return self.reads(node.child_by_field_name("value"))
        if t == "type_cast_expression":
            return sum((self.reads(c) for c in node.named_children
                        if c.type not in ("primitive_type","type_name")), [])
        if t in PURE_WRAPPERS:
            return sum((self.reads(c) for c in node.named_children), [])
        raise Unsupported("Unsupported expression: " + t)

    def targets(self, node):
        if node.type == "identifier":
            s = self._resolve(node)
            return ([], [s] if s else [])
        if node.type in ("member_expression","array_access"):
            return self.reads(node), []
        if node.type == "tuple_expression":
            reads, writes = [], []
            for c in node.named_children:
                r,w=self.targets(c); reads += r; writes += w
            if len(writes)!=len(set(writes)):
                raise Unsupported("Repeated tuple assignment target")
            return reads,writes
        raise Unsupported("Unsupported assignment target: " + node.type)

    def event(self, anchor, reads=(), writes=(), kind="expression"):
        e=Event(self.table.function_id+":e"+str(self.counter),
                self.table.function_id,anchor,tuple(sorted(set(reads))),
                tuple(sorted(set(writes))),kind)
        self.counter += 1
        return e

    def entry(self, function):
        return self.event(span(self.table.file,function),
                          writes=[s.id for s in self.table.entry_symbols],kind="entry")

    def extract(self, node, anchor=None):
        if node is None: return []
        owner = anchor or span(self.table.file,node)
        t=node.type
        if t=="expression_statement":
            return sum((self.extract(c,owner) for c in node.named_children
                        if "comment" not in c.type), [])
        if t=="variable_declaration_statement":
            value=node.child_by_field_name("value")
            r=self.reads(value)
            w=[self.table.lookup_decl(c).id for c in walk(node)
               if c.type=="variable_declaration"]
            if value is None and self.table.mode=="legacy": w=[]
            return [self.event(owner,r,w,"declaration")]
        if t in ("assignment_expression","augmented_assignment_expression"):
            left,right=node.child_by_field_name("left"),node.child_by_field_name("right")
            r,w=self.targets(left)
            if t=="augmented_assignment_expression": r += self.reads(left)
            r += self.reads(right)
            return [self.event(owner,r,w,"assignment")]
        if t=="update_expression":
            arg=node.child_by_field_name("argument")
            r,w=self.targets(arg)
            return [self.event(owner,r+self.reads(arg),w,"update")]
        if t=="unary_expression":
            op=node.child_by_field_name("operator")
            if op and self._name(op)=="delete":
                r,w=self.targets(node.child_by_field_name("argument"))
                return [self.event(owner,r,w,"delete")]
        if t=="return_statement":
            children=[c for c in node.named_children if "comment" not in c.type]
            r=sum((self.reads(c) for c in children), [])
            if not children:
                r=[s.id for s in self.table.symbols.values() if s.kind=="return"]
            return [self.event(owner,r,kind="return")]
        if t in ("emit_statement","revert_statement"):
            r=[]
            for c in node.named_children:
                if t=="revert_statement":
                    if c.type!="identifier" and "comment" not in c.type:
                        r += self.reads(c)
                elif c.type in ("call_expression","call_argument","revert_arguments"):
                    r += self.reads(c)
            return [self.event(owner,r,kind=t)]
        return [self.event(owner,self.reads(node))]
