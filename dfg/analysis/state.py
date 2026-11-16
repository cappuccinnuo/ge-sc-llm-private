"""Contract-state binding: call resolution, modifier expansion and the coverage-extended CFG builder."""
import re

from dfg.analysis.access import AccessExtractor
from dfg.analysis.cfg import CFGBuilder
from dfg.analysis.frontend import available, text, walk
from dfg.analysis.ir import FunctionIR, Unsupported
from dfg.analysis.symbols import (
    BUILTIN,
    CONTAINERS,
    CallBinding,
    CallBindingResolver,
    NON_BUILTIN,
    SymbolTable,
    UNKNOWN)


# ----------------------------------------------------------------------
# state/stage_f/binding
# Closed single-inheritance declaration evidence; no C3 or imported-name guesses.
class ClosedScope:
 def __init__(self,view,function):
  self.view=view;c=function.parent
  while c is not None and c.type not in CONTAINERS:c=c.parent
  if c is None:raise Unsupported("F: callable outside contract scope")
  if any(n.type=="import_directive" for n in view.tree.root_node.named_children):raise Unsupported("F: unresolved imports")
  units={}
  for n in view.tree.root_node.named_children:
   if n.type in CONTAINERS:
    name=n.child_by_field_name("name")
    if name is not None:units.setdefault(text(view.source,name),[]).append(n)
  self.contract=c;self.chain=[];seen=set()
  while c is not None:
   if c.start_byte in seen:raise Unsupported("F: cyclic inheritance")
   seen.add(c.start_byte);self.chain.append(c)
   bases=[n for n in c.named_children if n.type=="inheritance_specifier"]
   if len(bases)>1:raise Unsupported("F: multiple inheritance outside closed subset")
   if not bases:break
   base=bases[0];ancestor=base.child_by_field_name("ancestor")
   if ancestor is None or len(base.named_children)!=1:raise Unsupported("F: base constructor arguments unsupported")
   name=text(view.source,ancestor)
   if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*",name) or len(units.get(name,[]))!=1:raise Unsupported("F: base declaration not unique in compilation unit")
   c=units[name][0]
   if c.type!="contract_declaration":raise Unsupported("F: interface/library inheritance unsupported")
  self.members={};self.hidden={};self.owner={}
  for depth,c in enumerate(self.chain):
   body=c.child_by_field_name("body")
   if body is None:raise Unsupported("F: missing ancestor body")
   for n in body.named_children:
    name=n.child_by_field_name("name")
    if name is None:continue
    name=text(view.source,name);self.owner[n.start_byte]=c
    private=any(x.type=="visibility" and text(view.source,x)=="private" for x in n.named_children)
    (self.hidden if depth and private else self.members).setdefault(name,[]).append(n)
  self.evidence={"scope":"unique same-unit single chain; lexical declaring contract","source_sha256":view.sha256,
                 "chain":[{"name":text(view.source,c.child_by_field_name("name")),"start":c.start_byte,"end":c.end_byte} for c in self.chain],
                 "import_resolution":"none present","linearization":"single chain; no multiple-base linearization inferred"}
 def declarations(self,name):return self.members.get(name,[])
 def require_unambiguous(self,name):
  ds=self.declarations(name)
  if len(ds)>1:raise Unsupported("F: ambiguous inherited/overloaded declaration: "+name)
  if not ds and name in self.hidden:raise Unsupported("F: private ancestor member is not visible: "+name)
  return ds

class StageFCallResolver(CallBindingResolver):
 def __init__(self,view,function,table,scope):
  super().__init__(view,function,table);self.scope=scope
 def _unqualified(self,name,occurrence,form):
  local=self.table.resolve(name,occurrence)
  if local:return CallBinding(UNKNOWN,name,form,"local_scalar_is_not_a_supported_callee",{"symbol":local.id})
  ds=self.scope.declarations(name)
  if not ds:ds=self._declarations(self.view.tree.root_node.named_children,name)
  evidence=dict(self.scope.evidence,version=self.view.version_evidence,declarations=[{"kind":d.type,"start":d.start_byte,"end":d.end_byte} for d in ds])
  if len(ds)>1:return CallBinding(UNKNOWN,name,form,"F: ambiguous callable declaration",evidence)
  if ds:
   d=ds[0]
   if d.type=="function_definition" and not any(x.type=="visibility" and text(self.view.source,x)=="external" for x in d.named_children):
    return CallBinding(NON_BUILTIN,name,form,"unique visible user function",evidence)
   t=d.child_by_field_name("type")
   if d.type=="state_variable_declaration" and t is not None and any(c.type=="function" for c in t.children):
    return CallBinding(NON_BUILTIN,name,form,"unique state function pointer",evidence)
   return CallBinding(UNKNOWN,name,form,"F: unsupported shadowing callee",evidence)
  if name in self.scope.hidden:return CallBinding(UNKNOWN,name,form,"F: inaccessible private callable",evidence)
  if name=="suicide" and any("experimental" in text(self.view.source,n) for n in self.view.tree.root_node.named_children if n.type=="pragma_directive"):
   return CallBinding(UNKNOWN,name,form,"experimental_mode_suicide_unverified",evidence)
  return CallBinding(BUILTIN if available(self.view,name) else UNKNOWN,name,form,
    "closed_chain_and_version_confirm_builtin" if available(self.view,name) else "builtin_not_guaranteed_over_pragma_interval",evidence)


