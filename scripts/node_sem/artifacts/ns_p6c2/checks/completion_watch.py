"""Single, no-retry report completion after the sealed CPU controller."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT=Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
OUT=ROOT/"scripts/node_sem/artifacts/ns_p6c2"
os.chdir(str(ROOT))
def read(p):return json.loads(p.read_text())
def write(p,v):
    with p.open("x",encoding="utf8") as f:json.dump(v,f,ensure_ascii=False,indent=2)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):h.update(b)
    return h.hexdigest()
try:
    while not (OUT/"computation_complete.json").exists():
        if (OUT/"failure.json").exists():raise RuntimeError("CPU calculation failed; reporting not run")
        pid=read(OUT/"controller.started.json")["pid"]
        cmd=Path("/proc")/str(pid)/"cmdline"
        if not cmd.exists() or b"scripts.node_sem.p6c2_run" not in cmd.read_bytes():
            raise RuntimeError("CPU controller disappeared; no retry")
        time.sleep(15)
    with (OUT/"checks/finalize.log").open("x") as log:
        r=subprocess.run([sys.executable,"-B","-m","scripts.node_sem.p6c2_finalize"],
            stdout=log,stderr=subprocess.STDOUT)
    if r.returncode:raise RuntimeError("Report failed; no retry")
    args=[sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]
    for f,v in read(OUT/"doc_prefixes.json").items():
        assert hashlib.sha256((ROOT/f).read_bytes()[:v["bytes"]]).hexdigest()==v["sha256"]
        args.append(f+":"+str(v["bytes"]))
    args+=["scripts/node_sem/NS_P6C2_REPORT.md",str(OUT/"REPORT.md")]
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
    write(OUT/"checks/doc_check.json",dict(passed=r.returncode==0,command=args,output=r.stdout))
    if r.returncode:raise RuntimeError("Document validation failed")
    old=ROOT/"scripts/node_sem/artifacts/ns_p6c"
    for f in read(old/"artifact_inventory.json")["files"]:
        if sha(f["path"])!=f["sha256"]:raise ValueError("Old artifact modified: "+f["path"])
    write(OUT/"checks/completion_validation.json",dict(passed=True,old_artifacts_unchanged=True,
        document_prefixes_unchanged=True,report_sha256=sha(OUT/"report.json"),
        new_HGT_fits=0,committed=False))
    print("NS-P6c2 reporting and validation complete; local commit remains.",flush=True)
except Exception:
    write(OUT/"checks/completion_failure.json",dict(error=traceback.format_exc()))
    raise
