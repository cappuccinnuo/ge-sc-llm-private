"""Analysis-only CFG. Auxiliary blocks NEVER become HCG nodes."""
from .models import Block, FunctionIR, AnalysisResult, Unsupported
from .frontend import span, text, walk
from .symbol_table import SymbolTable
from .access_extractor import AccessExtractor
from .call_binding import CallBindingResolver, BindingUncertain, key as binding_key

def _if_bodies(node):
    """Resolve direct then/else children; extras must not become statements.

    Codex D1 repair (2026-10-13): the installed Solidity grammar can assign
    field=body to a comment between then and else (and field=else after else).
    Ignore only comments, then require an unambiguous complete branch shape.
    Do not truncate extra bodies or search descendant/textual else tokens.
    """
    bodies, conditions, alternatives = [], [], []
    for index, child in enumerate(node.children):
        if "comment" in child.type:
            continue
        field = node.field_name_for_child(index)
        if child.type == "else" and not child.is_named:
            alternatives.append(index)
        elif field == "body" and child.is_named:
            bodies.append((index, child))
        elif field == "condition" and child.is_named:
            conditions.append(index)
        elif child.is_named or child.type not in ("if", "(", ")"):
            raise Unsupported("Ambiguous if child: " + child.type)
    if len(conditions) != 1 or len(alternatives) > 1:
        raise Unsupported("Ambiguous if condition/else structure")
    expected = 2 if alternatives else 1
    if len(bodies) != expected or bodies[0][0] <= conditions[0]:
        raise Unsupported("Ambiguous if body count/order")
    if alternatives and not bodies[0][0] < alternatives[0] < bodies[1][0]:
        raise Unsupported("Ambiguous if then/else order")
    return bodies[0][1], bodies[1][1] if alternatives else None


class CFGBuilder:
    def __init__(self, view, function):
        self.view, self.function = view, function
        self.table = SymbolTable(view.source,view.file,function,view.mode)
        self.access = AccessExtractor(view.source,self.table)
        self.blocks = {}
        # B1 FIX (Codex, 2026-10-12): resolve before constructing any CFG.
        # Old name-only termination and file-wide shadow scan are in the audit snapshot.
        self.call_bindings, self.binding_diagnostics = CallBindingResolver(
            view, function, self.table).preflight()
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
            then_body, else_body = _if_bodies(n)
            head=self.new(self.access.extract(n.child_by_field_name("condition"),
                                              span(self.view.file,n)))
            self.link(incoming,head)
            tails=self.statement(then_body,{head},loop)
            tails |= self.statement(else_body,{head},loop) if else_body is not None else {head}
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
        terminates = t == "return_statement"
        children = [c for c in n.named_children if "comment" not in c.type]
        call = n if t == "revert_statement" else (
            children[0] if t == "expression_statement" and len(children) == 1 else None)
        decision = self.call_bindings.get(binding_key(call)) if call is not None else None
        if decision is not None:
            terminates = decision.terminates
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
            result.diagnostics.extend(b.binding_diagnostics)
            for d in b.access.diagnostics:
                result.diagnostics.append(dict(d,function=identity))
        except BindingUncertain as exc:
            # The builder has not committed an IR; nothing from this function reaches RD.
            result.diagnostics.append(dict(exc.diagnostic, kind="function_fallback"))
        except Unsupported as exc:
            result.diagnostics.append({"kind":"function_fallback","function":identity,
                                       "reason":str(exc)})
    return result
