"""NS-P3b feature oracles: source-only fixtures, no Solidity compilation claim."""
import copy
import hashlib
from pathlib import Path
import numpy as np
import pytest
from scripts.node_sem import static_profile as sp
from scripts.node_sem.facts_schema import new_facts, NODE_KINDS
from scripts.node_sem.ctx_alignment import enrich
from scripts.node_sem.ctx_fields import ctx_fields, render
from scripts.node_sem.facts import extract_source
from scripts.node_sem.tests.test_facts_integration import graph_fixture, FILE
from scripts.node_sem.tests.test_facts_names import rename
from scripts.node_sem.tests.test_facts_oracle import MANIFEST, FIXTURES
from scripts.node_sem.text_view import cut_span, normalize
from scripts.DFG.projection import Projector, ANCHOR, decoded
from scripts.DFG.dfg_v2.projection_view import ProjectionView


def make_rows(source, graph, evidence, inverse=None):
    records,_=extract_source(source,FILE,graph=graph,evidence=evidence,original_names=inverse)
    view=ProjectionView(source,FILE)
    projector=Projector(graph,view)
    by_id={i:view.compat_nodes[k] for k,i in view.compat_ids.items()}
    asts={nid:by_id[i] for i,nid in projector.by_ast.items()}
    texts=[]
    for nid,a in graph.nodes(data=True):
        ast=asts[nid]
        start,end,prefix,suffix,_,_=cut_span(ast,view,a["node_type"])
        text=normalize(prefix+view.compat[start:end].decode()+suffix)
        texts.append(dict(row_key=nid,file=FILE,node_type=a["node_type"],text=text,
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),source_sha256=view.sha256,
            code_sha256=hashlib.sha256(a["code"].encode()).hexdigest()))
    facts=[dict(row_key=nid,facts=records[nid]) for nid in graph]
    return facts,enrich(graph,{FILE:source},texts,facts)


def features(source,graph,evidence,inverse=None):
    facts,texts=make_rows(source,graph,evidence,inverse)
    schema=sp.load_schema()
    return (np.stack([sp.encode(r,schema) for r in facts]),
        [ctx_fields(f,t) for f,t in zip(facts,texts)],
        [ctx_fields(f,t,"masked") for f,t in zip(facts,texts)])


def test_schema_complete_nonoverlapping_and_derived_unknown_fields():
    schema=sp.load_schema()
    assert schema["dimension"]==243
    assert [i for f in schema["fields"] for i in range(f["start"],f["stop"])]==list(range(schema["dimension"]))
    assert len(sp.column_names())==len(set(sp.column_names()))
    for group,kind in (("state_decl","state_decl"),("fn_summary","function"),("contract_summary","contract")):
        expected=set(new_facts(kind)[group])-{"status","unknown_fields"}
        actual={f["name"].split(".")[-1] for f in schema["fields"] if f["name"].startswith("unknown."+group+".")}
        assert actual==expected


@pytest.mark.parametrize("kind",NODE_KINDS)
def test_applicability_one_hot_and_lossless_explanation(kind):
    f=new_facts(kind);schema=sp.load_schema();v=sp.encode(f,schema)
    assert v.dtype==np.uint8 and np.isin(v,[0,1]).all()
    assert np.array_equal(v,sp.from_explanation(sp.explain(v)))
    for field in schema["fields"]:
        bits=v[field["start"]:field["stop"]]
        applicable=kind in field["applicable"]
        unknown=applicable and field["unknown"] and sp.unknown(f,field["unknown"])
        if field["encoding"]=="one_hot": assert bits.sum()==(0 if unknown else 1)
        elif not applicable or unknown: assert not bits.any()


@pytest.mark.parametrize("kind,group", [("state_decl","state_decl"),("function","fn_summary"),("contract","contract_summary")])
def test_partial_unknown_preserves_other_true_values(kind,group):
    f=new_facts(kind)
    boolean=[k for k,v in f[group].items() if type(v) is bool]
    known,missing=boolean[:2]
    f[group].update({known:True,missing:True,"unknown_fields":[missing],"status":"unknown"})
    names=sp.explain(sp.encode(f))
    assert group+"."+known+"=true" in names
    assert group+"."+missing+"=true" not in names
    assert "unknown."+group+"."+missing+"=true" in names
    assert "unknown."+group+"."+known+"=true" not in names


