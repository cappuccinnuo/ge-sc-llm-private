"""CPU synthetic compatibility only: existing HGTLayer, no optimizer or fit."""
import copy
import torch
import numpy as np
from sco_models.model_hgt import HGTLayer
from scripts.DFG.model_validation import capture_model_input,assert_model_input
from scripts.DFG.graph_audit import fingerprint
from .model_adapter import build_dgl
from .initialization import initialize_pair,INITIALIZATION_VERSION
class SyntheticHGT(torch.nn.Module):
 def __init__(self,graph,reverse_schema=False):
  super().__init__();self.nx_graph=copy.deepcopy(graph)
  self.symmetrical_global_graph,_=build_dgl(self.nx_graph);g=self.symmetrical_global_graph
  ns=list(g.ntypes);es=list(g.canonical_etypes)
  if reverse_schema:ns.reverse();es.reverse()
  self.ntypes_dict={n:i for i,n in enumerate(ns)};self.etypes_dict={e:i for i,e in enumerate(es)}
  self.node_ids_dict={n:[i for i,d in self.nx_graph.nodes(data=True) if d["node_type"]==n] for n in ns}
  self.node_feature="inside_token";self.in_size=8;self.hidden_size=8;self.out_size=8;self.num_heads=2;self.num_layers=2
  for n,ids in self.node_ids_dict.items():g.nodes[n].data["inp"]=torch.tensor(np.stack([self.nx_graph.nodes[i]["token"] for i in ids]))
  self.gcs=torch.nn.ModuleList([HGTLayer(8,8,self.ntypes_dict,self.etypes_dict,2,dropout=0,use_norm=False) for _ in range(2)])
 def forward(self):
  h={n:self.symmetrical_global_graph.nodes[n].data["inp"] for n in self.ntypes_dict}
  for layer in self.gcs:h=layer(self.symmetrical_global_graph,h)
  return h
def smoke(base,enhanced,path):
 torch.set_num_threads(1);torch.manual_seed(1)
 a=SyntheticHGT(base);b=SyntheticHGT(enhanced,True);before=fingerprint(base)
 init=initialize_pair(a,b,seed=1);external={"stage":"F4_synthetic_initial_only","initialization_version":INITIALIZATION_VERSION,"training":False,"forward_scope":"synthetic_fixture","score_role":"not_scored"}
 binding=capture_model_input(b,external);b.eval();pred=b();loss=sum(t.square().sum() for t in pred.values());loss.backward()
 grads={}
 for relation in ("STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"):
  rows=[i for e,i in b.etypes_dict.items() if e[1]==relation]
  assert rows,relation
  grads[relation]=sum(layer.relation_msg.grad[rows].abs().sum().item() for layer in b.gcs)
  assert grads[relation]>0 and np.isfinite(grads[relation])
 torch.save({"kind":"untrained_synthetic_initial","binding":binding,"external":external,"init":init,"state_dict":b.state_dict()},str(path))
 restored=SyntheticHGT(enhanced,True);record=torch.load(str(path),map_location="cpu")
 assert_model_input(restored,record["binding"],record["external"]);restored.load_state_dict(record["state_dict"]);restored.eval()
 after=restored()
 assert all(torch.equal(pred[k],after[k]) for k in pred)
 assert fingerprint(base)==before
 return {"kind":"CPU_synthetic_compatibility","optimizer_steps":0,"initialization":init,"input_binding":binding,
         "relation_message_gradient_l1":grads,"reload_predictions_exact":True,"formal_training":False,"fixture_dimensions":8}
