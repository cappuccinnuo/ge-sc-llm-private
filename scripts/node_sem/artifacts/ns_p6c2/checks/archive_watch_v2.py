"""Archive only accepted NS-P6c2 code/compact results; never push or retrain."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

ROOT=Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
OUT=ROOT/"scripts/node_sem/artifacts/ns_p6c2"
os.chdir(str(ROOT))
def read(p):return json.loads(p.read_text())
def write(p,v):
    with p.open("x",encoding="utf8") as f:json.dump(v,f,ensure_ascii=False,indent=2)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
try:
    while not (OUT/"checks/completion_validation.json").exists():
        if (OUT/"checks/completion_failure.json").exists() or (OUT/"failure.json").exists():
            raise RuntimeError("Earlier calculation/report failed; archiving stopped")
        time.sleep(15)
    if not read(OUT/"checks/completion_validation.json")["passed"]:raise ValueError("Validation failed")
    plan=read(OUT/"plan.json")
    head=subprocess.check_output(["git","rev-parse","HEAD"],universal_newlines=True).strip()
    if head!=plan["head"]:raise ValueError("HEAD changed; do not mix external work")
    staged=subprocess.check_output(["git","diff","--cached","--name-only"],universal_newlines=True).strip()
    if staged:raise ValueError("Unrelated staged changes exist")
    for r in plan["sources"].values():
        if sha(r["path"])!=r["sha256"]:raise ValueError("Runtime changed")
    for r in read(OUT/"reporting_binding_v2.json")["sources"]:
        if sha(r["path"])!=r["sha256"]:raise ValueError("Reporting changed")
    for r in read(OUT/"artifact_inventory.json")["files"]:
        if sha(r["path"])!=r["sha256"]:raise ValueError("Output changed")
    files=[ROOT/n for n in ("HANDOVER.md","docs/training_changes_2026-10-07.md","scripts/node_sem/PROGRESS.md",
        "scripts/node_sem/NS_P6C2_REPORT.md","scripts/node_sem/p6c2_core.py","scripts/node_sem/p6c2_run.py",
        "scripts/node_sem/p6c2_report.py","scripts/node_sem/p6c2_finalize.py","scripts/node_sem/tests/test_p6c2.py")]
    files += [OUT/n for n in ("plan.json","plan.seal.json","doc_prefixes.json","launch.json","reporting_binding.json",
        "reporting_binding_v2.json","computation_complete.json","report.json","REPORT.md","result.seal.json","artifact_inventory.json",
        "complete.json","groups.csv","old_new.csv","paired_groups.csv","signal_summary.csv","signal_paired.csv")]
    files += sorted((OUT/"folds").glob("*/receipt.json"))
    files += sorted((OUT/"prepared").glob("*/population.json"))
    files += [OUT/"checks"/n for n in ("tests_final.json","frozen_runtime.json","doc_check.json",
        "completion_validation.json","completion_watch_binding.json","completion_watch.py",
        "archive_watch_binding.json","archive_watch.py","archive_watch_v2.py","archive_watch_revision.json","finalizer_before_inventory_fix.py","nodesem_final.log","dfgv2.log","legacy.log")]
    changed=subprocess.check_output(["git","diff","--name-only"],universal_newlines=True).splitlines()
    allowed={"HANDOVER.md","docs/training_changes_2026-10-07.md","scripts/node_sem/PROGRESS.md"}
    if set(changed)-allowed:raise ValueError("Unrelated tracked changes; archiving stopped")
    selection=dict(files=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in files],
        local_only=["per-fold result.json","control.npy","kinds.json","bits.json","signal_results.json",
                    "paired_fold_bits.csv","worker logs"],weights_included=False,
        generation_commands="scripts/node_sem/NS_P6C2_REPORT.md section 6")
    manifest=OUT/"checks/archive_selection.json";write(manifest,selection);files.append(manifest)
    rel=[str(p.relative_to(ROOT)) for p in files]
    subprocess.run(["git","add","-f","--"]+rel,check=True)
    actual=subprocess.check_output(["git","diff","--cached","--name-only"],universal_newlines=True).splitlines()
    if set(actual)!=set(rel):raise ValueError("Wrong staged file set")
    subprocess.run(["git","-c","core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
                    "diff","--cached","--check"],check=True)
    for f in rel:
        if subprocess.check_output(["git","show",":"+f])!=(ROOT/f).read_bytes():
            raise ValueError("Staged bytes differ")
    subprocess.run(["git","commit","-m","NS-P6c2: correct probe populations and add node-kind sensitivity analysis"],check=True)
    commit=subprocess.check_output(["git","rev-parse","HEAD"],universal_newlines=True).strip()
    write(OUT/"checks/commit_receipt.json",dict(commit=commit,files=len(rel),pushed=False,passed=True))
    print("NS-P6c2 local commit complete:",commit,flush=True)
except Exception:
    write(OUT/"checks/archive_failure.json",dict(error=traceback.format_exc()))
    raise
