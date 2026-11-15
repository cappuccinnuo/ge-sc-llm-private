"""CP1.1 mandatory documentation checks with frozen append offsets."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
version = sys.argv[1]
if version not in ("v1", "v2"):
    raise SystemExit("Use a new v1/v2 check receipt")
targets = ["compile_repair/CP1_REPORT.md:13921", "compile_repair/PROGRESS.md:23643",
           "compile_repair/docs/CHANGE_LOG.md:118369", "compile_repair/docs/HANDOVER.md",
           "compile_repair/docs/DECISIONS.md", "compile_repair/artifacts/cp1_1_v1/README.md"]
command = [sys.executable, "-B", "-m", "scripts.node_sem.doc_check", "--expect-cjk"] + targets
result = subprocess.run(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
rows = [json.loads(s) for s in result.stdout.decode("utf8").splitlines() if s.strip()]
passed = result.returncode == 0 and len(rows) == 6 and all(r["passed"] for r in rows)
name = "doc_check_" + version
with (OUT / (name + ".jsonl")).open("xb") as stream:
    stream.write(result.stdout)
with (OUT / (name + "_invocation.json")).open("x", encoding="utf8") as stream:
    json.dump(dict(command=command, returncode=result.returncode, all_passed=passed, rows=len(rows),
                   stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                   stderr=result.stderr.decode("utf8")), stream, indent=2)
print(json.dumps(dict(returncode=result.returncode, all_passed=passed, checks=rows), ensure_ascii=False))
if not passed:
    raise SystemExit(2)
