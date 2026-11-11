"""EP6 final input, archive, result and append-only documentation verification."""
import hashlib
import json
import re
import subprocess
import numpy as np
from .common import ROOT, read, checked, ref, write
from .ep6_common import OUT, TASKS
from .ep6_prereq import historical_manifest,strict_delta,OLD
from scripts.edge_sem.attr_batch import load_attributes,numeric_digest
from scripts.edge_sem.attrs import edge_rows,endpoint_test,select_groups
from scripts.edge_sem.build_f4 import load_edges
from scripts.node_sem.facts_io import load_context

def main(summary_path=None, receipt_path=None):
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.node_sem.doc_check import check
    before=read(OUT/"before.json")
    amendments=[read(OUT/n) for n in ("additional_source_changes.json","archive_source_change.json")]
    exceptions={r["original"]["path"] for a in amendments for r in a["changes"]}
    for r in before["frozen_code"]+before["prior_artifacts"]:checked(r)
    for r in before["edge_sources"]:
        if r["path"] not in exceptions:checked(r)
    for item in before["authorized_source_changes"]+[r for a in amendments for r in a["changes"]]:
        if item["original"]["sha256"]!=item["snapshot"]["sha256"]:raise ValueError("Baseline snapshot mismatch")
        checked(item["snapshot"])
    checked(before["prompt"]);checked(before["plan"])
    if _code_refs()!=before["dfg_code_refs"]:raise ValueError("Frozen DFG code refs differ")
    load(before["plan"]["path"])
    summary=read(summary_path or OUT/"summary.json")
    for k in ("report","before","decisions","cpu"):checked(summary[k])
    for r in summary["checks"].values():checked(r)
    prereq=read(OUT/"prerequisites.json")
    if not prereq["passed"]:raise ValueError("Prerequisite gate failed")
    for r in prereq["checks"].values():checked(r)
    anon=read(OUT/"anonymous_gate/summary.json")
    if not anon["passed"]:raise ValueError("Anonymous gate failed")
    for r in anon["implementation"]:checked(r)
    records=[read(checked(r)) for r in anon["files"]]
    if len(records)!=128:raise ValueError("Anonymous population differs")
    results={};endpoints={}
    for task in TASKS:
        ctx=load_context(task);graph=ctx["graphs"]["F3"]
        path=OUT/"attributes"/task/"manifest.json";m=read(path)
        edges=load_edges(checked(m["f4_manifest"]));values=load_attributes(path,graph,edges)
        rows=edge_rows(graph,edges)
        old=historical_manifest(OLD/task/"manifest.json",True)
        with np.load(checked(old["attrs"]),allow_pickle=False) as data:
            oldkeys=data["edge_keys"].tolist();oldmatrix=data["attrs"].copy()
        gaps={r["edge_key"] for r in read(checked(old["diagnostics"]))["edges"]
              if "no_exact_dfg_to_for_this_edge" in r["source_gaps"]}
        verified=strict_delta(oldkeys,oldmatrix,list(values),np.stack(list(values.values())),gaps,[r["relation"] for r in rows])
        if verified!=read(OUT/"attribute_delta.json")["tasks"][task]["delta"]:raise ValueError("Delta summary differs")
        endpoints[task]=endpoint_test(values,edges,graph)
        if json.loads(json.dumps(endpoints[task]))!=read(OUT/"attributes"/task/"endpoint_test.json"):
            raise ValueError("Endpoint selection measurements differ")
        task_rows=[r for r in records if r["task_id"]==task]
        if {r["file"] for r in task_rows}!=set(ctx["sources"]):raise ValueError("Anonymous file population differs")
        for r in task_rows:
            if not r["passed"] or r["attribute_differences"] or not r["old_new_edges_equal"]:
                raise ValueError("Failed anonymous row")
            if r["source"]!=ctx["sources"][r["file"]]:raise ValueError("Anonymous source identity differs")
            checked(r["source"])
            sub=graph.subgraph([n for n,a in graph.nodes(data=True) if a["source_file"]==r["file"]]).copy()
            keys=[v["key"] for v in edge_rows(sub,[e for e in edges if e["file"]==r["file"]])]
            digest=numeric_digest(keys,np.stack([values[k] for k in keys])) if keys else None
            if digest!=r["original_numeric_digest"] or len(keys)!=r["input_edges"]:
                raise ValueError("Per-file attribute digest differs")
        results[task]=dict(edge_rows=len(rows),anonymous_files=len(task_rows),delta=verified)
    selection=read(OUT/"attributes/selection.json")
    if {k:v for k,v in selection.items() if k!="per_task"}!=json.loads(json.dumps(select_groups(endpoints))):
        raise ValueError("Selection differs")
    history=read(OUT/"compiler_history.json")
    for name in ("versions","versions_seal","report","report_seal"):checked(history[name])
    # All original test identities must pass, with only the identified archive
    # callers rerun after the read-only source-resolution change.
    expected={
      "scripts/edge_sem/tests/test_build_f4_guards.py::test_archived_ep2_is_explicit_and_current_loader_still_rejects["+t+"]"
      for t in TASKS} | {
      "scripts/edge_sem/tests/test_build_f4_model.py::test_real_g4r_empty_and_added_edges["+t+"]" for t in TASKS}
    first=read(OUT/"execution/edge_tests/result.json");log=checked(first["log"]).read_text()
    failures=set(re.findall(r"^FAILED (\S+)",log,re.M))
    if first["returncode"]!=1 or failures!=expected or "4 failed, 288 passed" not in log:
        raise ValueError("Unexpected original regression outcomes")
    for name,count in (("archive_recheck",6),("nodesem_tests",1353),("dfg_tests",2653)):
        result=read(OUT/"execution"/name/"result.json")
        if not result["passed"] or result["returncode"]!=0 or str(count)+" passed" not in checked(result["log"]).read_text():
            raise ValueError("Unaccepted regression: "+name)
    cpu=read(OUT/"real_cpu.json")
    if cpu["optimizer_steps"]!=0 or cpu["cuda_initialized"] or cpu["zero_initial_max_abs"]>1e-6:
        raise ValueError("CPU probe boundary differs")
    for name,r in before["documents"].items():
        payload=(ROOT/name).read_bytes()
        if hashlib.sha256(payload[:r["bytes"]]).hexdigest()!=r["sha256"]:raise ValueError("Historical prose changed")
        if not check(ROOT/name,since_bytes=r["bytes"],expect_cjk=True)["passed"]:raise ValueError("New prose encoding")
    for path in (ROOT/"scripts/edge_sem/EP6_REPORT.md",OUT/"README.md"):
        if not check(path,expect_cjk=True)["passed"]:raise ValueError("Report encoding")
    changed=subprocess.check_output(["git","diff","--name-only"],cwd=str(ROOT),text=True).splitlines()
    if any(not p.startswith("scripts/edge_sem/") and p not in before["documents"] for p in changed):
        raise ValueError("Change outside scope")
    write(receipt_path or OUT/"verification.json",dict(passed=True,tasks=results,summary=ref(summary_path or OUT/"summary.json"),
        frozen_sources=len(before["frozen_code"]),prior_artifacts=len(before["prior_artifacts"]),
        frozen_8h_load=True,code_refs_unchanged=True,document_prefixes_unchanged=True,
        cpu_only=True,all_independent_tests_passed=4300,training_executed=False,
        implementation=[ref(p) for p in sorted((ROOT/"scripts/edge_sem").rglob("*.py")) if "artifacts" not in p.parts]))
    print("EP6 final verification passed",flush=True)

if __name__=="__main__":main()
