"""Check all six CP2.4 documents using the captured pre-append byte offsets."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def execute(version):
    if version not in ("v1", "v2"):
        raise ValueError("Use a new named check receipt")
    baseline = json.loads((OUT/"baseline.json").read_text())
    appended = ["compile_repair/CP2_REPORT.md", "compile_repair/PROGRESS.md",
                "compile_repair/docs/CHANGE_LOG.md"]
    targets = [p+":"+str(baseline["docs"][p]) for p in appended]
    targets += ["compile_repair/docs/HANDOVER.md", "compile_repair/docs/DECISIONS.md",
                "compile_repair/artifacts/cp2_4_v1/README.md"]
    command = [sys.executable, "-B", "-m", "scripts.node_sem.doc_check", "--expect-cjk"] + targets
    begin = time.monotonic()
    result = subprocess.run(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rows = [json.loads(line) for line in result.stdout.decode("utf8").splitlines() if line.strip()]
    passed = result.returncode == 0 and len(rows) == len(targets) and all(row["passed"] for row in rows)
    receipt = dict(command=command, cwd=str(ROOT), returncode=result.returncode,
        all_passed=passed, rows=len(rows), elapsed_seconds=time.monotonic()-begin,
        stdout_sha256=hashlib.sha256(result.stdout).hexdigest(), stderr=result.stderr.decode("utf8"),
        document_sha256={p.split(":")[0]:hashlib.sha256((ROOT/p.split(":")[0]).read_bytes()).hexdigest() for p in targets})
    with (OUT/("doc_check_"+version+".jsonl")).open("xb") as stream:
        stream.write(result.stdout)
    with (OUT/("doc_check_"+version+"_invocation.json")).open("x",encoding="utf8") as stream:
        json.dump(receipt,stream,indent=2,sort_keys=True)
        stream.write("\n")
    print(json.dumps(dict(passed=passed,checks=rows),ensure_ascii=False))
    if not passed:
        raise SystemExit(2)

if __name__ == "__main__":
    execute(sys.argv[1])
