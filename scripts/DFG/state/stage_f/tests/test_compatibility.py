import copy
import torch
import pytest
from scripts.DFG.state.tests.test_projection import fixture
from scripts.DFG.state.stage_f.analyzer import analyze_source
from scripts.DFG.state.stage_f.projection import projected_file,materialize
from scripts.DFG.state.stage_f.compatibility import smoke,SyntheticHGT
from scripts.DFG.state.stage_f.initialization import initialize_pair
from scripts.DFG.state.stage_f.model_adapter import build_dgl,reflected_input
from scripts.DFG.model_validation import capture_model_input,assert_model_input
from scripts.DFG.experiments.protocol import paired_initialize
def graphs():
 src="pragma solidity 0.5.17;contract C{uint s;function f(address payable to) public returns(uint){s=1;to.transfer(s);s=0;return s;}}"
 base,_=fixture(src);v,rs=analyze_source(src,file="p.sol");proof,_=projected_file(base,v,rs);new,_=materialize(base,proof);return base,new
def test_all_new_relations_forward_gradient_and_bound_reload(tmp_path):
 a,b=graphs();record=smoke(a,b,tmp_path/"initial_synthetic.pt")
 assert len(record["relation_message_gradient_l1"])==3 and record["optimizer_steps"]==0
def test_no_reversal_and_baseline_matches_frozen_adapter():
 from scripts.DFG.state.model_adapter import build_dgl as before
 a,b=graphs();g,_=build_dgl(b)
 for rel in ("STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"):
  assert sum(g.num_edges(k) for k in g.canonical_etypes if k[1]==rel)==sum(d["edge_type"]==rel for _,_,d in b.edges(data=True))
 old,_=before(a);cur,_=build_dgl(a)
 assert old.canonical_etypes==cur.canonical_etypes
 for k in old.canonical_etypes:assert all(torch.equal(x,y) for x,y in zip(old.edges(etype=k),cur.edges(etype=k)))
def test_reordered_schema_has_equal_common_parameters():
 a,b=graphs();ma,mb=SyntheticHGT(a),SyntheticHGT(b,True);audit=initialize_pair(ma,mb,1)
 for layer0,layer1 in zip(ma.gcs,mb.gcs):
  for e,i in ma.etypes_dict.items():assert torch.equal(layer0.relation_msg[i],layer1.relation_msg[mb.etypes_dict[e]])
 assert audit["shared_tensor_count"]>0
def test_drift_and_unregistered_schema_rejected_before_reload():
 a,b=graphs();m=SyntheticHGT(b);capt=capture_model_input(m,{"phase":"F4"})
 with pytest.raises(ValueError):assert_model_input(m,capt,{"phase":"other"})
 n=next(iter(m.nx_graph));m.nx_graph.nodes[n]["node_info_vulnerabilities"]=[{"lines":[1]}]
 with pytest.raises(ValueError):assert_model_input(m,capt,{"phase":"F4"})
 m=SyntheticHGT(b);m.etypes_dict.pop(next(iter(m.etypes_dict)))
 with pytest.raises(ValueError):capture_model_input(m)
def test_existing_data_only_initialization_numerically_unchanged():
 a,_=graphs();unaug=copy.deepcopy(a)
 for s,t,k,d in list(unaug.edges(keys=True,data=True)):
  if d["edge_type"]=="DATA_DEF_USE":unaug.remove_edge(s,t,k)
 torch.manual_seed(7);parent=SyntheticHGT(unaug);child1=SyntheticHGT(a,True);child2=SyntheticHGT(a,True)
 paired_initialize(parent,child1,seed=1);initialize_pair(parent,child2,seed=1)
 assert all(torch.equal(v,child2.state_dict()[k]) for k,v in child1.state_dict().items())
def test_bad_new_relation_refused():
 a,b=graphs();n,m=next(iter(b.edges()));b.add_edge(n,m,edge_type="NOT_APPROVED")
 with pytest.raises(ValueError):initialize_pair(SyntheticHGT(a),SyntheticHGT(b))
