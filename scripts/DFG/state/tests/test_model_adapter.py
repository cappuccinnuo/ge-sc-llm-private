from collections import OrderedDict
import pytest
import torch
from scripts.DFG.state.model_adapter import reflected_input,build_dgl
from sco_models.graph_utils import reflect_graph
from sco_models.model_hgt import HGTLayer
from scripts.DFG.state.projection import augment_state
from scripts.DFG.state.tests.test_projection import fixture

def test_legacy_would_reverse_state_adapter_preserves_forward_and_baseline():
    data=OrderedDict([
        (("s","next","s"),(torch.tensor([0]),torch.tensor([1]))),
        (("s","STATE_DEF_USE","s"),(torch.tensor([0]),torch.tensor([1])))])
    assert len(reflect_graph(data)[("s","STATE_DEF_USE","s")][0])==2
    fixed=reflected_input(data)
    assert len(fixed[("s","STATE_DEF_USE","s")][0])==1
    base=reflected_input(OrderedDict([next(iter(data.items()))]))
    gold=reflect_graph(OrderedDict([next(iter(data.items()))]))
    for k in base:
        assert all(torch.equal(a,b) for a,b in zip(base[k],gold[k]))

def test_existing_hgt_reads_state_canonical_and_receives_gradient():
    torch.set_num_threads(1);torch.manual_seed(21)
    g,s=fixture();out,a=augment_state(g,{"p.sol":s})
    dg,_=build_dgl(out)
    nd={n:i for i,n in enumerate(dg.ntypes)}
    ed={e:i for i,e in enumerate(dg.canonical_etypes)}
    rows=[i for e,i in ed.items() if e[1]=="STATE_DEF_USE"]
    assert rows
    layer=HGTLayer(8,8,nd,ed,2,dropout=0,use_norm=False)
    h={n:torch.randn(dg.num_nodes(n),8) for n in dg.ntypes}
    prediction=layer(dg,h)
    loss=sum(x.square().sum() for x in prediction.values())
    loss.backward()
    assert torch.isfinite(loss)
    assert layer.relation_msg.grad[rows].abs().sum().item()>0
    # Synthetic backward check only, no optimizer, no data-label benchmark.
