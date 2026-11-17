"""Validate the authorized CP3 acquisition checkpoint without continuing classification."""
import gzip, hashlib, json, os, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
def sha(path):
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for raw in iter(lambda:f.read(1048576),b""):digest.update(raw)
    return digest.hexdigest()
def write(name,value):
    with (OUT/name).open("x",encoding="utf8") as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2);f.write("\n")
def audit():
    """Check immutable predecessors, environments, source bytes and documentation history."""
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    current=json.loads((OUT/"baseline.json").read_text())
    baseline_path=ROOT/current["preflight_baseline_path"]
    assert sha(baseline_path)==current["preflight_baseline_sha256"]
    before=json.loads(baseline_path.read_text())
    previous=ROOT/"compile_repair/artifacts/cp3_preflight_v1/delivery_inventory.json"
    assert sha(previous)==current["preflight_inventory_sha256"]
    inventory=json.loads(previous.read_text())
    allowed=set(current["docs"])
    protected={p:h for p,h in before["tracked"].items() if p not in allowed}
    protected.update({p:v["sha256"] for p,v in inventory["files"].items() if p not in allowed})
    protected[inventory["self"]]=current["preflight_inventory_sha256"]
    changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    ref=before["old_sealed_reference"]
    assert sha(ROOT/ref["path"])==ref["sha256"]
    sealed=json.loads((ROOT/ref["path"]).read_text())["old_sealed"]
    old_changes=[p for p,h in sealed.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    envs={}
    for name in before["environment"]:
        base=Path("/home/zhao/miniconda3/envs")/name
        files=set(base.glob("lib/python*/site-packages/*.dist-info/METADATA"))
        files.update(base.glob("conda-meta/*.json"));files.add(base/"conda-meta/history")
        envs[name]={str(p):sha(p) for p in files if p.is_file()}
    solc={str(p):sha(p) for p in (Path.home()/".solc-select").rglob("*") if p.is_file()}
    module=ROOT/"compile_repair"
    paths=list(module.glob("*.py"))+[p for d in module.iterdir() if d.is_dir() and d.name not in ("tests","docs","artifacts") for p in d.rglob("*.py")]
    implementation={str(p.relative_to(ROOT)):sha(p) for p in paths}
    history={}
    for name in allowed:
        old=subprocess.check_output(["git","show",current["head"]+":"+name],cwd=str(ROOT))
        now=(ROOT/name).read_bytes()
        if name.endswith("HANDOVER.md"):
            marker=b"## 6. ";history[name]=now[now.index(marker):].startswith(old[old.index(marker):])
        elif name.endswith("DECISIONS.md"):
            marker=b"## 2. ";history[name]=now[:now.index(marker)].startswith(old[:old.index(marker)]) and now[now.index(marker):].startswith(old[old.index(marker):])
        else:history[name]=now.startswith(old)
    external_count=0;external_changes=[]
    for manifest in sorted((OUT/"acquisition").glob("*/manifest.jsonl.gz")):
        with gzip.open(manifest,"rt",encoding="utf8") as f:
            for line in f:
                row=json.loads(line);p=Path(row["absolute_path"]);external_count+=1
                if not p.is_file() or sha(p)!=row["sha256"]:external_changes.append(str(p))
    docs=json.loads((OUT/"document_manifest.json").read_text())["files"]
    document_changes=[r["destination"] for r in docs if sha(Path(r["destination"]))!=r["sha256"]]
    tracked_changes=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT)).decode().splitlines()
    taxonomy=json.loads((OUT/"taxonomy_initial_receipt.json").read_text())
    result=dict(protected_tracked=len(protected),protected_tracked_changes=changed,
        outside_module_files=sum(not p.startswith("compile_repair/") for p in protected),
        old_artifact_files=sum(p.startswith("compile_repair/artifacts/") for p in protected),
        old_sealed_files=len(sealed),old_sealed_changes=old_changes,
        environment_equal=envs==before["environment"],environment_counts={k:len(v) for k,v in envs.items()},
        solc_equal=solc==before["solc"],solc_files=len(solc),code_refs_equal=_code_refs()==before["code_refs"],
        code_refs_count=len(before["code_refs"]),implementation_unchanged=implementation==before["implementation_sha256"],
        production_file_count=len(implementation),documentation_history_preserved=history,
        unexpected_tracked_changes=[p for p in tracked_changes if p not in allowed],
        selection_environment_equal={k:os.environ.get(k) for k in before["selection_environment"]}==before["selection_environment"],
        acquired_corpus_files=external_count,acquired_corpus_changes=external_changes,
        acquired_documents=len(docs),acquired_document_changes=document_changes,
        taxonomy_initial_bytes_preserved=sha(OUT/"taxonomy.json")==taxonomy["taxonomy_sha256"],
        authorization_sha256=sha(OUT/"authorization.json"),llm_calls=0,cost_usd=0,
        structure_mismatch_still_unresolved=True)
    result["passed"]=(not changed and not old_changes and not external_changes and not document_changes
        and not result["unexpected_tracked_changes"] and all(history.values())
        and len(implementation)<=30 and all(result[k] for k in ("environment_equal","solc_equal",
            "code_refs_equal","implementation_unchanged","selection_environment_equal","taxonomy_initial_bytes_preserved")))
    write("frozen_audit.json",result);print(json.dumps(result,ensure_ascii=False),flush=True)
    if not result["passed"]:raise SystemExit(2)
def docs():
    """Check all six new or changed Markdown documents with frozen doc_check."""
    version=sys.argv[2]
    if version not in ("v1","v2"):raise ValueError("fresh named receipt required")
    before=json.loads((OUT/"baseline.json").read_text())
    targets=[p+":"+str(before["docs"][p]) for p in ("compile_repair/PROGRESS.md","compile_repair/docs/CHANGE_LOG.md","compile_repair/CP3_REPORT.md")]
    targets+=["compile_repair/docs/HANDOVER.md","compile_repair/docs/DECISIONS.md","compile_repair/artifacts/cp3_v1/README.md"]
    command=[sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+targets
    start=time.monotonic();run=subprocess.run(command,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    rows=[json.loads(line) for line in run.stdout.decode("utf8").splitlines() if line.strip()]
    passed=run.returncode==0 and len(rows)==len(targets) and all(r["passed"] for r in rows)
    with (OUT/("doc_check_"+version+".jsonl")).open("xb") as f:f.write(run.stdout)
    receipt=dict(command=command,cwd=str(ROOT),returncode=run.returncode,all_passed=passed,rows=len(rows),
        elapsed_seconds=time.monotonic()-start,stdout_sha256=hashlib.sha256(run.stdout).hexdigest(),
        stderr=run.stderr.decode("utf8"),document_sha256={p.split(":")[0]:sha(ROOT/p.split(":")[0]) for p in targets})
    write("doc_check_"+version+"_invocation.json",receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)
    if not passed:raise SystemExit(2)
if __name__=="__main__":{"audit":audit,"docs":docs}[sys.argv[1]]()
