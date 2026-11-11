"""EP1 direction, collision and semantic parameter-copy contracts."""
import copy
import math
import dgl
import pytest
import torch
from scripts.DFG.dfg_v2.model_input import materialize as frozen
from scripts.DFG.dfg_v2.hgt_layer import HGTLayerSharedProjection
from scripts.edge_sem import PROFILES, RELATION_FAMILY, validate_profile
from scripts.edge_sem.materialize import materialize, parameter_key_map
from scripts.edge_sem.init import copy_typed_layer_parameters, relation_seed


@pytest.fixture
def data(monkeypatch):
    # The prompt's synthetic 'a' has no production meaning; register only here.
    monkeypatch.setitem(RELATION_FAMILY,"a","call")
    return {
        ("X","next_line","X"):(torch.tensor([0,1,2]),torch.tensor([1,2,0])),
        ("X","a","Y"):(torch.tensor([0,1]),torch.tensor([0,1])),
        ("Y","a","X"):(torch.tensor([1]),torch.tensor([2])),
        ("X","DATA_DEF_USE","X"):(torch.tensor([0]),torch.tensor([2])),
    }


def equal_data(a,b):
    assert list(a)==list(b)
    assert all(torch.equal(x,y) for c in a for x,y in zip(a[c],b[c]))


def layer(data):
    g=dgl.heterograph(data,num_nodes_dict={"X":3,"Y":2})
    return HGTLayerSharedProjection(8,8,{t:i for i,t in enumerate(g.ntypes)},
        {c:i for i,c in enumerate(g.canonical_etypes)},2,use_norm=True)


def test_merge_exact_order_endpoints_and_input_unchanged(data):
    before=copy.deepcopy(data)
    result,meta=materialize(data,"G3R")
    equal_data(result,frozen(data,"G3R"))
    equal_data(data,before)
    assert parameter_key_map(meta)=={c:c for c in result}
    assert all(meta[c]["reverse"]==c[1].startswith("REV_") for c in meta)


def test_typed_endpoints_do_not_merge_opposite_directions(data):
    result,meta=materialize(data,"G3R-T")
    assert len(result)==2*len(data)
    for c,ends in data.items():
        rev=(c[2],"REV_"+c[1],c[0])
        assert all(torch.equal(x,y) for x,y in zip(result[c],ends))
        assert all(torch.equal(x,y) for x,y in zip(result[rev],ends[::-1]))
        assert meta[rev]["reverse"]
    keys=parameter_key_map(meta)
    assert keys[("Y","REV_a","X")]==("Y","a","X")
    assert keys[("X","REV_a","Y")]==("X","a","Y")
    assert keys[("X","REV_next_line","X")]==("X","next_line","X")
    assert keys[("X","REV_DATA_DEF_USE","X")]==("X","REV_DATA_DEF_USE","X")


def test_new_relations_are_explicit_and_source_free(data):
    data[("X","GUARDS","Y")]=(torch.tensor([2]),torch.tensor([0]))
    result,meta=materialize(data,"G4R")
    assert torch.equal(result[("Y","REV_GUARDS","X")][1],torch.tensor([2]))
    assert meta[("X","GUARDS","Y")]["family"]=="guard"
    assert ("X","GUARDS","Y") not in parameter_key_map(meta)
    with pytest.raises(ValueError,match="not allowed"):
        materialize(data,"G3R-T")


@pytest.mark.parametrize("relation",["REV_next_line","REV_GUARDS","REV_DATA_DEF_USE"])
def test_input_reverse_collision_rejected(data,relation):
    data[("X",relation,"Y")]=(torch.tensor([0]),torch.tensor([0]))
    with pytest.raises(ValueError,match="collision"):
        materialize(data,"G4R")


def test_repeated_input_groups_preserve_order_and_new_collision_rejected():
    class Items:
        def __init__(self,relation):self.relation=relation
        def items(self):
            c=("X",self.relation,"X")
            return [(c,(torch.tensor([0]),torch.tensor([1]))),
                    (c,(torch.tensor([2]),torch.tensor([0])))]
    result,_=materialize(Items("next_line"),"G3R-T")
    assert result[("X","next_line","X")][0].tolist()==[0,2]
    assert result[("X","REV_next_line","X")][0].tolist()==[1,0]
    with pytest.raises(ValueError,match="collision"):
        materialize(Items("GUARDS"),"G4R")


