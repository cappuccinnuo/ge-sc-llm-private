import copy
import numpy as np
import pytest
from scripts.DFG.pipeline import augment
from scripts.DFG.graph_audit import fingerprint,assert_augmented
from scripts.DFG.tests.test_projection import assets,SOURCE

def test_add_only_edges_preserves_tokens_labels_ids_and_multiedges():
    g,_=assets()
    for n in g:
        g.nodes[n]["token"]=np.arange(512,dtype=np.float32)+n
        g.nodes[n]["node_info_vulnerabilities"]=None
    s,t=next(iter(g.edges()))
    g.add_edge(s,t,key="parallel_original",edge_type="next")
    initial=fingerprint(g)
    enhanced,audit=augment(g,{"a.sol":SOURCE})
    assert fingerprint(g)==initial
    assert audit["invariants"]["ddg_edges"]>0
    assert all(d["edge_type"]!="REV_DATA_DEF_USE" for _,_,d in enhanced.edges(data=True))
    assert_augmented(g,enhanced)
    assert len(enhanced)==len(g)

def test_label_permutation_changes_no_ddg_edges():
    g,_=assets()
    a,_=augment(g,{"a.sol":SOURCE})
    for n in g:g.nodes[n]["node_info_vulnerabilities"]=[{"lines":[n]}]
    b,_=augment(g,{"a.sol":SOURCE})
    ddg=lambda z:{(s,t) for s,t,d in z.edges(data=True) if d["edge_type"]=="DATA_DEF_USE"}
    assert ddg(a)==ddg(b)

def test_missing_or_unsupported_source_retains_entire_graph():
    g,_=assets()
    for sources in ({},{"a.sol":SOURCE.replace("^0.5.17",">=0.4.0 <0.9.0")}):
        out,audit=augment(g,sources)
        assert fingerprint(out)==fingerprint(g)
        assert audit["files"]["a.sol"]["diagnostics"]

def test_duplicate_augmentation_rejected():
    g,_=assets(); enhanced,_=augment(g,{"a.sol":SOURCE})
    with pytest.raises(ValueError,match="Already enhanced"):
        augment(enhanced,{"a.sol":SOURCE})

def test_wrong_source_does_not_guess_by_line():
    g,_=assets()
    out,a=augment(g,{"a.sol":SOURCE.replace("y=x+1","y=x+2")})
    assert fingerprint(out)==fingerprint(g)
    assert a["files"]["a.sol"]["diagnostics"][-1]["kind"]=="projection_fallback"
