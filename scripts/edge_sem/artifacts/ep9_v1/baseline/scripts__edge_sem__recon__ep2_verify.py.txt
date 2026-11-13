"""Read-only EP2 artifact, identity, input and archive verification."""
import hashlib
import re
import subprocess
from collections import Counter,defaultdict
import torch
from .common import ROOT,read,ref,checked,write,key
from .ep2_common import OUT,TASKS,contexts,file_views
from scripts.edge_sem.build_f4 import load_edges,add_edges
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint


def verify():
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.node_sem.doc_check import check
    before=read(OUT/"before.json");summary=read(OUT/"summary.json")
    assert _code_refs()==before["dfg_code_refs"]
    for r in before["frozen_code"]+before["prior_edge_sources"]+before["prior_artifacts"]:checked(r)
    for name in ("plan","seal","prompt","historical_verification"):checked(before[name])
    for r in before["authorized_source_changes"]:
        checked(r["snapshot"]);assert r["snapshot"]["sha256"]==r["original"]["sha256"]
    load(before["plan"]["path"])
    original=read(ROOT/"scripts/edge_sem/artifacts/ep0b_v1/verification.json")
    for r in original["input_refs"]:checked(r)
    for r in summary["source_refs"]+summary["evidence_refs"]:checked(r)
    assert summary["gate_pass"] and summary["historical_ep0e_gate_pass"] is False
    assert read(ROOT/"scripts/edge_sem/artifacts/ep0e_v1/summary.json")["gate_pass"] is False
    assert not summary["training_executed"] and not summary["gpu_executed"]
    assert summary["graphs_written"]==summary["optimizer_steps"]==0 and not summary["ep3_started"]
    details={}
    for task in TASKS:
        context=contexts(task);graph=context["graphs"]["F3"];fp=graph_fingerprint(graph)
        manifest=read(OUT/task/"manifest.json")
        rows=load_edges(OUT/task/"manifest.json")
        audit=read(checked(manifest["audit"]));fix=read(OUT/"call_fix"/(task+".json"))
        assert manifest["original_fingerprint"]==fp and manifest["source_view"]=="original"
        assert {r["file"] for r in audit["files"]}==set(context["sources"])
        assert len(audit["files"])==len(context["sources"])
        assert all(r["relation"] in ("MOD_APPLY","CALL_SITE") for r in rows)
        assert len({(r["relation"],r["src"],r["dst"]) for r in rows})==len(rows)
        projected={(r["source_node"],r["target_node"]) for r in fix["sites"] if r["projected"]}
        assert {(r["src"],r["dst"]) for r in rows if r["relation"]=="CALL_SITE"}==projected
        by_file=defaultdict(list)
        for row in rows:by_file[row["file"]].append(row)
        audit_files={r["file"]:r for r in audit["files"]}
        anchors_checked=0
        for file,source,sub,sem,raw,inverse in file_views(context):
            events=audit_files[file]["events"]
            calls={(tuple(e["owner_anchor"]),tuple(e["target_anchor"]),tuple(e["anchor"])):e
                   for e in events if e["relation"]=="CALL_SITE" and e["outcome"] in ("emitted","duplicate")}
            mods={(tuple(e["owner_anchor"]),tuple(e["target_anchor"]),tuple(e["anchor"])):e
                  for e in events if e["relation"]=="MOD_APPLY" and e["outcome"] in ("emitted","duplicate")}
            covered_calls=set();covered_mods=set()
            for row in by_file[file]:
                assert row["source_sha256"]==context["sources"][file]["sha256"]
                assert inverse[tuple(row["src_anchor"])]==row["src"]
                assert inverse[tuple(row["dst_anchor"])]==row["dst"]
                assert row["src"]!=row["dst"]
                assert row["rule"]==("E1-MOD-1" if row["relation"]=="MOD_APPLY" else "E1-CALL-1")
                for evidence in row["evidence"]:
                    anchor=evidence["call_anchor"] if row["relation"]=="CALL_SITE" else evidence["invocation_anchor"]
                    ident=(tuple(row["src_anchor"]),tuple(row["dst_anchor"]),tuple(anchor))
                    if row["relation"]=="CALL_SITE":
                        assert ident in calls and evidence["kind"]==row["kind"]==calls[ident]["kind"]
                        assert evidence["reason"]==calls[ident]["reason"];covered_calls.add(ident)
                    else:
                        assert ident in mods and evidence["reason"]==mods[ident]["reason"];covered_mods.add(ident)
                anchors_checked+=2
            assert covered_calls==set(calls) and covered_mods==set(mods)
        assert graph_fingerprint(graph)==fp
        enriched=add_edges(graph,rows)
        assert graph_fingerprint(graph)==fp and list(enriched)==list(graph)
        # Prove the old keyed subgraph (including all attributes) survives.
        restored=enriched.copy()
        new_edges=[(a,b,k) for a,b,k,d in enriched.edges(keys=True,data=True)
                   if d.get("edge_type") in ("MOD_APPLY","CALL_SITE")]
        assert len(new_edges)==len(rows)
        restored.remove_edges_from(new_edges)
        assert graph_fingerprint(restored)==fp
        for entry in context["provenance"]["graphs"].values():checked(entry)
        count=Counter();status=Counter();reason=Counter()
        for f in audit["files"]:
            count.update(f["counts"]);status.update(f["statuses"]);reason.update(f["reasons"])
        assert dict(count)==audit["counts"] and dict(status)==audit["statuses"] and dict(reason)==audit["reasons"]
        assert manifest["counts_by_relation"]==dict(Counter(r["relation"] for r in rows))
        assert fix["summary"]["hard_conditions_pass"]
        assert all(r["equal"] for r in fix["prior_resolved_comparisons"])
        assert not any(r["outside_candidate"] for r in fix["using_candidates"])
        cs=[r for r in fix["using_candidates"] if r["candidate"]]
        assert len(cs)==347 and sum(r["matched"] for r in cs)==334
        assert len(fix["added_bindings"])==22
        build_started=read(OUT/"execution"/("build_"+task+".started.json"))["started"]
        for t in TASKS:
            started=read(OUT/"execution"/("call_fix_"+t+".started.json"))["started"]
            run=read(OUT/"execution"/("call_fix_"+t+".json"))
            assert run["exit_code"]==0 and started+run["seconds"]<=build_started
        probe=summary["tasks"][task]["probe"]
        assert probe["edge_rows"]==len(rows) and probe["optimizer_steps"]==0 and not probe["cuda_initialized"]
        for flag in ("empty_matches_typed_bitwise","forward_backward_finite","common_parameters_equal",
                     "new_rows_match_relation_seed","repeated_initialization_equal","graph_unchanged","source_file_unchanged"):
            assert probe[flag]
        details[task]=dict(files=len(audit["files"]),edges=len(rows),endpoint_anchors_checked=anchors_checked,
                          original_graph_preserved=True,call_fix_preceded_build=True)
        del graph,enriched,restored,context
    total=0
    for name,row in summary["tests"].items():
        r=read(checked(row["receipt"]));assert r["exit_code"]==0
        assert re.findall(r"(?m)^(\d+) passed",checked(r["log"]).read_text())==[str(row["passed"])]
        total+=row["passed"]
    assert total==summary["test_total"]
    docs=[]
    for name,r in before["documents"].items():
        data=(ROOT/name).read_bytes()
        assert hashlib.sha256(data[:r["bytes"]]).hexdigest()==r["sha256"]
        docs.append(check(ROOT/name,r["bytes"],expect_cjk=True))
    docs.append(check(ROOT/"scripts/edge_sem/EP2_REPORT.md",expect_cjk=True))
    docs.append(check(OUT/"call_fix/REPORT.md",expect_cjk=True))
    r=read(OUT/"execution/doc_check.json");assert r["exit_code"]==0;checked(r["log"])
    changed=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT),text=True).splitlines()
    assert all(n in before["documents"] or n.startswith("scripts/edge_sem/") for n in changed)
    subprocess.run(["git","diff","--check"],cwd=str(ROOT),check=True)
    assert not torch.cuda.is_initialized()
    write(OUT/"verification.json",dict(passed=True,gate_pass=True,historical_ep0e_gate_pass=False,
        frozen_code_count=len(before["frozen_code"]),dfg_code_refs_count=len(before["dfg_code_refs"]),
        prior_edge_source_count=len(before["prior_edge_sources"]),prior_artifact_count=len(before["prior_artifacts"]),
        input_reference_count=len(original["input_refs"]),historical_8h_load=True,
        tasks=details,test_total=total,documents=docs,report=ref(ROOT/"scripts/edge_sem/EP2_REPORT.md"),
        summary=ref(OUT/"summary.json"),training_executed=False,cuda_initialized=False,ep3_not_started=True))
    print("EP2 verified:",total,"tests; exact edge provenance and historical files preserved",flush=True)


if __name__=="__main__":verify()
