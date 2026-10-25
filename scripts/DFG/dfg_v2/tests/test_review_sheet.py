"""Review export integrity tests; fixtures are synthetic audit records."""
import copy
import csv
import hashlib
import json
from pathlib import Path

import networkx as nx
import pytest

from scripts.DFG.dfg_v2 import review_sheet as rs
from scripts.DFG.dfg_v2.score_review import score_review, wilson95
from scripts.DFG.integration.io import sha256, write_json
from scripts.labeling_v2.safe_graph import write_graph

SOURCE = "// UTF8: \u6ce8\u91ca\r\nuint x;\r\nuint a = 1;\r\nx = a;\r\nreturn x + msg.sender;\r\n"
NAME = "same.sol"


def span(text):
    raw = SOURCE.encode("utf8")
    start = raw.index(text.encode())
    return dict(file=NAME, start=start, end=start+len(text.encode()), role="statement")


def fixture(tmp_path, task="fake_contract"):
    folder = tmp_path / task
    folder.mkdir()
    source = folder / NAME
    source.write_bytes(SOURCE.encode("utf8"))
    ref = dict(path=str(source), sha256=sha256(source))
    g = nx.MultiDiGraph()
    for node, code in [(0, "uint x;"), (1, "uint a = 1;"), (2, "x = a;"),
                       (3, "return x + msg.sender;"), (4, "msg.sender")]:
        g.add_node(node, source_file=NAME, node_type="env_source" if node == 4 else "statement",
                   code=code, node_source_code_lines=[99999])
    g.add_edge(1, 2, edge_type=rs.DATA_DEF_USE, ddg_fact_indices=[0])
    g.add_edge(2, 0, edge_type=rs.WRITES_STATE, evidence_indices=[0])
    g.add_edge(0, 3, edge_type=rs.READS_STATE, evidence_indices=[1])
    g.add_edge(4, 3, edge_type=rs.ENV_FLOW, env_key="msg.sender", evidence_indices=[0])
    state = dict(span("uint x;"), name="x")
    audits = dict(L1=dict(source_hashes={NAME:ref["sha256"]},
        files={NAME:dict(anchors=[dict(span("uint a = 1;"),node_id=1),
                                  dict(span("x = a;"),node_id=2)],diagnostics=[])},
        evidence=[dict(source=1,target=2,symbol=NAME+":f:32:a",self_fact=False,
                       function=NAME+":f",routes=["legacy"])]),
        L2=dict(source_hashes={NAME:ref["sha256"]},files={NAME:dict(diagnostics=[])},
            evidence=[dict(file=NAME,source=2,target=0,status="projected",
                relation=rs.WRITES_STATE,state=state,statement=span("x = a;"),
                occurrence=span("x = a;"),via_alias=False),
                dict(file=NAME,source=0,target=3,status="projected",
                relation=rs.READS_STATE,state=state,statement=span("return x + msg.sender;"),
                occurrence=span("return x + msg.sender;"),via_alias=False)]),
        L3=dict(source_hashes={NAME:ref["sha256"]},files={NAME:dict(diagnostics=[])},
            evidence=[dict(file=NAME,source=4,target=3,status="projected",
                env_key="msg.sender",spelling="msg.sender",callable=NAME+":f",
                occurrence=span("msg.sender"),statement=span("return x + msg.sender;"))]))
    return g, dict(layers=audits), ref


def fake_store(tmp_path, monkeypatch):
    tasks, inputs = {}, {}
    for task in ["alpha_contract", "beta_contract"]:
        g,a,ref = fixture(tmp_path,task)
        folder = tmp_path/task
        graph_path, audit_path = folder/"g.gpickle",folder/"audit.json"
        write_graph(g,graph_path)
        write_json(audit_path,a)
        tasks[task] = dict(task="contract", graphs={"F3":dict(
            graph=dict(path=str(graph_path),sha256=sha256(graph_path)),
            audit=dict(path=str(audit_path),sha256=sha256(audit_path)))})
        inputs[task] = dict(graph_files=[NAME],sources={NAME:ref},source_task_id=task)
    manifest = tmp_path/"input.json"
    write_json(manifest,dict(tasks=inputs))
    p = tmp_path/"store.json"
    write_json(p,dict(tasks=tasks,input_manifest=dict(path=str(manifest),sha256=sha256(manifest))))
    monkeypatch.setattr(rs.store,"verify_store",
        lambda path: dict(status="accepted",store_sha256=sha256(path)))
    return p


