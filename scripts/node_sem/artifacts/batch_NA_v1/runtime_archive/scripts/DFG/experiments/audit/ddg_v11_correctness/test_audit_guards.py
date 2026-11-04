"""Regression checks for the new D1 audit gate, not model training."""
from pathlib import Path
import networkx as nx
import pytest
from scripts.DFG.experiments.audit.ddg_v11_correctness.protect_assets import unexpected_files
from scripts.DFG.experiments.audit.ddg_v11_correctness.finalize_d1 import validate_core
from scripts.DFG.experiments.audit.ddg_v11_correctness.coverage_rebuild import semantic_edges

def test_added_original_file_is_not_hidden_by_before_only_hash_scan():
    assert unexpected_files({'/old/a.py':{}},[Path('/old/a.py'),Path('/old/new.py')])==['/old/new.py']
def test_existing_scope_adds_no_false_new_files():
    assert unexpected_files({'/old/a.py':{}},[Path('/old/a.py')])==[]
def test_only_declared_three_core_changes_are_accepted():
    before={n:'a' for n in ['scripts/DFG/__init__.py','scripts/DFG/projection.py','scripts/DFG/semantic_cfg.py']}
    after={n:'b' for n in before}
    assert len(validate_core(before,after))==3
def test_unrelated_analyzer_change_is_rejected():
    names=['scripts/DFG/__init__.py','scripts/DFG/projection.py','scripts/DFG/semantic_cfg.py','scripts/DFG/reaching_definitions.py']
    with pytest.raises(AssertionError,match='Unexpected core'):
        validate_core({n:'a' for n in names},{n:'b' for n in names})
def assets():
    g=nx.MultiDiGraph()
    g.add_node(1,source_file='a.sol',node_type='function_definition',node_info_vulnerabilities=None)
    g.add_node(2,source_file='a.sol',node_type='return',node_info_vulnerabilities=[{'lines':[12]}])
    g.add_edge(1,2,edge_type='next')
    g.add_edge(1,2,edge_type='DATA_DEF_USE',ddg_fact_indices=[0])
    a={'evidence':[dict(function='a.sol:10',symbol='S',definition='D',use='U',source=1,target=2,self_fact=False)]}
    return g,a
def test_new_edge_must_refer_to_exact_canonical_and_fact_endpoints():
    g,a=assets();r=semantic_edges(g,a)
    assert len(r)==1 and r[0]['canonical']==['function_definition','DATA_DEF_USE','return']
    assert r[0]['facts']==a['evidence']
def test_forged_evidence_endpoint_is_rejected():
    g,a=assets();a['evidence'][0]['target']=1
    with pytest.raises(AssertionError):semantic_edges(g,a)