# ----------------------------------------------------------------------
# state/stage_j/binding
# Closed same-source inheritance. C3 validates hierarchy, never guesses overrides.
def merge(sequences):
    sequences = [list(x) for x in sequences if x]
    result = []
    while sequences:
        candidate = next((s[0] for s in sequences
                          if not any(s[0] in t[1:] for t in sequences)), None)
        if candidate is None:
            raise Unsupported("J: inconsistent C3 inheritance")
        result.append(candidate)
        sequences = [s[1:] if s[0] == candidate else s for s in sequences]
        sequences = [s for s in sequences if s]
    return result

class ClosedScopeJ(ClosedScope):
    def __init__(self, view, function):
        self.view = view
        c = function.parent
        while c is not None and c.type not in CONTAINERS:
            c = c.parent
        if c is None:
            raise Unsupported("J: callable outside contract")
        if any(n.type == "import_directive" for n in view.tree.root_node.named_children):
            raise Unsupported("J: unresolved imports")
        units = {}
        for n in view.tree.root_node.named_children:
            if n.type in CONTAINERS:
                name = n.child_by_field_name("name")
                if name is not None:
                    units.setdefault(text(view.source, name), []).append(n)
        self.contract = c
        by_id, memo, active = {}, {}, set()
        def linearize(node):
            ident = node.start_byte
            by_id[ident] = node
            if ident in active:
                raise Unsupported("J: cyclic inheritance")
            if ident in memo:
                return memo[ident]
            if node.type == "library_declaration" and node is not self.contract:
                raise Unsupported("J: library is not an inheritance base")
            active.add(ident)
            bases = []
            for base in node.named_children:
                if base.type != "inheritance_specifier":
                    continue
                ancestor = base.child_by_field_name("ancestor")
                children = [x for x in base.named_children if "comment" not in x.type]
                if ancestor is None or len(children) != 1:
                    raise Unsupported("J: base constructor arguments unsupported")
                name = text(view.source, ancestor)
                if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name) or len(units.get(name, [])) != 1:
                    raise Unsupported("J: base declaration not unique in source")
                bases.append(units[name][0])
            if len({x.start_byte for x in bases}) != len(bases):
                raise Unsupported("J: duplicate direct base")
            # Solidity gives rightmost direct bases precedence.
            direct = list(reversed(bases))
            result = [ident] + merge([linearize(x) for x in direct] +
                                    [[x.start_byte for x in direct]])
            active.remove(ident)
            memo[ident] = result
            return result
        self.chain = [by_id[i] for i in linearize(c)]
        self.members, self.hidden, self.owner = {}, {}, {}
        for depth, owner in enumerate(self.chain):
            body = owner.child_by_field_name("body")
            if body is None:
                raise Unsupported("J: missing ancestor body")
            for node in body.named_children:
                if owner.type == "interface_declaration":
                    if node.type == "state_variable_declaration" or (
                        node.type == "function_definition" and node.child_by_field_name("body") is not None):
                        raise Unsupported("J: interface with executable body/storage")
                name = node.child_by_field_name("name")
                if name is None:
                    continue
                name = text(view.source, name)
                self.owner[node.start_byte] = owner
                private = any(x.type == "visibility" and text(view.source, x) == "private"
                              for x in node.named_children)
                (self.hidden if depth and private else self.members).setdefault(name, []).append(node)
        self.evidence = {
            "scope": "closed same-source hierarchy; lexical declaration identity",
            "source_sha256": view.sha256,
            "chain": [{"name": text(view.source, x.child_by_field_name("name")),
                       "kind": x.type, "start": x.start_byte, "end": x.end_byte}
                      for x in self.chain],
            "linearization": "Solidity rightmost-first C3, checked for consistency",
            "dispatch": "no override/overload selection or interprocedural summaries",
            "import_resolution": "none present",
        }


