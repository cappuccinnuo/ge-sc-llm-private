"""Explicit Stage F adapters; no monkeypatching of frozen scalar or Stage E modules."""
from ...frontend import span,text
from ...models import Unsupported
from ...symbol_table import SymbolTable
from ...access_extractor import AccessExtractor
from ...semantic_cfg import CFGBuilder
from ..access import StateExtractor
from ..locations import LocationTable,scalar_type
from ..models import DeclarationRef,StateAnalysisResult
from ..reaching_definitions import solve
from .binding import ClosedScope,StageFCallResolver
from .versioning import available
from .frontend import StageFSourceView
class StageFCFGBuilder(CFGBuilder):
 def __init__(self,view,function):
  self.view,self.function=view,function
  self.table=SymbolTable(view.source,view.file,function,view.mode)
  self.scope=ClosedScope(view,function)
  self.access=AccessExtractor(view.source,self.table);self.blocks={}
  self.call_bindings,self.binding_diagnostics=StageFCallResolver(view,function,self.table,self.scope).preflight()
  if any(c.type=="modifier_invocation" for c in function.named_children):raise Unsupported("Modifier execution is outside phase-one scope")
class StageFLocationTable(LocationTable):
 def __init__(self,view,function,table,ir,scope):
  self.view,self.function,self.table,self.ir=view,function,table,ir;self.scope=scope;self.contract=scope.contract
  self.members=scope.members;self.roots={};self.locations={};self.written_locals={s for b in ir.blocks.values() for e in b.events if e.kind!="entry" for s in e.writes}
  for name,nodes in scope.members.items():
   for n in nodes:
    if n.type!="state_variable_declaration":continue
    if len(nodes)!=1:raise Unsupported("F: state declaration conflicts with inherited/member name: "+name)
    typ=n.child_by_field_name("type");raw=text(view.source,typ) if typ else "";kind="unsupported";keytype=""
    if scalar_type(raw):kind="scalar"
    elif typ and any(x.type=="mapping" for x in typ.children):
     kt,vt=typ.child_by_field_name("key_type"),typ.child_by_field_name("value_type")
     keytype=scalar_type(text(view.source,kt)) if kt else None
     if keytype and vt and scalar_type(text(view.source,vt)):kind="mapping"
    if any(text(view.source,x) in ("constant","immutable") for x in n.children):kind="unsupported"
    c=scope.owner[n.start_byte];identity="{}:{}:{}:{}".format(view.sha256,view.file,c.start_byte,n.start_byte)
    self.roots[name]=DeclarationRef(identity,view.sha256,view.file,span(view.file,c),span(view.file,n),name,raw,kind,keytype or "")
 def bare_root(self,node):
  if node.type=="identifier" and self.table.resolve(text(self.view.source,node),node) is None:
   self.scope.require_unambiguous(text(self.view.source,node))
  return super().bare_root(node)
 def builtin(self,name,node):
  if name in self.scope.hidden:return False
  return super().builtin(name,node)
 def _intern(self,root,kind,value,typ,certainty,evidence):
  return super()._intern(root,kind,value,typ,certainty,list(evidence)+["closed unique declaration chain; root span="+str(root.declaration.start)])
class StageFExtractor(StateExtractor):
 def __init__(self,view,function,builder,ir):
  self.view,self.function,self.builder,self.ir=view,function,builder,ir
  self.table=StageFLocationTable(view,function,builder.table,ir,builder.scope)
  self.current=None;self.block=None;self.seq=0
 def extract(self,n):
  events=super().extract(n)
  if n is not None and n.type=="revert_statement":
   from ...call_binding import key as binding_key,NON_BUILTIN
   binding=self.builder.call_bindings.get(binding_key(n))
   if binding is None:raise Unsupported("F: revert statement missing binding evidence")
   if binding.classification==NON_BUILTIN:
    events.append(self.event("HAVOC",n,detail="UNKNOWN_CALL:revert:all_state_top"))
  return events
 def call(self,n):
  fn,args=self.call_parts(n)
  if fn.type=="identifier":
   name=text(self.view.source,fn)
   if name in ("require","assert") and self.table.builtin(name,fn) and available(self.view,name):
    return self.merge_unordered([self.expr(a) for a in args])
   from ...call_binding import key as binding_key
   terminal=self.builder.call_bindings.get(binding_key(n))
   if terminal and terminal.terminates:return self.merge_unordered([self.expr(a) for a in args])
   groups=[self.expr(a) for a in args]
   if self.table.bare_root(fn) is not None:groups.append(self.expr(fn))
   return self.merge_unordered(groups)+[self.event("HAVOC",n,detail="UNKNOWN_CALL:"+name+":all_state_top")]
  events=super().call(n)
  # Stage E does not version-gate address operations; Stage F records uncertain availability as opaque.
  for i,e in enumerate(events):
   if e.kind=="HAVOC" and e.detail.startswith("EXTERNAL_CALL:"):
    method=e.detail.split(":")[1]
    if not available(self.view,method):
     from dataclasses import replace
     events[i]=replace(e,detail="UNKNOWN_CALL_VERSION:"+method+":all_state_top")
  return events
def analyze_view(view,selected_functions=None,max_iterations=100000):
 out=[];selected=set(selected_functions) if selected_functions is not None else None
 for fn in view.functions:
  fid="{}:{}".format(view.file,fn.start_byte)
  if selected is not None and fid not in selected:continue
  try:
   b=StageFCFGBuilder(view,fn);base=b.build();ir=StageFExtractor(view,fn,b,base).build();result=solve(ir,max_iterations)
   result.binding_evidence={"scope":b.scope.evidence,"calls":b.binding_diagnostics,"version":view.version_evidence}
   out.append(result)
  except Unsupported as e:out.append(StateAnalysisResult(fid,"function_fallback",diagnostics=[{"file":view.file,"start":fn.start_byte,"end":fn.end_byte,"line":fn.start_point[0]+1,"reason":str(e),"partial_state_facts_published":False}]))
 if selected is not None and selected!={r.function for r in out}:raise ValueError("Selected function missing")
 return out
def analyze_source(source,file="example.sol",metadata=None):
 view=StageFSourceView(source,file,metadata);return view,analyze_view(view)