def export(tmp_path, monkeypatch, name="out"):
    p = fake_store(tmp_path,monkeypatch)
    result=rs.export_review(p,tmp_path/name,files_per_task=1)
    return Path(result["csv"]),Path(result["seal"])


def read_rows(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))


def edit(path, callback):
    rows=read_rows(path)
    callback(rows)
    path.write_bytes(rs._csv_bytes(rows))


def test_same_seed_byte_identical_bom_blank_and_raw_coordinates(tmp_path,monkeypatch):
    p=fake_store(tmp_path,monkeypatch)
    a=rs.export_review(p,tmp_path/"a",files_per_task=1)
    b=rs.export_review(p,tmp_path/"b",files_per_task=1)
    assert Path(a["csv"]).read_bytes()==Path(b["csv"]).read_bytes()
    assert Path(a["csv"]).read_bytes().startswith(b"\xef\xbb\xbf")
    rows=read_rows(Path(a["csv"]))
    assert len(rows)==8
    assert all(r["verdict"]==r["note"]=="" for r in rows)
    by_rel={r["relation"]:r for r in rows}
    assert by_rel[rs.DATA_DEF_USE]["src_line"]=="3"
    assert by_rel[rs.DATA_DEF_USE]["dst_line"]=="4"
    assert by_rel[rs.WRITES_STATE]["dst_line"]=="2"
    assert by_rel[rs.ENV_FLOW]["src_line"]==""
    assert by_rel[rs.ENV_FLOW]["dst_line"]=="5"
    assert all(r["grammar_recovered"]=="not_recorded" for r in rows)
    provenance=json.loads((tmp_path/"a/review_sheet.provenance.json").read_text())
    assert {p["task"] for p in provenance["rows"]}=={"alpha_contract","beta_contract"}
    assert all(p["file"]==NAME and p["source_sha256"] for p in provenance["rows"])


def test_score_blank_and_all_verdict_types_with_wilson(tmp_path,monkeypatch):
    table,seal=export(tmp_path,monkeypatch)
    initial=score_review(table,seal)
    assert not initial["completed"]
    assert all(x["wilson95"] is None for x in initial["relations"].values())
    def fill(rows):
        for row in rows:
            row["verdict"]="correct" if row["task"]=="alpha_contract" else "wrong"
            row["note"]="manual"
        rows[0]["verdict"]="unsure"
    edit(table,fill)
    result=score_review(table,seal)
    assert result["completed"]
    first=result["relations"][rs.DATA_DEF_USE]
    assert first["unsure"]==1 and first["reviewed_denominator"]==1
    for rel in (rs.WRITES_STATE,rs.READS_STATE,rs.ENV_FLOW):
        assert result["relations"][rel]["correct_proportion"]==.5
        assert result["relations"][rel]["wilson95"]==pytest.approx([.0945312057,.9054687943])
    assert wilson95(0,0) is None


@pytest.mark.parametrize("column",[c for c in rs.COLUMNS if c not in rs.EDITABLE_COLUMNS])
def test_every_immutable_column_edit_rejected(tmp_path,monkeypatch,column):
    table,seal=export(tmp_path,monkeypatch)
    edit(table,lambda rows:rows[0].__setitem__(column,rows[0][column]+" changed"))
    with pytest.raises(ValueError,match="Immutable"):
        score_review(table,seal)


@pytest.mark.parametrize("action",["remove","duplicate","reorder","bad_verdict","extra_column","seal_blank","proof"])
def test_review_mutations_rejected(tmp_path,monkeypatch,action):
    table,seal=export(tmp_path,monkeypatch)
    if action=="remove": edit(table,lambda rows:rows.pop())
    elif action=="duplicate": edit(table,lambda rows:rows.append(dict(rows[0])))
    elif action=="reorder": edit(table,lambda rows:rows.reverse())
    elif action=="bad_verdict": edit(table,lambda rows:rows[0].__setitem__("verdict","yes"))
    elif action=="extra_column":table.write_text(table.read_text(encoding="utf-8-sig").replace("review_id,","extra,review_id,",1),encoding="utf8")
    elif action=="seal_blank":(seal.parent/"review_sheet.blank.csv").write_text("tampered")
    elif action=="proof":(seal.parent/"review_sheet.provenance.json").write_text("{}")
    with pytest.raises((ValueError,AssertionError)):
        score_review(table,seal)


