"""CP3 preflight documentation and integrity checks; never download resources."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for raw in iter(lambda: stream.read(1048576), b""):
            value.update(raw)
    return value.hexdigest()

def write(name, value):
    with (OUT / name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")

def audit():
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    before = json.loads((OUT / "baseline.json").read_text())
    allowed = set(before["docs"])
    protected = {p:h for p,h in before["tracked"].items() if p not in allowed}
    changed = [p for p,h in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p) != h]
    ref = before["old_sealed_reference"]
    assert sha(ROOT/ref["path"]) == ref["sha256"]
    sealed = json.loads((ROOT/ref["path"]).read_text())["old_sealed"]
    sealed_changes = [p for p,h in sealed.items() if not (ROOT/p).is_file() or sha(ROOT/p) != h]
    envs = {}
    for name in before["environment"]:
        base = Path("/home/zhao/miniconda3/envs") / name
        paths = set(base.glob("lib/python*/site-packages/*.dist-info/METADATA"))
        paths.update(base.glob("conda-meta/*.json"))
        paths.add(base / "conda-meta/history")
        envs[name] = {str(p):sha(p) for p in paths if p.is_file()}
    solc = {str(p):sha(p) for p in (Path.home()/".solc-select").rglob("*") if p.is_file()}
    module = ROOT/"compile_repair"
    paths = list(module.glob("*.py")) + [p for d in module.iterdir()
        if d.is_dir() and d.name not in ("tests", "docs", "artifacts")
        for p in d.rglob("*.py")]
    implementation = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    history = {}
    for path in allowed:
        old = subprocess.check_output(["git","show",before["head"]+":"+path],cwd=str(ROOT))
        current = (ROOT/path).read_bytes()
        if path.endswith("HANDOVER.md"):
            marker = b"## 6. "
            history[path] = current[current.index(marker):].startswith(old[old.index(marker):])
        else:
            history[path] = current.startswith(old)
    tracked_changes = subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT)).decode().splitlines()
    result = dict(protected_tracked=len(protected), protected_tracked_changes=changed,
        outside_module_files=sum(not p.startswith("compile_repair/") for p in protected),
        old_artifact_files=sum(p.startswith("compile_repair/artifacts/") for p in protected),
        old_sealed_files=len(sealed),old_sealed_changes=sealed_changes,
        environment_equal=envs==before["environment"],environment_counts={k:len(v) for k,v in envs.items()},
        solc_equal=solc==before["solc"],solc_files=len(solc),
        code_refs_equal=_code_refs()==before["code_refs"],code_refs_count=len(before["code_refs"]),
        implementation_unchanged=implementation==before["implementation_sha256"],
        production_file_count=len(implementation),documentation_history_preserved=history,
        unexpected_tracked_changes=[p for p in tracked_changes if p not in allowed],
        selection_environment_equal={k:os.environ.get(k) for k in before["selection_environment"]}==before["selection_environment"],
        external_content_downloads=0,llm_calls=0,cost_usd=0)
    result["passed"] = (not changed and not sealed_changes and not result["unexpected_tracked_changes"]
        and all(history.values()) and len(implementation)<=30
        and all(result[k] for k in ("environment_equal","solc_equal","code_refs_equal",
            "implementation_unchanged","selection_environment_equal")))
    write("frozen_audit.json",result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if not result["passed"]:
        raise SystemExit(2)

def docs():
    version=sys.argv[2]
    if version not in ("v1", "v2"):
        raise ValueError("Use a named fresh receipt")
    before=json.loads((OUT/"baseline.json").read_text())
    targets=[p+":"+str(before["docs"][p]) for p in (
        "compile_repair/PROGRESS.md","compile_repair/docs/CHANGE_LOG.md")]
    targets += ["compile_repair/docs/HANDOVER.md","compile_repair/CP3_REPORT.md",
        "compile_repair/artifacts/cp3_preflight_v1/README.md"]
    command=[sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+targets
    start=time.monotonic()
    result=subprocess.run(command,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    rows=[json.loads(line) for line in result.stdout.decode("utf8").splitlines() if line.strip()]
    passed=result.returncode==0 and len(rows)==len(targets) and all(row["passed"] for row in rows)
    with (OUT/("doc_check_"+version+".jsonl")).open("xb") as stream:
        stream.write(result.stdout)
    receipt=dict(command=command,cwd=str(ROOT),returncode=result.returncode,all_passed=passed,
        rows=len(rows),elapsed_seconds=time.monotonic()-start,stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
        stderr=result.stderr.decode("utf8"),
        document_sha256={p.split(":")[0]:sha(ROOT/p.split(":")[0]) for p in targets})
    write("doc_check_"+version+"_invocation.json",receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)
    if not passed:
        raise SystemExit(2)

if __name__=="__main__":
    {"audit":audit,"docs":docs}[sys.argv[1]]()