@pytest.mark.parametrize("pair",[
    (torch.tensor([-1]),torch.tensor([0])),
    (torch.tensor([0.]),torch.tensor([0.])),
    (torch.tensor([0,1]),torch.tensor([0])),
])
def test_invalid_endpoints(pair):
    with pytest.raises(ValueError):
        materialize({("X","next_line","X"):pair},"G3R-T")


def test_empty_relation_and_unknown_family():
    empty=torch.empty(0,dtype=torch.long)
    data={("X","next_line","Y"):(empty,empty)}
    result,_=materialize(data,"G3R-T")
    assert len(result)==2 and sum(len(v[0]) for v in result.values())==0
    with pytest.raises(ValueError,match="Unregistered"):
        materialize({("X","unregistered","Y"):(empty,empty)},"G3R-T")


def test_profile_registry_and_future_layer_guard(monkeypatch):
    assert set(PROFILES)=={"G3R","G3R-T","G4R","G4R-P","G4R-A","G4R-Api","G4R-AC","G3R-TA"}
    assert all(not validate_profile(p)["cf_back"] for p in PROFILES)
    assert RELATION_FAMILY["recursive_method_call"]=="structure"
    assert RELATION_FAMILY["MOD_APPLY"]=="call"
    with pytest.raises(ValueError,match="EdgeAware"):
        validate_profile("G4R-A",HGTLayerSharedProjection)
    bad=dict(PROFILES["G4R"],direction_mode="merge")
    monkeypatch.setitem(PROFILES,"G4R",bad)
    with pytest.raises(ValueError,match="typed"):validate_profile("G4R")


def test_canonical_copy_new_row_seed_bound_and_rng(data):
    anchor=layer(frozen(data,"G3R"))
    augmented=dict(data)
    augmented[("X","GUARDS","Y")]=(torch.tensor([1]),torch.tensor([0]))
    typed,meta=materialize(augmented,"G4R")
    first,second=layer(typed),layer(typed)
    source={k:v.clone() for k,v in anchor.state_dict().items()}
    rng=torch.get_rng_state().clone()
    report=copy_typed_layer_parameters(anchor,first,parameter_key_map(meta))
    copy_typed_layer_parameters(anchor,second,parameter_key_map(meta))
    assert torch.equal(rng,torch.get_rng_state())
    assert all(torch.equal(source[k],v) for k,v in anchor.state_dict().items())
    assert all(torch.equal(v,second.state_dict()[k]) for k,v in first.state_dict().items())
    expected=math.sqrt(6.0/((2+len(anchor.edge_dict))*16))
    assert report["xavier_bound"]==expected
    new_keys=[c for c in typed if c not in parameter_key_map(meta)]
    for c in new_keys:
        idx=first.edge_dict[c]
        gen=torch.Generator().manual_seed(relation_seed(c))
        for name in ("relation_att","relation_msg"):
            value=first.state_dict()[name][idx]
            exact=torch.rand(tuple(value.shape),generator=gen).mul(2*expected).sub(expected)
            assert torch.equal(exact,value)
            assert value.abs().max()<=expected
        assert torch.equal(first.relation_pri[idx],torch.ones(2))
    assert not torch.equal(first.relation_att[first.edge_dict[new_keys[0]]],
                           first.relation_att[first.edge_dict[new_keys[1]]])
    with pytest.raises(ValueError,match="Only new E1"):
        copy_typed_layer_parameters(anchor,first,{})
    with pytest.raises(ValueError,match="absent"):
        copy_typed_layer_parameters(anchor,first,{("X","GUARDS","Y"):("X","bad","Y")})


def test_merge_layer_copy_is_bitwise_identical(data):
    merged,_=materialize(data,"G3R")
    anchor,target=layer(merged),layer(merged)
    copy_typed_layer_parameters(anchor,target,{c:c for c in merged})
    assert all(torch.equal(v,target.state_dict()[k]) for k,v in anchor.state_dict().items())
