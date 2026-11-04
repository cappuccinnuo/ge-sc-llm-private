import networkx as nx
import pytest
from .context_audit import ensure_identity,exact_train_matches,interval_rows

def graph():
    g=nx.MultiDiGraph()
    g.add_node(1,source_file='a.sol',code='x()',node_info_vulnerabilities=None)
    g.add_node(2,source_file='b.sol',code='x()',node_info_vulnerabilities=[{'lines':[4]}])
    g.add_node(3,source_file='c.sol',code='x()',node_info_vulnerabilities=None)
    return g
def test_exact_train_match_excludes_val_and_label():
    assert exact_train_matches(graph(),['a.sol','b.sol'],['c.sol'],'x()')==[1,2]
def test_split_overlap_rejected():
    with pytest.raises(ValueError):exact_train_matches(graph(),['a.sol'],['a.sol'],'x()')
def test_whitespace_not_fuzzy():
    assert exact_train_matches(graph(),['a.sol'],['c.sol'],' x()')==[]
@pytest.mark.parametrize('row',[dict(file='b.sol',original_graph_node_id=1,target=0),
    dict(file='a.sol',original_graph_node_id=2,target=0),
    dict(file='a.sol',original_graph_node_id=1,target=1)])
def test_identity_errors(row):
    with pytest.raises(ValueError):ensure_identity(graph(),'a.sol',1,row)
def test_typed_id():
    with pytest.raises(ValueError):ensure_identity(graph(),'a.sol','1',{})
def test_identity_pass():
    assert ensure_identity(graph(),'a.sol',1,dict(file='a.sol',original_graph_node_id=1,target=0))['code']=='x()'
def test_overlap_union_preserves_csv_records():
    rows=[dict(loc='105',length='10'),dict(loc='111',length='6')]
    assert len(interval_rows(rows,112,112))==2
    assert len(interval_rows(rows,115,115))==1
    assert interval_rows(rows,117,117)==[]
def test_invalid_interval_rejected():
    with pytest.raises(ValueError):interval_rows([dict(loc='0',length='2')],1,2)


def test_source_hash_integrity_is_not_mapping_fallback(tmp_path):
    from .context_audit import SourceIndex, MappingUnavailable
    p=tmp_path/'a.sol';p.write_text('contract C {}')
    index=SourceIndex(graph(),{'sources':{'a.sol':{'path':str(p),'sha256':'bad'}}},{})
    with pytest.raises(ValueError,match='Source SHA mismatch') as result:index.file('a.sol')
    assert not isinstance(result.value,MappingUnavailable)

def test_projection_failure_not_downgraded(tmp_path,monkeypatch):
    from . import context_audit as m
    p=tmp_path/'a.sol';p.write_text('contract C {}')
    index=m.SourceIndex(graph(),{'sources':{'a.sol':{'path':str(p),'sha256':m.sha(p)}}},{})
    monkeypatch.setattr(m,'SourceView',lambda *a: object())
    def fail(*args):raise m.Unsupported('AST/HCG source text differs: 1')
    monkeypatch.setattr(m,'Projector',fail)
    with pytest.raises(ValueError,match='Integrity') as result:index.file('a.sol')
    assert not isinstance(result.value,m.MappingUnavailable)

def test_known_version_parse_limit_is_explicit(tmp_path,monkeypatch):
    from . import context_audit as m
    p=tmp_path/'a.sol';p.write_text('contract C {}')
    index=m.SourceIndex(graph(),{'sources':{'a.sol':{'path':str(p),'sha256':m.sha(p)}}},{})
    def fail(*args):raise m.Unsupported('Multiple Solidity pragmas require version intersection verification')
    monkeypatch.setattr(m,'SourceView',fail)
    with pytest.raises(m.MappingUnavailable):index.file('a.sol')
