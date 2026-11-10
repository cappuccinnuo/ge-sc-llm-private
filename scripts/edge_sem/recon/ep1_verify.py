"""Read-only EP1 archive, input and acceptance verification."""
import hashlib
import re
import subprocess
import torch
from .common import ROOT,read,ref,checked,write
from .ep1_common import OUT


def verify():
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.node_sem.doc_check import check
    before,summary=read(OUT/"before.json"),read(OUT/"summary.json")
    assert _code_refs()==before["dfg_code_refs"]
    for entry in before["frozen_code"]+before["prior_edge_sources"]+before["prior_artifacts"]:
        checked(entry)
    for name in ("plan","seal","prompt","historical_verification"):
        checked(before[name])
    for item in before["authorized_source_changes"]:
        checked(item["snapshot"])
        assert item["snapshot"]["sha256"]==item["original"]["sha256"]
    assert summary["head"]==before["head"] and summary["prompt"]==before["prompt"]
    load(before["plan"]["path"])
    previous=read(ROOT/"scripts/edge_sem/artifacts/ep0b_v1/verification.json")
    for entry in previous["input_refs"]:
        checked(entry)
    for entry in summary["source_refs"]+summary["evidence_refs"]:
        checked(entry)
    audit=read(OUT/"audit_plan.json")
    for entry in audit["sources"]:
        checked(entry)
    assert not audit["training_executed"] and audit["optimizer_steps"]==0 and not audit["gpu_executed"]
    assert not summary["training_executed"] and not summary["gpu_executed"]
    assert summary["optimizer_steps"]==0 and summary["graphs_written"]==0 and not summary["cf_back"]
    assert summary["stop_after"]=="EP1" and not summary["ep2_r8_decisions_authorized"]
    old_gate=read(ROOT/"scripts/edge_sem/artifacts/ep0e_v1/summary.json")
    assert old_gate["gate_pass"] is False
    assert all(s["matched_calls"]==312 and s["candidate_calls"]==347 for s in old_gate["using_summaries"].values())
    cases=summary["probes"]
    assert {(r["task_id"],r["profile"],r["fold"]) for r in cases}=={
        ("reentrancy_node","G3R",0),("reentrancy_node","G3R",9),
        ("reentrancy_node","G3R-T",0),("access_control_node","G3R-T",0)}
    assert len(cases)==4
    inputs=read(ROOT/"scripts/edge_sem/artifacts/ep0_v1/inputs.json")
    first=read(ROOT/"scripts/edge_sem/artifacts/ep0_v1/cpu_A.json")
    for row in cases:
        task=inputs["tasks"][row["task_id"]]
        assert row["source_graph"]==task["graph_refs"]["F3"] and row["feature_view"]==task["feature_view"]
        assert row["config"]==task["config"] and row["graph_unchanged"]
        checked(row["source_graph"])
        assert row["construction_seconds"]>=0 and row["optimizer_steps"]==0 and not row["cuda_initialized"]
        if row["profile"]=="G3R":
            assert row["canonical_count"]==212 and row["parameter_count"]==5111012
            assert row["forward_bitwise_equal"] and row["all_parameters_equal"] and row["endpoints_equal"]
            assert row["seed"]==10000+row["fold"] and row["max_abs"]==0
            if row["fold"]==0:
                assert row["state_digest"]==first["anchor_state_digest"]
        else:
            counts=read(ROOT/("scripts/edge_sem/artifacts/ep0_v1/"+row["task_id"]+".json"))["graph_counts"]
            assert row["relations"]==counts["typed"]
            assert row["canonical_count"]==len(counts["typed"])
            assert row["sparse_relations"]==[r for r in counts["typed"] if r["edges"]<20]
            assert row["copied_rows"]==[row["canonical_count"]]*row["config"]["layers"]
            assert row["forward_backward_finite"]
            # All node-specific banks unchanged; only canonical banks vary.
            expected=5111012+2*(row["canonical_count"]-212)*(2*8*16*16+8)
            # Tasks may differ in node types: do not infer across task schemas.
            if row["task_id"]=="reentrancy_node":assert row["parameter_count"]==expected
    total=0
    for name,item in summary["tests"].items():
        receipt=read(checked(item["receipt"]))
        assert receipt["exit_code"]==0
        assert re.findall(r"(?m)^(\d+) passed",checked(receipt["log"]).read_text())==[str(item["passed"])]
        total+=item["passed"]
    assert total==summary["test_total"] and summary["gate_pass"]
    documents=[]
    for name,original in before["documents"].items():
        data=(ROOT/name).read_bytes()
        assert hashlib.sha256(data[:original["bytes"]]).hexdigest()==original["sha256"]
        documents.append(check(ROOT/name,original["bytes"],expect_cjk=True))
    documents.append(check(ROOT/"scripts/edge_sem/EP1_REPORT.md",expect_cjk=True))
    receipt=read(OUT/"execution/doc_check.json")
    assert receipt["exit_code"]==0
    checked(receipt["log"])
    changed=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT),text=True).splitlines()
    assert all(n in before["documents"] or n.startswith("scripts/edge_sem/") for n in changed)
    subprocess.run(["git","diff","--check"],cwd=str(ROOT),check=True)
    assert not torch.cuda.is_initialized()
    write(OUT/"verification.json",dict(passed=True,gate_pass=True,training_executed=False,cuda_initialized=False,
        frozen_code_count=len(before["frozen_code"]),dfg_code_refs_count=len(before["dfg_code_refs"]),
        prior_edge_source_count=len(before["prior_edge_sources"]),prior_artifact_count=len(before["prior_artifacts"]),
        input_reference_count=len(previous["input_refs"]),historical_8h_load=True,
        test_total=total,probe_count=len(cases),documents=documents,
        report=ref(ROOT/"scripts/edge_sem/EP1_REPORT.md"),summary=ref(OUT/"summary.json"),
        historical_ep0e_gate_pass=False,ep2_not_started=True))
    print("EP1 verified:",total,"tests; four CPU acceptance probes; historical files unchanged",flush=True)


if __name__=="__main__":
    verify()
