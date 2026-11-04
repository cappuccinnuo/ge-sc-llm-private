"""State events on existing scalar CFG events; uncertain order falls back the function."""
from ..frontend import span, text, walk, solidity_version_interval
from ..models import Unsupported
from ..access_extractor import LITERALS, PURE_WRAPPERS, WRITE_TYPES
from ..call_binding import key as binding_key
from .models import StateEvent, StateFunctionIR
from .locations import LocationTable

ENV = {"msg":{"sender","value","data","sig"}, "tx":{"origin","gasprice"},
       "block":{"timestamp","number","coinbase","difficulty","gaslimit","basefee","chainid","prevrandao"}}

class StateExtractor:
    def __init__(self,view,function,builder,ir):
        self.view,self.function,self.builder,self.ir=view,function,builder,ir
        self.table=LocationTable(view,function,builder.table,ir)
        self.current=None
        self.block=None
        self.seq=0

    def event(self,kind,node,location=None,detail=""):
        e=StateEvent(self.current.id+":state:"+str(self.seq),self.ir.id,self.block,
                     self.current.id,self.current.anchor,span(self.view.file,node),kind,location,detail)
        self.seq+=1
        return e

    def merge_unordered(self,groups):
        # Solidity does not guarantee a general operand/argument evaluation order.
        effect=[g for g in groups if any(e.kind=="HAVOC" for e in g)]
        if effect and (len(effect)>1 or any(g is not effect[0] and any(e.kind in ("READ","WRITE","HAVOC") for e in g) for g in groups)):
            raise Unsupported("state: effectful operand order requires a separate expression CFG")
        return [e for g in groups for e in g]

    def call_parts(self,n):
        fn=n.child_by_field_name("function")
        args=[c for c in n.named_children if c.type in ("call_argument","call_struct_argument")]
        # Legacy .value(v).gas(g)(data) configurations are not separate external calls.
        while fn is not None and fn.type=="call_expression":
            opt=fn.child_by_field_name("function")
            prop=opt.child_by_field_name("property") if opt and opt.type=="member_expression" else None
            if prop is None or text(self.view.source,prop) not in ("value","gas"):
                raise Unsupported("state: computed callee unsupported")
            args.extend(c for c in fn.named_children if c.type in ("call_argument","call_struct_argument"))
            fn=opt.child_by_field_name("object")
        if fn is None:raise Unsupported("state: absent callee")
        return fn,args

    def call(self,n):
        fn,args=self.call_parts(n)
        groups=[self.expr(a) for a in args]
        terminal=self.builder.call_bindings.get(binding_key(n))
        if terminal and terminal.terminates:
            return self.merge_unordered(groups)
        if fn.type=="identifier":
            name=text(self.view.source,fn)
            interval=solidity_version_interval(self.view.source,self.view.tree.root_node)
            if name in ("require","assert") and self.table.builtin(name,fn) and interval and (0,4,10)<=interval[0] and interval[1]<=(0,9,0):
                return self.merge_unordered(groups)
            # Unknown/user calls are opaque effects, never assumed pure by name.
            if self.table.bare_root(fn) is not None:
                groups.append(self.expr(fn))
            events=self.merge_unordered(groups)
            events.append(self.event("HAVOC",n,detail="UNKNOWN_CALL:"+name+":all_state_top"))
            return events
        if fn.type=="member_expression":
            receiver,prop=fn.child_by_field_name("object"),fn.child_by_field_name("property")
            method=text(self.view.source,prop) if prop else ""
            # Standalone to.call.value(amount); only configures a function value.
            if method in ("value","gas") and receiver is not None and receiver.type=="member_expression":
                recv=receiver.child_by_field_name("object")
                op=receiver.child_by_field_name("property")
                if op and text(self.view.source,op) in ("call","callcode","delegatecall") and self.table.address_receiver(recv):
                    groups.append(self.expr(recv))
                    return self.merge_unordered(groups)+[self.event("CALL_CONFIGURATION",n,detail="no_invocation")]
            if method in ("delegatecall","callcode"):
                raise Unsupported("state: delegatecall/callcode effect unsupported")
            if method in ("call","send","transfer","staticcall") and self.table.address_receiver(receiver):
                groups.append(self.expr(receiver))
                events=self.merge_unordered(groups)
                # staticcall is conservatively TOP too, not a claim it can write state.
                return events+[self.event("HAVOC",n,detail="EXTERNAL_CALL:"+method+":conservative_all_state_top")]
            # Unresolved member calls may be library/internal/external, not automatically external.
            groups.append(self.expr(receiver))
            return self.merge_unordered(groups)+[self.event("HAVOC",n,detail="UNKNOWN_MEMBER_CALL:"+method+":all_state_top")]
        raise Unsupported("state: unsupported computed callee")

    def expr(self,n):
        if n is None:return []
        t=n.type
        if "comment" in t or t in LITERALS:return []
        if t in WRITE_TYPES:raise Unsupported("state: nested write needs expression sequencing")
        if t=="identifier":
            loc=self.table.location(n)
            return [self.event("READ",n,loc)] if loc else []
        if t=="array_access":
            loc=self.table.location(n)
            index=n.child_by_field_name("index")
            key_events=self.expr(index)
            if any(e.kind=="HAVOC" for e in key_events):raise Unsupported("state: effectful key unsupported")
            return key_events+[self.event("READ",n,loc)]
        if t=="member_expression":
            obj,prop=n.child_by_field_name("object"),n.child_by_field_name("property")
            if obj is not None and prop is not None and obj.type=="identifier":
                base,name=text(self.view.source,obj),text(self.view.source,prop)
                if base in ENV and name in ENV[base]:
                    if not self.table.builtin(base,obj):raise Unsupported("state: environment namespace shadowed")
                    return [self.event("ENVIRONMENT",n,detail=base+"."+name)]
                if self.table.bare_root(obj):raise Unsupported("state: unsupported storage member")
            if prop is not None and text(self.view.source,prop)=="balance" and self.table.address_receiver(obj):
                return self.expr(obj)+[self.event("ENVIRONMENT",n,detail="address.balance")]
            raise Unsupported("state: unresolved member value")
        if t=="call_expression":return self.call(n)
        if t=="call_struct_argument":return self.expr(n.child_by_field_name("value"))
        if t=="type_cast_expression":
            return self.merge_unordered([self.expr(c) for c in n.named_children if c.type not in ("primitive_type","type_name")])
        if t=="unary_expression":
            op=n.child_by_field_name("operator")
            if op is not None and text(self.view.source,op)=="delete":raise Unsupported("state: nested delete")
            return self.expr(n.child_by_field_name("argument"))
        if t in PURE_WRAPPERS:
            groups=[self.expr(c) for c in n.named_children]
            if t=="ternary_expression" or (t=="binary_expression" and any(c.type in ("&&","||") for c in n.children)):
                if any(e.kind=="HAVOC" for g in groups for e in g):
                    raise Unsupported("state: conditional call requires expression CFG")
            return self.merge_unordered(groups)
        raise Unsupported("state: unsupported expression "+t)

    def target(self,n):
        if n.type=="identifier":return self.table.location(n),[]
        if n.type=="array_access":
            loc=self.table.location(n)
            key_events=self.expr(n.child_by_field_name("index"))
            if any(e.kind=="HAVOC" for e in key_events):raise Unsupported("state: effectful target key")
            return loc,key_events
        raise Unsupported("state: complex assignment target")

    def extract(self,n):
        if n is None:return []
        t=n.type
        if t=="expression_statement":
            children=[c for c in n.named_children if "comment" not in c.type]
            return [e for c in children for e in self.extract(c)]
        if t=="variable_declaration_statement":
            return self.expr(n.child_by_field_name("value"))
        if t in ("assignment_expression","augmented_assignment_expression"):
            left,right=n.child_by_field_name("left"),n.child_by_field_name("right")
            if left.type=="tuple_expression":
                if any(self.table.bare_root(c) for c in walk(left) if c.type=="identifier"):
                    raise Unsupported("state: tuple storage assignment")
                return self.expr(right)
            loc,keys=self.target(left)
            rhs=self.expr(right)
            if keys and any(e.kind=="HAVOC" for e in rhs):raise Unsupported("state: call/key evaluation order")
            if t=="augmented_assignment_expression" and loc:
                if any(e.kind=="HAVOC" for e in rhs):raise Unsupported("state: compound read/call order")
                keys += [self.event("READ",left,loc,"READ_MODIFY_WRITE")]
            return keys+rhs+([self.event("WRITE",left,loc,"READ_MODIFY_WRITE" if t=="augmented_assignment_expression" else "assignment")] if loc else [])
        if t=="update_expression":
            arg=n.child_by_field_name("argument");loc,keys=self.target(arg)
            return keys+([self.event("READ",arg,loc,"READ_MODIFY_WRITE"),self.event("WRITE",arg,loc,"READ_MODIFY_WRITE")] if loc else [])
        if t=="unary_expression" and n.child_by_field_name("operator") is not None and text(self.view.source,n.child_by_field_name("operator"))=="delete":
            loc,keys=self.target(n.child_by_field_name("argument"))
            return keys+([self.event("WRITE",n,loc,"delete")] if loc else [])
        if t=="return_statement":
            return self.merge_unordered([self.expr(c) for c in n.named_children if "comment" not in c.type])
        if t=="emit_statement":
            # Event invocation does not execute arbitrary contract code.
            return self.merge_unordered([self.expr(c) for c in n.named_children if c.type=="call_argument"])
        if t=="revert_statement":
            return self.merge_unordered([self.expr(c) for c in n.named_children if c.type!="identifier" and "comment" not in c.type])
        return self.expr(n)

    def expression_for(self,e):
        key=(e.anchor.start,e.anchor.end,e.anchor.role)
        n=self.view.raw_nodes.get(key)
        if n is None:raise Unsupported("state: stale scalar event AST anchor")
        if n.type=="if_statement":return n.child_by_field_name("condition")
        if n.type in ("while_statement","for_statement","do_while_statement"):
            if e.kind=="condition":
                c=n.child_by_field_name("condition")
                if c is not None and c.type=="expression_statement":
                    cs=[x for x in c.named_children if "comment" not in x.type]
                    if len(cs)!=1:raise Unsupported("state: ambiguous loop condition")
                    return cs[0]
                return c
            initial=n.child_by_field_name("initial")
            if initial is None:raise Unsupported("state: cannot associate loop event")
            return initial
        return n

    def build(self):
        events={}
        for bid,b in self.ir.blocks.items():
            events[bid]=[]
            for e in b.events:
                if e.function!=self.ir.id:raise Unsupported("state: event identity mismatch")
                if e.kind=="entry":continue
                self.current,self.block,self.seq=e,bid,0
                events[bid].extend(self.extract(self.expression_for(e)))
        return StateFunctionIR(self.ir,events,self.table.locations,
                               {r.id:r for r in self.table.roots.values()})
