"""Stage F source view, same exact raw/compat token and AST mapping as v1.1."""
import bisect,hashlib
from ...frontend import SourceView,parse,leaves,walk,FUNCTION_TYPES
from ...models import Unsupported
from .versioning import effective_interval,mode_for
class StageFSourceView(SourceView):
 def __init__(self,source,file,metadata=None):
  from process_graphs.tree_sitter_codeviews.utils import preprocessor
  self.source,self.file=source,file;self.raw=source.encode("utf8");self.sha256=hashlib.sha256(self.raw).hexdigest()
  self.tree=parse(source);self.version_interval,self.version_evidence=effective_interval(source,self.tree.root_node,metadata)
  self.mode=mode_for(source,self.tree.root_node,self.version_interval)
  self.compat_source=preprocessor.remove_comments("solidity",preprocessor.remove_empty_lines(source))
  self.compat=self.compat_source.encode("utf8");self.compat_tree=parse(self.compat_source)
  a,b=leaves(self.tree.root_node),leaves(self.compat_tree.root_node)
  if [self.raw[n.start_byte:n.end_byte] for n in a]!=[self.compat[n.start_byte:n.end_byte] for n in b]:raise Unsupported("Preprocessing changed executable tokens")
  self.raw_nodes={(n.start_byte,n.end_byte,n.type):n for n in walk(self.tree.root_node)}
  self.compat_nodes={};self.compat_ids={}
  def ids(n):
   if n.is_named:
    k=(n.start_byte,n.end_byte,n.type);self.compat_ids[k]=5+len(self.compat_ids);self.compat_nodes[k]=n
    for c in n.children:
     if c.is_named:ids(c)
  ids(self.compat_tree.root_node);self.mapping={}
  aa=[n.start_byte for n in a];az=[n.end_byte for n in a];ba=[n.start_byte for n in b];bz=[n.end_byte for n in b];index={}
  for k,n in self.compat_nodes.items():index.setdefault((bisect.bisect_left(ba,n.start_byte),bisect.bisect_right(bz,n.end_byte),n.type),[]).append(k)
  for k,n in self.raw_nodes.items():
   matches=index.get((bisect.bisect_left(aa,n.start_byte),bisect.bisect_right(az,n.end_byte),n.type),[])
   if len(matches)==1:self.mapping[k]=matches[0]
  self.functions=[n for n in walk(self.tree.root_node) if n.type in FUNCTION_TYPES and n.child_by_field_name("body")]
