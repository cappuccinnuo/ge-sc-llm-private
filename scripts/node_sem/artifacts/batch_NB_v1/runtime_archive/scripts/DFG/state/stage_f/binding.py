"""Closed single-inheritance declaration evidence; no C3 or imported-name guesses."""
import re
from ...frontend import text,span
from ...models import Unsupported
from ...call_binding import CallBindingResolver,CallBinding,BUILTIN,NON_BUILTIN,UNKNOWN,CONTAINERS
from .versioning import available
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
