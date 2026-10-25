"""Read-only diff integrity. Synthetic graph/audit fixtures, not Solidity compilation."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.DFG.dfg_v2 import store_diff as sd, review_sheet as rs
from scripts.DFG.dfg_v2.tests.test_review_sheet import fixture, span, SOURCE, NAME
from scripts.DFG.integration.io import sha256, write_json
from scripts.labeling_v2.safe_graph import write_graph


def graph_pair(tmp_path, added=False):
    graph, audit, ref = fixture(tmp_path)
    fn = dict(function=NAME+":f", file=NAME, start=0, end=len(SOURCE.encode()),
        line=1, name="stable", old_status="supported", old_reason=None,
        status="supported", routes=["legacy"], facts=1, recovered=False, legacy_reused=True)
    pending = dict(function=NAME+":pending", file=NAME, start=0, end=len(SOURCE.encode()),
        line=1, name="recovered", old_status="fallback", old_reason="unsupported struct_expression",
        status="fallback", routes=[], facts=0, recovered=False,
        reason="unsupported struct_expression", partial_facts_published=False)
    audit["layers"]["L1"]["files"][NAME]["analysis"] = dict(functions=[fn,pending])
    new, next_audit = copy.deepcopy(graph), copy.deepcopy(audit)
    if added:
        rec=next_audit["layers"]["L1"]["files"][NAME]["analysis"]["functions"][1]
        rec.update(status="supported",routes=["v2_retry"],facts=1,recovered=True,legacy_reused=False)
        next_audit["layers"]["L1"]["evidence"].append(dict(source=1,target=3,
            symbol=NAME+":pending:a",self_fact=False,function=NAME+":pending",routes=["v2_retry"]))
        next_audit["layers"]["L1"]["files"][NAME]["anchors"].append(
            dict(span("return x + msg.sender;"),node_id=3))
        new.add_edge(1,3,edge_type=rs.DATA_DEF_USE,ddg_fact_indices=[1])
    return graph,new,audit,next_audit,{NAME:ref}


def compare(parts):
    return sd.compare_graphs(*parts, key="F3")


def test_zero_change_exact_acceptance(tmp_path):
    result=compare(graph_pair(tmp_path))
    assert result["added_edges"]==result["removed_edges"]==0
    assert result["unchanged_function_count"]==2


def test_recovered_function_addition_has_text_reason_and_proof(tmp_path):
    result=compare(graph_pair(tmp_path,True))
    assert result["added_edges"]==1
    assert result["added_by_relation"]=={"DATA_DEF_USE":1}
    edge=result["added"][0]
    assert edge["source_statement"]["code"]=="uint a = 1;"
    assert edge["target_statement"]["code"]=="return x + msg.sender;"
    assert edge["old_fallback_reasons"]=={NAME+":pending":"unsupported struct_expression"}
    assert result["recovered_functions"][0]["source_code"]==SOURCE


@pytest.mark.parametrize("mutation",[
    "node_label","node_token","node_order","graph_attr","edge_attr","edge_removed",
    "edge_key","wrong_relation","L2_evidence","L3_evidence","old_L1_evidence",
    "old_function_record","unproven_addition","unknown_evidence_function",
    "new_edge_bad_index","wrong_function_span"])
def test_invariants_reject_changes(tmp_path,mutation):
    old,new,a,b,sources=graph_pair(tmp_path,True)
    if mutation=="node_label":new.nodes[1]["label"]=1
    elif mutation=="node_token":new.nodes[1]["token"]=np.ones(512)
    elif mutation=="node_order":
        attrs=new.nodes[0].copy();new.remove_node(0);new.add_node(0,**attrs)
    elif mutation=="graph_attr":new.graph["other"]=1
    elif mutation=="edge_attr":new[1][2][0]["ddg_fact_indices"]=[1]
    elif mutation=="edge_removed":new.remove_edge(1,2,0)
    elif mutation=="edge_key":
        attrs=dict(new[1][2][0]);new.remove_edge(1,2,0);new.add_edge(1,2,key=77,**attrs)
    elif mutation=="wrong_relation":new[1][3][0]["edge_type"]="READS_STATE"
    elif mutation=="L2_evidence":b["layers"]["L2"]["evidence"][0]["via_alias"]=True
    elif mutation=="L3_evidence":b["layers"]["L3"]["evidence"][0]["spelling"]="spoof"
    elif mutation=="old_L1_evidence":b["layers"]["L1"]["evidence"][0]["symbol"]="wrong"
    elif mutation=="old_function_record":
        b["layers"]["L1"]["files"][NAME]["analysis"]["functions"][0]["facts"]=9
    elif mutation=="unproven_addition":
        b["layers"]["L1"]["evidence"][-1]["function"]=NAME+":f"
    elif mutation=="unknown_evidence_function":
        b["layers"]["L1"]["evidence"][-1]["function"]="not-a-function"
    elif mutation=="new_edge_bad_index":new[1][3][0]["ddg_fact_indices"]=[999]
    elif mutation=="wrong_function_span":
        for audit in (a,b):
            audit["layers"]["L1"]["files"][NAME]["analysis"]["functions"][1]["start"]=10
            audit["layers"]["L1"]["files"][NAME]["analysis"]["functions"][1]["end"]=11
    with pytest.raises(ValueError):
        compare((old,new,a,b,sources))


def test_l2_derived_invariants_excluded_but_semantics_exact(tmp_path):
    parts=graph_pair(tmp_path,True)
    parts[2]["layers"]["L2"]["invariants"]={"original_edges":5}
    parts[3]["layers"]["L2"]["invariants"]={"original_edges":6}
    assert compare(parts)["added_edges"]==1


def make_stores(tmp_path,monkeypatch,added=False):
    old,new,a,b,sources=graph_pair(tmp_path,added)
    task="fake_contract"
    manifest=tmp_path/"input.json"
    write_json(manifest,dict(tasks={task:dict(sources=sources,graph_files=[NAME])}))
    input_ref=dict(path=str(manifest),sha256=sha256(manifest))
    paths=[]
    for name,g,audit in (("old",old,a),("new",new,b)):
        folder=tmp_path/name;folder.mkdir()
        gp,ap=folder/"graph.gpickle",folder/"audit.json"
        write_graph(g,gp);write_json(ap,audit)
        entry=dict(graph=dict(path=str(gp),sha256=sha256(gp)),
                   audit=dict(path=str(ap),sha256=sha256(ap)))
        doc=dict(tasks={task:dict(task_id=task,category="fake",task="contract",
            input_task_digest="same",missing_sources=[],graphs={"F3":entry})},
            input_manifest=input_ref,requested_tasks=[task],saved_graph_keys=["F3"])
        path=folder/"store.json";write_json(path,doc);write_json(folder/"store.seal.json",{"test":True})
        paths.append(path)
    # Production verify_store is separately tested. These deliberately minimal
    # synthetic audit fixtures exercise diff logic after a successful verifier.
    monkeypatch.setattr(sd.store,"verify_store",
        lambda path:dict(status="accepted",store_sha256=sha256(path)))
    exported=rs.export_review(paths[0],tmp_path/"review",files_per_task=1)
    return paths,Path(exported["seal"]),Path(exported["csv"])


def test_store_seal_review_all_rows_and_scoring_binding(tmp_path,monkeypatch):
    from scripts.DFG.dfg_v2.score_review import score_review
    paths,seal,table=make_stores(tmp_path,monkeypatch,True)
    result=sd.write_diff(*paths,seal,tmp_path/"diff")
    assert result["review"]["rows_verified"]==4
    assert result["review"]["new_F3_edges_in_reviewed_tasks_not_sampled"]==1
    report=tmp_path/"diff/store_diff.json"
    checked=sd.verify_equivalence(report,seal)
    assert checked["rows_verified"]==4
    assert checked["scoring_store"]["path"]==str(paths[1])
    scored=score_review(table,seal,equivalence=report)
    assert scored["scoring_store"]["path"]==str(paths[1])
    assert scored["relations"]["DATA_DEF_USE"]["blank"]==1
    assert "scoring_store" not in score_review(table,seal)
    with pytest.raises(FileExistsError):
        sd.write_diff(*paths,seal,tmp_path/"diff")


@pytest.mark.parametrize("mutation",["report","resealed_report","store","store_seal","review_seal","graph"])
def test_equivalence_tamper_rejected(tmp_path,monkeypatch,mutation):
    paths,seal,table=make_stores(tmp_path,monkeypatch)
    sd.write_diff(*paths,seal,tmp_path/"diff")
    report=tmp_path/"diff/store_diff.json"
    if mutation in ("report","resealed_report"):
        data=json.loads(report.read_text());data["review"]["rows_verified"]=999;write_json(report,data)
        if mutation=="resealed_report":
            sealp=report.with_name("store_diff.seal.json")
            data=json.loads(sealp.read_text());data["report_sha256"]=sha256(report);write_json(sealp,data)
    elif mutation=="store":paths[1].write_text("{}")
    elif mutation=="store_seal":paths[1].with_name("store.seal.json").write_text("{}")
    elif mutation=="review_seal":
        data=json.loads(seal.read_text());data["row_count"]=99;write_json(seal,data)
    elif mutation=="graph":(paths[1].parent/"graph.gpickle").write_bytes(b"spoof")
    with pytest.raises((ValueError,AssertionError)):
        sd.verify_equivalence(report,seal)


def test_wrong_inputs_fail_before_publication(tmp_path,monkeypatch):
    paths,seal,table=make_stores(tmp_path,monkeypatch)
    doc=json.loads(paths[1].read_text());doc["input_manifest"]["sha256"]="bad";write_json(paths[1],doc)
    with pytest.raises(ValueError,match="input manifest"):
        sd.write_diff(*paths,seal,tmp_path/"diff")
    assert not (tmp_path/"diff").exists()


def test_review_proof_forgery_resealed_rejected(tmp_path,monkeypatch):
    paths,seal,table=make_stores(tmp_path,monkeypatch)
    provenance=seal.parent/"review_sheet.provenance.json"
    proof=json.loads(provenance.read_text());proof["rows"][0]["source_node_id"]=99;write_json(provenance,proof)
    data=json.loads(seal.read_text());data["provenance"]["sha256"]=sha256(provenance);write_json(seal,data)
    with pytest.raises(ValueError,match="no longer exists"):
        sd.write_diff(*paths,seal,tmp_path/"diff")
    assert not (tmp_path/"diff").exists()

@pytest.mark.parametrize("mutation", ["span", "node_id", "role", "remove", "extra_property"])
def test_old_nonreviewed_anchor_cannot_change(tmp_path, mutation):
    old, new, before, after, sources = graph_pair(tmp_path)
    # An old anchor need not be sampled or appear in an edge to remain bound.
    extra = dict(span("return x + msg.sender;"), node_id=3)
    before["layers"]["L1"]["files"][NAME]["anchors"].append(dict(extra))
    after["layers"]["L1"]["files"][NAME]["anchors"].append(dict(extra))
    anchors = after["layers"]["L1"]["files"][NAME]["anchors"]
    if mutation == "span": anchors[-1]["start"] += 1
    elif mutation == "node_id": anchors[-1]["node_id"] = 77
    elif mutation == "role": anchors[-1]["role"] = "other_role"
    elif mutation == "remove": anchors.pop()
    else: anchors[-1]["unexpected"] = "modified"
    with pytest.raises(ValueError, match="Old L1 node/Span anchor"):
        compare((old, new, before, after, sources))


def test_new_anchor_without_recovered_function_rejected(tmp_path):
    parts = graph_pair(tmp_path)
    parts[3]["layers"]["L1"]["files"][NAME]["anchors"].append(
        dict(span("return x + msg.sender;"), node_id=3))
    with pytest.raises(ValueError, match="outside recovered"):
        compare(parts)


def test_new_anchor_outside_recovered_function_rejected(tmp_path):
    old, new, before, after, sources = graph_pair(tmp_path, True)
    for audit in (before, after):
        audit["layers"]["L1"]["files"][NAME]["analysis"]["functions"][1]["start"] = len(SOURCE.encode()) - 2
    with pytest.raises(ValueError, match="outside recovered"):
        compare((old, new, before, after, sources))


def test_shared_node_id_distinct_old_spans_retained(tmp_path):
    parts = graph_pair(tmp_path, True)
    for audit in (parts[2], parts[3]):
        audit["layers"]["L1"]["files"][NAME]["anchors"].append(
            dict(span("uint x;"), node_id=2))
    # Shared node IDs do not permit one record to overwrite the other.
    # This tests anchor comparison directly; edge projection requires one
    # unambiguous statement span and is tested elsewhere.
    recovered, unchanged = sd.compare_l1(parts[2]["layers"]["L1"], parts[3]["layers"]["L1"], parts[4])
    assert len(recovered) == 1 and len(unchanged) == 1


def reindex_new_pair(parts):
    old, new, before, after, sources = parts
    proof = after["layers"]["L1"]["evidence"]
    assert len(proof) == 2
    after["layers"]["L1"]["evidence"] = [proof[1], proof[0]]
    new[1][2][0]["ddg_fact_indices"] = [1]
    new[1][3][0]["ddg_fact_indices"] = [0]
    return parts


def test_allowed_index_reorder_preserves_exact_fact_identity(tmp_path):
    parts = reindex_new_pair(graph_pair(tmp_path, True))
    result = compare(parts)
    assert result["added_edges"] == 1
    remaps = result["l1_reference_remappings"]
    assert len(remaps) == 1
    assert remaps[0]["old_indices"] == [0]
    assert remaps[0]["new_indices"] == [1]
    assert remaps[0]["index_mapping"] == [{"old": 0, "new": 1}]
    assert remaps[0]["resolved_evidence_exact"] is True
    assert result["invariants"]["old_edge_raw_attributes_exact"] is False


@pytest.mark.parametrize("bad", [[0], [True], [-1], [999], [1, 1], []])
def test_reference_reorder_rejects_invalid_or_wrong_fact_indices(tmp_path, bad):
    parts = reindex_new_pair(graph_pair(tmp_path, True))
    parts[1][1][2][0]["ddg_fact_indices"] = bad
    with pytest.raises(ValueError):
        compare(parts)


def test_reference_reorder_does_not_allow_other_attributes(tmp_path):
    parts = reindex_new_pair(graph_pair(tmp_path, True))
    parts[1][1][2][0]["routes"] = ["changed"]
    with pytest.raises(ValueError, match="attributes"):
        compare(parts)


def test_reference_reorder_requires_same_order_and_multiplicity(tmp_path):
    old, new, before, after, sources = graph_pair(tmp_path)
    extra = dict(before["layers"]["L1"]["evidence"][0], symbol=NAME+":f:other")
    before["layers"]["L1"]["evidence"].append(dict(extra))
    after["layers"]["L1"]["evidence"].append(dict(extra))
    old[1][2][0]["ddg_fact_indices"] = [0, 1]
    new[1][2][0]["ddg_fact_indices"] = [1, 0]
    with pytest.raises(ValueError, match="evidence"):
        compare((old, new, before, after, sources))


def test_reference_reorder_rejects_changed_fact_with_same_index(tmp_path):
    parts = graph_pair(tmp_path)
    parts[3]["layers"]["L1"]["evidence"][0]["symbol"] = NAME+":f:wrong"
    with pytest.raises(ValueError, match="evidence"):
        compare(parts)


def test_review_equivalence_reordered_indices_remain_source_bound(tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2.score_review import score_review
    from scripts.labeling_v2.safe_graph import read_graph
    paths, seal, table = make_stores(tmp_path, monkeypatch, True)
    new_store = json.loads(paths[1].read_text())
    entry = new_store["tasks"]["fake_contract"]["graphs"]["F3"]
    graph_path, audit_path = Path(entry["graph"]["path"]), Path(entry["audit"]["path"])
    graph, audit = read_graph(graph_path), json.loads(audit_path.read_text())
    proof = audit["layers"]["L1"]["evidence"]
    audit["layers"]["L1"]["evidence"] = [proof[1], proof[0]]
    graph[1][2][0]["ddg_fact_indices"] = [1]
    graph[1][3][0]["ddg_fact_indices"] = [0]
    graph_path = graph_path.with_name("reindexed.gpickle")
    write_graph(graph, graph_path); write_json(audit_path, audit)
    entry["graph"]["path"] = str(graph_path)
    entry["graph"]["sha256"], entry["audit"]["sha256"] = sha256(graph_path), sha256(audit_path)
    write_json(paths[1], new_store)
    result = sd.write_diff(*paths, seal, tmp_path/"diff")
    assert result["review"]["rows_verified"] == 4
    assert result["review"]["reference_remapping_rows"] == 1
    reviewed = [x for x in result["review"]["rows"] if x["relation"] == rs.DATA_DEF_USE][0]
    assert reviewed["old_indices"] == [0] and reviewed["new_indices"] == [1]
    assert reviewed["old_attributes_sha256"] != reviewed["new_attributes_sha256"]
    assert reviewed["semantically_unchanged"] is True
    scored = score_review(table, seal, equivalence=tmp_path/"diff/store_diff.json")
    assert scored["scoring_store"]["path"] == str(paths[1])

def still_fallback_reason_pair(tmp_path):
    old, new, before, after, sources = graph_pair(tmp_path)
    ident = NAME + ":pending"
    for audit in (before, after):
        audit["layers"]["L1"]["files"][NAME]["diagnostics"].append(dict(
            kind="v2_function_fallback", function=ident, file=NAME,
            reason="unsupported struct_expression", partial_facts_published=False))
    after["layers"]["L1"]["files"][NAME]["analysis"]["functions"][1]["reason"] = "Unsupported control flow: assembly_statement"
    after["layers"]["L1"]["files"][NAME]["diagnostics"][-1]["reason"] = "Unsupported control flow: assembly_statement"
    return old, new, before, after, sources


def test_approved_still_fallback_reason_progression_is_separate(tmp_path):
    result = compare(still_fallback_reason_pair(tmp_path))
    assert result["added_edges"] == result["removed_edges"] == 0
    assert not result["recovered_functions"]
    assert result["unchanged_function_count"] == 2
    assert len(result["reason_changes"]) == 1
    change = result["reason_changes"][0]
    assert change["function"] == NAME + ":pending"
    assert change["old_reason"] == "unsupported struct_expression"
    assert change["new_reason"] == "Unsupported control flow: assembly_statement"
    assert change["old_facts"] == change["new_facts"] == 0
    assert change["partial_facts_published"] is False


@pytest.mark.parametrize("mutation", [
    "fact_count", "fact", "partial", "routes", "name", "legacy_reason",
    "diagnostic_kind", "diagnostic_scope", "diagnostic_reason", "anchor",
    "extra_metadata", "supported_reason"])
def test_reason_exception_does_not_relax_other_invariants(tmp_path, mutation):
    old, new, before, after, sources = still_fallback_reason_pair(tmp_path)
    record = after["layers"]["L1"]["files"][NAME]["analysis"]["functions"][1]
    diag = after["layers"]["L1"]["files"][NAME]["diagnostics"][-1]
    if mutation == "fact_count": record["facts"] = 1
    elif mutation == "fact":
        after["layers"]["L1"]["evidence"].append(dict(source=1, target=2,
            symbol=NAME+":pending:a", function=NAME+":pending", self_fact=False))
    elif mutation == "partial": record["partial_facts_published"] = True
    elif mutation == "routes": record["routes"] = ["v2_retry"]
    elif mutation == "name": record["name"] = "renamed"
    elif mutation == "legacy_reason": record["old_reason"] = "changed"
    elif mutation == "diagnostic_kind": diag["kind"] = "other"
    elif mutation == "diagnostic_scope": diag["file"] = "other.sol"
    elif mutation == "diagnostic_reason": diag["reason"] = "does not match record"
    elif mutation == "anchor":
        after["layers"]["L1"]["files"][NAME]["anchors"].append(
            dict(span("return x + msg.sender;"), node_id=3))
    elif mutation == "extra_metadata": record["new_field"] = True
    elif mutation == "supported_reason":
        after["layers"]["L1"]["files"][NAME]["analysis"]["functions"][0]["reason"] = "changed"
    with pytest.raises(ValueError):
        compare((old, new, before, after, sources))
