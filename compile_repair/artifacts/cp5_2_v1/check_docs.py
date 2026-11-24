"""Verify the new evidence guide, handover and the four append-only documentation ranges."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
MODULE=ROOT/"compile_repair"
baseline=json.loads((HERE/"baseline.json").read_bytes())["documents"]
targets=[MODULE/name for name in ("CP5_REPORT.md","PROGRESS.md","docs/CHANGE_LOG.md","docs/DECISIONS.md","docs/HANDOVER.md")]
targets.append(HERE/"README.md")
args=[]
for path in targets:
    rel=path.relative_to(ROOT).as_posix()
    name=path.relative_to(MODULE).as_posix()
    if name in baseline and name!="docs/HANDOVER.md":
        length=baseline[name]["bytes"]
        assert hashlib.sha256(path.read_bytes()[:length]).hexdigest()==baseline[name]["sha256"]
        rel+=":"+str(length)
    args.append(rel)
command=[sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk",*args]
ran=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
rows=list(map(json.loads,ran.stdout.splitlines()))
result=dict(command=command,returncode=ran.returncode,docs=rows,errors=ran.stderr.decode("utf8"),
    sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in targets})
with (HERE/(sys.argv[1]+".json")).open("x",encoding="utf8") as f:
    json.dump(result,f,ensure_ascii=False,sort_keys=True,indent=2);f.write("\n")
assert ran.returncode==0 and len(rows)==len(targets) and all(r["passed"] for r in rows)
print("doc_check",len(rows),"passed",flush=True)
