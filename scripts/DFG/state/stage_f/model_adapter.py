"""Stage F directional relations for candidate validation, not the old formal loader."""
from collections import OrderedDict,Counter
from . import FORWARD_RELATIONS
def reflected_input(edge_data):
 from sco_models.graph_utils import reflect_graph
 ordinary=OrderedDict((k,v) for k,v in edge_data.items() if k[1] not in FORWARD_RELATIONS)
 result=reflect_graph(ordinary)
 for k,v in edge_data.items():
  if k[1] in FORWARD_RELATIONS:
   if k in result:raise ValueError("canonical collision")
   result[k]=v
 return result
def build_dgl(graph):
 import torch,dgl
 data=OrderedDict();ids={};counts={}
 for n,d in graph.nodes(data=True):
  typ=d["node_type"];ids[n]=counts.get(typ,0);counts[typ]=ids[n]+1
 for s,t,d in graph.edges(data=True):
  k=(graph.nodes[s]["node_type"],d["edge_type"],graph.nodes[t]["node_type"]);a,b=data.setdefault(k,([],[]));a.append(ids[s]);b.append(ids[t])
 tensors=OrderedDict((k,(torch.tensor(a,dtype=torch.int64),torch.tensor(b,dtype=torch.int64))) for k,(a,b) in data.items())
 return dgl.heterograph(reflected_input(tensors),num_nodes_dict=counts),ids
def information_increment(base,new):
 def near(g):
  adj={n:set() for n in g}
  for s,t,d in g.edges(data=True):
   adj[s].add(t)
   if d["edge_type"] not in FORWARD_RELATIONS:adj[t].add(s)
  return {n:set(a).union(*(adj[x] for x in a)) for n,a in adj.items()}
 before,after=near(base),near(new);pairs={(s,t) for s in after for t in after[s]-before[s] if s!=t}
 canonical=lambda g:{(g.nodes[s]["node_type"],d["edge_type"],g.nodes[t]["node_type"]) for s,t,d in g.edges(data=True)}
 rels=canonical(new)-canonical(base)
 edges=[(s,t,d["edge_type"]) for s,t,d in new.edges(data=True) if d["edge_type"] in FORWARD_RELATIONS-{"DATA_DEF_USE"}]
 return {"new_model_edges_by_relation":dict(Counter(rel for _,_,rel in edges)),
 "new_edges_outside_E2_two_hops":sum(t not in before[s] for s,t,_ in edges),"new_two_layer_pairs":len(pairs),
 "new_context_target_nodes":len({t for _,t in pairs}),"new_canonical_relations":sorted(rels),
 "conditional_parameter_increment_h128_heads8_layers2":len(rels)*8208,
 "parameter_count_is_formula_not_full_model_measurement":True,"meaning":"topology and relation semantics, not measured accuracy"}
