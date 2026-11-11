"""Run one bounded CPU probe/test, preserving its log and exit receipt."""
import argparse
import os
import subprocess
import sys
import time
from .common import OUT, write, ref

def main():
    p=argparse.ArgumentParser();p.add_argument("--name",required=True);p.add_argument("args",nargs=argparse.REMAINDER)
    a=p.parse_args()
    if not a.args:raise ValueError("Missing Python module arguments")
    dest=OUT/"execution";dest.mkdir(parents=True,exist_ok=True)
    args=a.args[1:] if a.args[0]=="--" else a.args
    cmd=[sys.executable,"-B"]+args
    write(dest/(a.name+".started.json"),dict(command=cmd,CUDA_VISIBLE_DEVICES=os.environ.get("CUDA_VISIBLE_DEVICES"),started=time.time()))
    start=time.monotonic()
    with (dest/(a.name+".log")).open("x",encoding="utf8")as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    write(dest/(a.name+".json"),dict(command=cmd,exit_code=result.returncode,
        seconds=time.monotonic()-start,log=ref(dest/(a.name+".log"))))
    print(a.name,"exit",result.returncode,flush=True)
    sys.exit(result.returncode)

if __name__=="__main__":main()
