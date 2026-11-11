"""Independent EP5 artifact/integrity acceptance; no fitting or GPU access."""
import hashlib
import json
import subprocess
from collections import Counter
import numpy as np
from .common import ROOT,ref,read,checked,write
from .ep5_common import OUT,TASKS
from .ep5_delta import archived,hard_delta
from scripts.edge_sem.attrs import edge_rows,endpoint_test,select_groups
from scripts.edge_sem.attr_batch import load_attributes,numeric_digest
from scripts.edge_sem.build_f4 import load_edges
from scripts.edge_sem.placebo import degree_signature
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint


def verify():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.node_sem.facts_io import load_context
    from scripts.node_sem.doc_check import check
    before=read(OUT/"before.json")
    for r in before["frozen_code"]+before["prior_artifacts"]+before["prior_edge_sources"]:checked(r)
    for name in ("prompt","plan","seal","historical_verification"):checked(before[name])
    for r in before["authorized_source_changes"]:
        assert r["original"]["sha256"]==r["snapshot"]["sha256"]
        checked(r["snapshot"])
    assert _code_refs()==before["dfg_code_refs"]
    load(before["plan"]["path"])
    summary=read(OUT/"summary.json")
    for r in summary["checks"].values():checked(r)
    anon=read(checked(summary["checks"]["anonymous"]))
    assert anon["passed"] and sum(anon["counts"].values())==128
    for r in anon["implementation"]:checked(r)
    anonymous_rows=[read(checked(r)) for r in anon["files"]]
    topology=read(checked(summary["checks"]["topology"]))
    assert topology["passed"] and topology["total_cases"]==21
    for r in topology["implementation"]:checked(r)
    cases=read(checked(topology["cases"]))
    reach=read(checked(topology["reachability"]))
    checked(topology["table"])
    assert {(c["task_id"],c["original_graph_node_id"]) for c in cases}=={
        (c["task_id"],c["original_graph_node_id"]) for c in reach}
    assert topology["any_case_gains_evidence"]==any(c["delta_total_unique"]>0 for c in reach)
    loop=read(OUT/"loop_context_audit.json")
    assert read(OUT/"loop_context_decision.json")["approved"]
    results={};endpoints={}
    for task in TASKS:
        ctx=load_context(task);graph=ctx["graphs"]["F3"];fp=graph_fingerprint(graph)
        path=OUT/"attributes"/task/"manifest.json";manifest=read(path)
        edges=load_edges(checked(manifest["f4_manifest"]))
        values=load_attributes(path,graph,edges);keys=list(values);new=np.stack(list(values.values()))
        _,old_keys,old=archived(task)
        hard_delta(old_keys,old,keys,new)
        rows=edge_rows(graph,edges);row_by_key={r["key"]:r for r in rows}
        endpoints[task]=endpoint_test(values,edges,graph)
        assert json.loads(json.dumps(endpoints[task]))==read(OUT/"attributes"/task/"endpoint_test.json")
        flagged={r["key"] for r in rows if values[r["key"]][20] and not values[r["key"]][59]}
        assert flagged=={r["edge_key"] for r in loop[task]["rows"]}
        assert loop[task]["all_loop_headers"]
        task_rows=[r for r in anonymous_rows if r["task_id"]==task]
        assert {r["file"] for r in task_rows}==set(ctx["sources"]) and len(task_rows)==len(ctx["sources"])
        for r in task_rows:
            assert r["passed"] and r["attribute_keys_equal"] and not r["attribute_differences"]
            assert r["old_new_edges_equal"] and not r["missing_edges"] and not r["added_edges"]
            assert r["source"]==ctx["sources"][r["file"]]
            checked(r["source"])
            file_keys=[x["key"] for x in rows if x["file"]==r["file"]]
            assert len(file_keys)==r["input_edges"]
            actual=numeric_digest(file_keys,np.stack([values[k] for k in file_keys])) if file_keys else None
            assert actual==r["original_numeric_digest"]
            if r["status"]=="fallback":
                assert r["renamed_sha256"]==r["source"]["sha256"] and not r["translation_proof"]
        item=topology["tasks"][task]
        for name in ("graph_statistics","attributes","evidence","placebo_audit","permutation"):checked(item[name])
        stats=read(item["graph_statistics"]["path"])
        folder=checked(item["graph_statistics"]).parent
        randomized=read(folder/"placebo_edges.json")
        assert degree_signature(graph,randomized)==degree_signature(graph,edges)
        assert stats["G4R"]["edges"]==stats["G3R-T"]["edges"]+2*len(edges)
        assert stats["G4R"]==stats["G4R-P"]
        perm=read(checked(item["permutation"]));audit=read(checked(perm["audit"]))
        with np.load(checked(perm["output"]),allow_pickle=False) as data:
            shuffled_keys=data["edge_keys"].tolist();shuffled=data["attrs"].copy()
        assert shuffled_keys==keys and numeric_digest(keys,shuffled)==perm["numeric_digest"]
        assert set(audit["source_key_for_target"])==set(keys)
        for i,k in enumerate(keys):
            source=audit["source_key_for_target"][k]
            assert row_by_key[k]["relation"]==row_by_key[source]["relation"]
            assert np.array_equal(shuffled[i],values[source])
        for rel in {r["relation"] for r in rows}:
            indices=[i for i,r in enumerate(rows) if r["relation"]==rel]
            assert Counter(new[i].tobytes() for i in indices)==Counter(shuffled[i].tobytes() for i in indices)
        assert graph_fingerprint(graph)==fp
        results[task]=dict(attribute_rows=len(rows),loop_carried=int(new[:,20].sum()),
            loop_header_exceptions=len(flagged),anonymous_files=len(task_rows),
            original_graph_unchanged=True,placebo_degrees_exact=True,permutation_multisets_exact=True)
    selection=read(OUT/"attributes/selection.json")
    assert {k:v for k,v in selection.items() if k!="per_task"}==json.loads(json.dumps(select_groups(endpoints)))
    for name in ("edge_tests","nodesem_tests","dfg_tests"):
        receipt=read(OUT/"execution"/(name+".json"))
        assert receipt["exit_code"]==0
        checked(receipt["log"])
    for name,record in before["documents"].items():
        data=(ROOT/name).read_bytes()
        assert hashlib.sha256(data[:record["bytes"]]).hexdigest()==record["sha256"]
        assert check(ROOT/name,since_bytes=record["bytes"],expect_cjk=True)["passed"]
    assert check(ROOT/"scripts/edge_sem/EP5_REPORT.md",expect_cjk=True)["passed"]
    changed=subprocess.check_output(["git","diff","--name-only"],cwd=str(ROOT),text=True).splitlines()
    assert all(p.startswith("scripts/edge_sem/") or p in before["documents"] for p in changed)
    write(OUT/"verification.json",dict(passed=True,tasks=results,
        frozen_source_count=len(before["frozen_code"]),dfg_code_refs=len(before["dfg_code_refs"]),
        prior_artifact_count=len(before["prior_artifacts"]),prior_edge_source_count=len(before["prior_edge_sources"]),
        documents_prefix_unchanged=True,frozen_8h_load=True,code_refs_unchanged=True,
        summary=ref(OUT/"summary.json"),training_executed=False,gpu_executed=False))
    print("EP5 immutable archive, matrix, anonymization, case and placebo acceptance passed",flush=True)
if __name__=="__main__":verify()
