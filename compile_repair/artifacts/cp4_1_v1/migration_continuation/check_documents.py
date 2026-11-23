"""Verify the prior append-only prefixes and run the repository's Chinese documentation checker."""
import json
from pathlib import Path
import subprocess
import sys
DEST=Path(__file__).resolve().parent
ROOT=DEST.parents[3]
BASE="0f690e6f2152d4bb6390f56ffb9de91e06a893ea"
MANDO_PYTHON="/home/zhao/miniconda3/envs/mando/bin/python"
targets=["compile_repair/docs/HANDOVER.md","compile_repair/docs/DECISIONS.md",
         (DEST/"README.md").relative_to(ROOT).as_posix()]
for name in ("compile_repair/docs/CHANGE_LOG.md","compile_repair/CP4_REPORT.md","compile_repair/PROGRESS.md"):
    old=subprocess.check_output(["git","show",BASE+":"+name],cwd=ROOT)
    assert (ROOT/name).read_bytes().startswith(old), "Prior document prefix changed: "+name
    targets.append(name+":"+str(len(old)))
cmd=[MANDO_PYTHON,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+targets
p=subprocess.run(cmd,cwd=ROOT,capture_output=True,check=False)
records=[json.loads(row) for row in p.stdout.splitlines()]
with (DEST/sys.argv[1]).open("x",encoding="utf8") as fp:
    json.dump(dict(command=cmd,returncode=p.returncode,records=records,stderr=p.stderr.decode()),
              fp,ensure_ascii=False,indent=2);fp.write("\n")
assert p.returncode==0 and len(records)==6 and all(r["passed"] for r in records)
print(len(records),"UTF-8 and CJK documents passed")