def test_verify_called_before_any_graph_read_and_no_output_on_reject(tmp_path,monkeypatch):
    p=fake_store(tmp_path,monkeypatch)
    def reject(path):raise ValueError("store rejected")
    def forbidden(path):raise AssertionError("graph read before verify")
    monkeypatch.setattr(rs.store,"verify_store",reject)
    monkeypatch.setattr(rs,"read_graph",forbidden)
    with pytest.raises(ValueError,match="store rejected"):
        rs.export_review(p,tmp_path/"out",files_per_task=1)
    assert not (tmp_path/"out").exists()


def test_source_and_audit_mutation_rejected_before_publication(tmp_path,monkeypatch):
    p=fake_store(tmp_path,monkeypatch)
    (tmp_path/"alpha_contract"/NAME).write_text("changed")
    with pytest.raises(ValueError):
        rs.export_review(p,tmp_path/"out",files_per_task=1)
    assert not (tmp_path/"out").exists()


def test_existing_output_insufficient_files_and_node_task_rejected(tmp_path,monkeypatch):
    p=fake_store(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="Insufficient"):
        rs.export_review(p,tmp_path/"too_many")
    with pytest.raises(ValueError,match="contract"):
        rs.export_review(p,tmp_path/"node",task_ids=["fake_node"])
    rs.export_review(p,tmp_path/"ok",files_per_task=1)
    with pytest.raises(FileExistsError):
        rs.export_review(p,tmp_path/"ok",files_per_task=1)


def test_missing_ambiguous_anchor_and_mismatched_evidence_rejected(tmp_path):
    g,a,ref=fixture(tmp_path)
    raw=SOURCE.encode()
    edge=next(e for e in g.edges(keys=True,data=True) if e[3]["edge_type"]==rs.DATA_DEF_USE)
    bad=copy.deepcopy(a)
    bad["layers"]["L1"]["files"][NAME]["anchors"]=[]
    with pytest.raises(ValueError,match="anchor"):
        rs._edge_row("fake",g,bad,ref,raw,edge)
    bad=copy.deepcopy(a)
    bad["layers"]["L1"]["files"][NAME]["anchors"].append(dict(span("uint x;"),node_id=1))
    with pytest.raises(ValueError,match="anchor"):
        rs._edge_row("fake",g,bad,ref,raw,edge)
    bad=copy.deepcopy(a)
    bad["layers"]["L1"]["evidence"][0]["target"]=0
    with pytest.raises(ValueError,match="endpoints"):
        rs._edge_row("fake",g,bad,ref,raw,edge)


def test_grammar_status_does_not_invent_missing_l2_evidence(tmp_path):
    g,a,ref=fixture(tmp_path)
    l1edge=next(e for e in g.edges(keys=True,data=True) if e[3]["edge_type"]==rs.DATA_DEF_USE)
    a["layers"]["L1"]["evidence"][0]["routes"]=["v2_access_shape"]
    row,_=rs._edge_row("fake",g,a,ref,SOURCE.encode(),l1edge)
    assert row["grammar_recovered"]=="function_route_recorded"
    envedge=next(e for e in g.edges(keys=True,data=True) if e[3]["edge_type"]==rs.ENV_FLOW)
    occurrence=span("msg.sender")
    a["layers"]["L3"]["files"][NAME]["diagnostics"]=[dict(kind="grammar_shape_recovered",
        callable=NAME+":f",start=occurrence["start"],end=occurrence["end"],
        key="msg.sender",spelling="msg.sender")]
    row,proof=rs._edge_row("fake",g,a,ref,SOURCE.encode(),envedge)
    assert row["grammar_recovered"]=="occurrence_confirmed"
    assert len(proof["grammar_recovery_evidence"])==1


def test_sampling_cap_and_deterministic_subset(tmp_path):
    import random
    g,a,ref=fixture(tmp_path)
    for i in range(10):
        g.add_edge(1,2,key=10+i,edge_type=rs.DATA_DEF_USE,ddg_fact_indices=[0])
    args=("fake",g,a,{NAME:ref})
    rows,proof,pop=rs._sample_task(*args,rng=random.Random(0),files_per_task=1,max_edges=5)
    again=rs._sample_task(*args,rng=random.Random(0),files_per_task=1,max_edges=5)
    assert (rows,proof,pop)==again
    assert sum(r["relation"]==rs.DATA_DEF_USE for r in rows)==5
    assert pop[0]["available_edges"][rs.DATA_DEF_USE]==11
    assert pop[0]["sampled_edges"][rs.DATA_DEF_USE]==5
