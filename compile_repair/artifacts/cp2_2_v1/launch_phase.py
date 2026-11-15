"""Run one CP2.2 phase with durable raw logs and an exact command receipt."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
mode=sys.argv[1]
environment="mando" if mode=="replay" else "compile-repair-production"
script="run_replay.py" if mode=="replay" else "run_corpus.py"
command=["/home/zhao/miniconda3/envs/"+environment+"/bin/python","-B",str(OUT/script)]
if mode!="replay":
    command.append(mode)
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONNOUSERSITE="1",
         OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",
         TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
started=time.monotonic()
with (OUT/(mode+".stdout.log")).open("xb") as stdout, (OUT/(mode+".stderr.log")).open("xb") as stderr:
    process=subprocess.Popen(command,cwd=str(ROOT),env=env,stdout=subprocess.PIPE,stderr=stderr)
    for index,line in enumerate(process.stdout,1):
        stdout.write(line);stdout.flush()
        if line.startswith((b"CP1 ",b"REPLAY ")) or line.startswith(b'{"mode"'):
            print(line.decode("utf8",errors="replace").rstrip(),flush=True)
    rc=process.wait()
logs={}
for suffix in (".stdout.log",".stderr.log"):
    p=OUT/(mode+suffix);raw=p.read_bytes()
    with (OUT/(p.name+".gz")).open("xb") as stream:
        with gzip.GzipFile(filename="",mode="wb",fileobj=stream,mtime=0) as zipped:zipped.write(raw)
    logs[p.name]={"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
                  "gzip_sha256":hashlib.sha256((OUT/(p.name+".gz")).read_bytes()).hexdigest()}
receipt={"command":command,"cwd":str(ROOT),"returncode":rc,"elapsed_seconds":time.monotonic()-started,
         "logs":logs,"environment":{k:env[k] for k in ("PYTHONDONTWRITEBYTECODE","PYTHONNOUSERSITE",
             "OMP_NUM_THREADS","MKL_NUM_THREADS","TREE_SITTER_LIB_DIR")}}
with (OUT/(mode+"_invocation.json")).open("x",encoding="utf8") as f:json.dump(receipt,f,sort_keys=True,indent=2)
print(json.dumps(receipt),flush=True)
raise SystemExit(rc)
