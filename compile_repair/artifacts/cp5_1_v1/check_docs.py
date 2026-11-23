"""Check the exact report and append-only documentation ranges at this CP5 checkpoint."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = "5fe7671fb6ebe6c9393bf41e29c0cfea950861e8"
targets = ["compile_repair/CP5_REPORT.md", "compile_repair/PROGRESS.md",
           "compile_repair/docs/CHANGE_LOG.md", "compile_repair/docs/DECISIONS.md",
           "compile_repair/docs/HANDOVER.md", "compile_repair/artifacts/cp5_1_v1/README.md"]
if (OUT/"final_tables.md").is_file():
    targets.append("compile_repair/artifacts/cp5_1_v1/final_tables.md")
append = {"compile_repair/CP5_REPORT.md", "compile_repair/PROGRESS.md", "compile_repair/docs/CHANGE_LOG.md"}
args = []
for p in targets:
    if p in append:
        old = subprocess.check_output(["git","show",BASE+":"+p],cwd=ROOT)
        assert (ROOT/p).read_bytes().startswith(old)
        args.append(p+":"+str(len(old)))
    else:
        args.append(p)
command=[sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+args
run=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
answer=dict(command=command,returncode=run.returncode,records=list(map(json.loads,run.stdout.splitlines())),
            errors=run.stderr.decode("utf8"),sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in targets})
with (OUT/(sys.argv[1]+".json")).open("x",encoding="utf8") as fp:
    json.dump(answer,fp,ensure_ascii=False,sort_keys=True,indent=2)
    fp.write("\n")
assert len(answer["records"]) == len(targets) and all(r["passed"] for r in answer["records"]) and run.returncode==0
print(len(targets),"passed",flush=True)
