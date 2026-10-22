"""CPU synthetic mechanism tests, not model training or Solidity verification."""
import copy
from collections import Counter
import numpy as np
import networkx as nx
import pytest
import torch
from scripts.DFG.experiments.guard_extension import model as guard
from scripts.DFG.experiments.integration_diagnostics import message_probe as probe
from scripts.DFG.experiments.common import tensor_digest, sha256
from scripts.DFG.graph_audit import fingerprint

@pytest.fixture(autouse=True)
def cpu_threads():
    old=torch.get_num_threads();torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def graphs():
    a=nx.MultiDiGraph();rng=np.random.RandomState(44)
    for idx in range(4):
        a.add_node(idx,source_file="train.sol" if idx<2 else "val.sol",node_type="S",
                   token=rng.normal(size=512).astype(np.float32),node_info_vulnerabilities=None,
                   node_source_code_lines=[idx+1],label="synthetic")
    a.add_edge(0,1,edge_type="next");a.add_edge(2,3,edge_type="next")
    c=copy.deepcopy(a);c.add_edge(2,3,edge_type="DATA_DEF_USE")
    c.add_edge(2,3,edge_type="CONTROL_DEPENDENCE")
    return a,c


def models():
    a,c=graphs();torch.manual_seed(19)
    ma=guard.make_model("node",a,hidden_size=8,layers=2,heads=2)
    mc=guard.make_model("node",c,hidden_size=8,layers=2,heads=2)
    guard._initialize(ma,mc,seed=51)
    mb=guard.make_model("node",c,hidden_size=8,layers=2,heads=2)
    mb.load_state_dict(mc.state_dict());probe.silence_added_messages(mb)
    return ma,mb,mc


def test_original_hgt_first_layer_denominator_includes_val_only_relation():
    a,b,c=models()
    probe.verify_common(guard.semantic_state(a),guard.semantic_state(c))
    pa,pb=probe.capture_forward(a,"node"),probe.capture_forward(b,"node")
    ta,tc=probe.topology(a),probe.topology(c)
    rows=[dict(d,original_graph_node_id=n) for n,d in a.nx_graph.nodes(data=True)]
    scaling=probe.first_layer_scaling(pa,pb,rows,ta,tc)
    assert scaling["verified"] and len(set(scaling["ratios"]))==1
    assert scaling["ratios"][0]==pytest.approx(1./3.)
    assert set(tc["added_target_nodes"])=={3}
    assert not np.array_equal(pa["aggregate_0"][1],pb["aggregate_0"][1])
    assert np.allclose(pb["aggregate_0"][1],pa["aggregate_0"][1]/3.,atol=1e-6)


def test_silence_only_changes_new_message_slices_not_schema_or_old_parameters():
    a,b,c=models();before=fingerprint(c.nx_graph)
    state_before={k:v.clone() for k,v in c.state_dict().items()}
    probe.silence_added_messages(c)
    for name,value in c.state_dict().items():
        if name.endswith("relation_msg"):
            for canon,idx in c.etypes_dict.items():
                if canon[1] in guard.FORWARD_RELATIONS:assert torch.equal(value[idx],torch.zeros_like(value[idx]))
                else:assert torch.equal(value[idx],state_before[name][idx])
        else:assert torch.equal(value,state_before[name])
    assert fingerprint(c.nx_graph)==before and b.etypes_dict==c.etypes_dict


def test_forward_capture_keeps_input_weights_and_gradients_untouched():
    a,b,c=models();before=tensor_digest(c.state_dict());graph=fingerprint(c.nx_graph)
    direct=c.eval()()
    observed=probe.capture_forward(c,"node")
    assert np.array_equal(direct.detach().numpy(),observed["logits"])
    assert before==tensor_digest(c.state_dict()) and graph==fingerprint(c.nx_graph)
    assert all(p.grad is None for p in c.parameters())


def test_node_summary_separates_no_new_edge_scaling_and_new_message():
    a,b,c=models();data={k:probe.capture_forward(m,"node") for k,m in zip("ABC",(a,b,c))}
    ta,tc=probe.topology(a),probe.topology(c)
    rows=[dict(d,original_graph_node_id=n) for n,d in a.nx_graph.nodes(data=True)]
    scaling=probe.first_layer_scaling(data["A"],data["B"],rows,ta,tc)
    nodes,groups=probe.summarize_nodes(rows,data,ta,tc,scaling["ratios"],{"train_files":["train.sol"]})
    assert len(nodes)==4 and len(groups)==2
    assert nodes[1]["no_new_incoming_denominator_changed"]
    assert not nodes[3]["no_new_incoming_denominator_changed"]
    assert nodes[3]["has_new_incoming"]
    assert nodes[1]["C_minus_B_aggregate0_l2"]==0
    assert nodes[3]["C_minus_B_aggregate0_l2"]>0


def test_common_initial_mismatch_and_wrong_scaling_rejected():
    a,b,c=models();aa=guard.semantic_state(a);cc={k:v.clone() for k,v in guard.semantic_state(c).items()}
    cc["classify.bias"][0]+=1
    with pytest.raises(ValueError):probe.verify_common(aa,cc)
    pa,pb=probe.capture_forward(a,"node"),probe.capture_forward(b,"node")
    pb["aggregate_0"]=pb["aggregate_0"]+1
    with pytest.raises(AssertionError):
        probe.first_layer_scaling(pa,pb,[d for _,d in a.nx_graph.nodes(data=True)],probe.topology(a),probe.topology(c))


def test_trained_initial_refused_even_with_valid_file_digest(tmp_path):
    a,_,_=models();state=a.state_dict();path=tmp_path/"initial.pt"
    record=dict(kind="untrained_initial",optimizer_steps=1,task_id="t",fold=0,variant="HCG",fit_seed=1,
                graph_sha256="x",state_dict=state,state_sha256=tensor_digest(state))
    torch.save(record,str(path))
    info=dict(task_id="t",fit_seed=1,graphs={"HCG":{"sha256":"x"}},
              initialization={"HCG":{"path":str(path),"sha256":sha256(path),"state_sha256":tensor_digest(state)}})
    with pytest.raises(ValueError):probe.load_initial(info,"HCG",{})


def test_isolated_type_without_any_incoming_relation_is_not_denominator_change():
    a={"aggregate_0":np.zeros((1,2),dtype=np.float32)}
    result=probe.first_layer_scaling(a,a,[{"node_type":"isolated"}],{"incoming_canonical":{}},{"incoming_canonical":{}})
    assert result["ratios"]==[1.0]
