"""Exclusive CPU regression logs for EP7, with immutable per-run receipts."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from .ep7_common import OUT
from ..io import write,ref

def run(suite):
    paths={"nodesem":"scripts/node_sem/tests","dfg":"scripts/DFG/dfg_v2/tests","edgesem":"scripts/edge_sem/tests"}
    folder=OUT/"regression"/suite
    folder.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider",paths[suite],
         "--junitxml="+str(folder/"junit.xml")]
    started=time.monotonic()
    env=dict(os.environ,CUDA_VISIBLE_DEVICES="",PYTHONDONTWRITEBYTECODE="1")
    with (folder/"output.log").open("x",encoding="utf8") as stream:
        result=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT,env=env)
    write(folder/"result.json",dict(suite=suite,command=cmd,exit_code=result.returncode,
        seconds=time.monotonic()-started,log=ref(folder/"output.log"),cuda_visible_devices=""))
    print(suite,"exit",result.returncode,"seconds",time.monotonic()-started,flush=True)
    if result.returncode:sys.exit(result.returncode)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("suite",choices=("nodesem","dfg","edgesem"))
    run(p.parse_args().suite)
