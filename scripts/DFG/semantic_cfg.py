"""Analysis-only CFG. Auxiliary blocks NEVER become HCG nodes."""
from .models import Block, FunctionIR, AnalysisResult, Unsupported
from .frontend import span, text, walk
from .symbol_table import SymbolTable
from .access_extractor import AccessExtractor

class CFGBuilder:
    def __init__(self, view, function):
        self.view, self.function = view, function
        self.table = SymbolTable(view.source,view.file,function,view.mode)
        self.access = AccessExtractor(view.source,self.table)
        self.blocks = {}
        terminals={"revert","selfdestruct","suicide"}
        shadowed={text(view.source,n.child_by_field_name("name")) for n in view.functions
                  if n.child_by_field_name("name") is not None} & terminals
        ambiguous=bool(shadowed) or any(n.type=="import_directive"
                      for n in view.tree.root_node.named_children)
        parent=function.parent
        while parent is not None:
            if parent.type=="contract_declaration" and any(c.type=="is" for c in parent.children):
                ambiguous=True
            parent=parent.parent
        if ambiguous:
            for node in walk(function):
                fn=node.child_by_field_name("function") if node.type=="call_expression" else None
                if node.type=="revert_statement" or (fn is not None and fn.type=="identifier"
                        and text(view.source,fn) in terminals):
                    raise Unsupported("Terminating builtin may be shadowed/imported/inherited")
        if any(c.type=="modifier_invocation" for c in function.named_children):
            raise Unsupported("Modifier execution is outside phase-one scope")

    def new(self, events=()):
        key=self.table.function_id+":b"+str(len(self.blocks))
        self.blocks[key]=Block(key,list(events))
        return key

    def link(self, tails, head):
        for t in tails: self.blocks[t].successors.add(head)

    def sequence(self, nodes, incoming, loop=None):
        tails=set(incoming)
        for node in nodes:
            if "comment" not in node.type:
                tails=self.statement(node,tails,loop)
        return tails

    def statement(self, n, incoming, loop=None):
        t=n.type
        if t in ("function_body","block_statement"):
            return self.sequence(n.named_children,incoming,loop)
        if t=="if_statement":
            head=self.new(self.access.extract(n.child_by_field_name("condition"),
                                              span(self.view.file,n)))
            self.link(incoming,head)
            bodies=[c for i,c in enumerate(n.children)
                    if n.field_name_for_child(i)=="body"]
            if not bodies: raise Unsupported("If without a body")
            tails=self.statement(bodies[0],{head},loop)
            tails |= self.statement(bodies[1],{head},loop) if len(bodies)>1 else {head}
            return tails
        if t in ("while_statement","for_statement","do_while_statement"):
            owner=span(self.view.file,n)
            initial=n.child_by_field_name("initial") if t=="for_statement" else None
            tails=set(incoming)
            if initial:
                init=self.new(self.access.extract(initial,owner))
                self.link(tails,init); tails={init}
            cond_node=n.child_by_field_name("condition")
            # A condition must not flatten nested writes / short-circuit effects.
            condition_expr=cond_node
            if cond_node is not None and cond_node.type=="expression_statement":
                children=[c for c in cond_node.named_children if "comment" not in c.type]
                if len(children)!=1: raise Unsupported("Ambiguous loop condition")
                condition_expr=children[0]
            cond=self.new([self.access.event(owner,self.access.reads(condition_expr),
                                            kind="condition")])
            after=self.new()
            update=n.child_by_field_name("update") if t=="for_statement" else None
            update_id=self.new(self.access.extract(update)) if update else cond
            if update: self.link({update_id},cond)
            body=n.child_by_field_name("body")
            if body is None: raise Unsupported("Loop without a body")
            start=self.new()
            self.link({cond},start)
            # Missing for-condition is true, so no fictitious loop-exit path.
            if cond_node is not None: self.link({cond},after)
            self.link(tails,start if t=="do_while_statement" else cond)
            body_tails=self.statement(body,{start},(after,update_id))
            self.link(body_tails,update_id)
            return {after}
        if t in ("break_statement","continue_statement"):
            if loop is None: raise Unsupported("Loop control outside a loop")
            b=self.new(); self.link(incoming,b)
            self.link({b},loop[0 if t=="break_statement" else 1])
            return set()
        if t in ("assembly_statement","try_statement"):
            raise Unsupported("Unsupported control flow: "+t)
        spelling=text(self.view.source,n).strip()
        semantic_children=[c for c in n.named_children if "comment" not in c.type]
        if (t=="expression_statement" and len(semantic_children)==1
                and semantic_children[0].type=="identifier"
                and text(self.view.source,semantic_children[0])=="throw"):
            b=self.new(); self.link(incoming,b)
            return set()
        if t not in ("variable_declaration_statement","expression_statement",
                     "return_statement","emit_statement","revert_statement"):
            raise Unsupported("Unsupported statement: "+t)
        b=self.new(self.access.extract(n))
        self.link(incoming,b)
        terminates=t in ("return_statement","revert_statement")
        children=[c for c in n.named_children if "comment" not in c.type]
        if t=="expression_statement" and len(children)==1:
            expr=children[0]
            if expr.type=="call_expression":
                fn=expr.child_by_field_name("function")
                if fn and fn.type=="identifier" and text(self.view.source,fn) in (
                        "revert","selfdestruct","suicide"):
                    terminates=True
        return set() if terminates else {b}

    def build(self):
        entry=self.new([self.access.entry(self.function)])
        self.statement(self.function.child_by_field_name("body"),{entry})
        return FunctionIR(self.table.function_id,self.view.file,entry,
                          self.blocks,self.table.symbols)

def analyze(view):
    result=AnalysisResult()
    for fn in view.functions:
        identity="{}:{}".format(view.file,fn.start_byte)
        try:
            b=CFGBuilder(view,fn)
            result.functions.append(b.build())
            for d in b.access.diagnostics:
                result.diagnostics.append(dict(d,function=identity))
        except Unsupported as exc:
            result.diagnostics.append({"kind":"function_fallback","function":identity,
                                       "reason":str(exc)})
    return result