def test_unknown_is_neither_known_zero_count_nor_absent_guard():
    f=new_facts("statement");f["guard_status"]="unknown"
    names=sp.explain(sp.encode(f))
    assert "state.write_count=zero" not in names and "guards.kinds=none" not in names
    assert "unknown.state=true" in names and "unknown.guard=true" in names
    f["state"]["status"]="supported";f["guard_status"]="none"
    names=sp.explain(sp.encode(f))
    assert "state.write_count=zero" in names and "guards.kinds=none" in names


def test_semantic_expected_columns_and_fields():
    s,g,e=graph_fixture("address owner; uint total; function f(uint p) public { require(msg.sender==owner); uint x=p+1; total=x; }")
    facts,texts=make_rows(s,g,e)
    idx=next(i for i,r in enumerate(texts) if r["text"]=="total=x;")
    f=facts[idx];t=texts[idx];fields=ctx_fields(f,t)
    assert fields["STMT"]==["total=x;"]
    assert fields["STATE_W"]==["total:scalar"]
    assert fields["GUARD"][0]=="kind:require"
    assert any("@-1" in x for x in fields["FROM"])
    assert "function f(uint p) public" in fields["FUNC"][0]
    names=sp.explain(sp.encode(f))
    assert "state.write_count=one" in names and "guards.pairs=env_state" in names
    masked=ctx_fields(f,t,"masked")
    assert "STATE1" in masked["STMT"][0]
    assert all(x not in render(masked) for x in ("total","owner","uint x"))
    assert masked["GUARD"]==fields["GUARD"]


@pytest.mark.parametrize("case",MANIFEST["cases"],ids=lambda x:x["id"])
def test_oracle_bijection_static_and_masked_context_invariant(case):
    source=(FIXTURES/case["source"]).read_text()
    changed,inverse=rename(source)
    s,g,e=graph_fixture("",source_override=source)
    t,h,q=graph_fixture("",source_override=changed)
    old=features(s,g,e);new=features(t,h,q,inverse)
    assert np.array_equal(old[0],new[0])
    assert old[2]==new[2]


@pytest.mark.parametrize("perturb",["labels","prefix"])
def test_direct_producer_target_and_dot_prefix_invariance(perturb):
    s,g,e=graph_fixture("address owner; uint total; function f(uint p) public { require(msg.sender==owner); total=p; }")
    old=features(s,g,e)
    changed=copy.deepcopy(g)
    for _,a in changed.nodes(data=True):
        if perturb=="labels":a.update(node_info_vulnerabilities=[{"lines":[999]}],type_label=123,method="DO_NOT_USE_TARGET")
        else:a["label"]="DO_NOT_USE_TARGET-"+ANCHOR.search(decoded(a["label"])).group()
    new=features(s,changed,e)
    assert np.array_equal(old[0],new[0]) and old[1:]==new[1:]


def test_bad_anchor_fails_before_feature_output():
    s,g,e=graph_fixture("uint total; function f(uint p) public { total=p; }")
    next(iter(g.nodes(data=True)))[1]["label"]="broken"
    with pytest.raises(ValueError):features(s,g,e)


def test_auxiliary_and_end_have_only_stmt_and_no_invented_semantics():
    for kind,text in (("end","<END_IF>"),("env","msg.sender")):
        f=new_facts(kind)
        if kind=="env":f["env"]["keys"]=["msg.sender"]
        t={"_ctx":dict(piece=dict(text=text,identifiers=[]),neighbors={},function=None)}
        assert list(ctx_fields(f,t))==["STMT"]
        names=sp.explain(sp.encode(f))
        assert not any(x.startswith("external.kinds=") for x in names)
        assert ("env.merged=msg.sender" in names)==(kind=="env")


def test_summary_ctx_unknown_is_per_field():
    f=new_facts("function")
    f["fn_summary"].update(external_call=True,unknown_fields=["state_write"],status="unknown")
    t={"_ctx":dict(piece=dict(text="function f()",identifiers=[]),neighbors={},function=None)}
    fields=ctx_fields(f,t)
    assert "external_call=true" in fields["FN_SUMMARY"]
    assert "state_write=unknown" in fields["FN_SUMMARY"]