# ----------------------------------------------------------------------
# state/stage_j/modifiers
# One parameterless prefix modifier, ending in exactly one top-level _.
def children(n):
    return [c for c in n.named_children if "comment" not in c.type]

def placeholder(n, source):
    cs = children(n)
    return (n.type == "expression_statement" and len(cs) == 1
            and cs[0].type == "identifier" and text(source, cs[0]) == "_")

def prefix_modifier(view, function, scope):
    calls = [n for n in function.named_children if n.type == "modifier_invocation"]
    if not calls:
        return [], None
    if len(calls) != 1:
        raise Unsupported("J: multiple modifier invocations unsupported")
    call = calls[0]
    cs = children(call)
    if len(cs) != 1 or cs[0].type != "identifier":
        raise Unsupported("J: modifier arguments/qualified invocation unsupported")
    name = text(view.source, cs[0])
    declarations = scope.require_unambiguous(name)
    if len(declarations) != 1 or declarations[0].type != "modifier_definition":
        raise Unsupported("J: modifier binding is not a unique declaration")
    modifier = declarations[0]
    if any(n.type == "parameter" for n in modifier.named_children):
        raise Unsupported("J: modifier parameters unsupported")
    if any(n.type == "modifier_invocation" for n in modifier.named_children):
        raise Unsupported("J: nested modifier invocation unsupported")
    body = modifier.child_by_field_name("body")
    if body is None:
        raise Unsupported("J: modifier has no body")
    statements = children(body)
    holes = [n for n in walk(body) if placeholder(n, view.source)]
    if len(holes) != 1 or not statements or holes[0] != statements[-1]:
        raise Unsupported("J: requires one unconditional terminal placeholder; suffix/conditional/repeated _ unsupported")
    prefix = statements[:-1]
    for statement in prefix:
        if statement.type != "expression_statement":
            raise Unsupported("J: modifier prefix only supports straight-line expressions")
        for node in walk(statement):
            if node.type in ("variable_declaration", "return_statement", "assembly_statement"):
                raise Unsupported("J: modifier local declarations/control unsupported")
            if node.type == "call_expression":
                callee = node.child_by_field_name("function")
                name = text(view.source, callee) if callee is not None else ""
                # Only a top-level, confirmed builtin guard; nested calls are not pure.
                direct = children(statement)
                if len(direct) != 1 or direct[0] != node or callee.type != "identifier":
                    raise Unsupported("J: effectful/nested modifier call unsupported")
                global_shadow = any(n.child_by_field_name("name") is not None and
                    text(view.source, n.child_by_field_name("name")) == name
                    for n in view.tree.root_node.named_children)
                if (name not in ("require", "assert") or name in scope.members or name in scope.hidden
                        or global_shadow or not available(view, name)):
                    raise Unsupported("J: modifier guard builtin binding/version uncertain")
    return prefix, {
        "modifier_name": text(view.source, modifier.child_by_field_name("name")),
        "declaration": {"start": modifier.start_byte, "end": modifier.end_byte},
        "invocation": {"start": call.start_byte, "end": call.end_byte},
        "placeholder": {"start": holes[0].start_byte, "end": holes[0].end_byte},
        "parameter_binding": "none; arguments and parameters rejected",
        "execution": "prefix then function body; no suffix",
        "control_dependence_edges": False,
    }


# ----------------------------------------------------------------------
# state/stage_j/analyzer (picked: StageJCFGBuilder)
class StageJCFGBuilder(CFGBuilder):
    def __init__(self, view, function, enable_modifiers=True):
        self.view, self.function = view, function
        self.table = SymbolTable(view.source, view.file, function, view.mode)
        self.scope = ClosedScopeJ(view, function)
        self.access = AccessExtractor(view.source, self.table)
        self.blocks = {}
        self.call_bindings, self.binding_diagnostics = StageFCallResolver(
            view, function, self.table, self.scope).preflight()
        if not enable_modifiers and any(n.type == "modifier_invocation" for n in function.named_children):
            raise Unsupported("J: modifier recovery disabled")
        self.prefix, self.modifier_evidence = prefix_modifier(view, function, self.scope)

    def build(self):
        entry = self.new([self.access.entry(self.function)])
        tails = self.sequence(self.prefix, {entry})
        self.statement(self.function.child_by_field_name("body"), tails)
        return FunctionIR(self.table.function_id, self.view.file, entry, self.blocks, self.table.symbols)
