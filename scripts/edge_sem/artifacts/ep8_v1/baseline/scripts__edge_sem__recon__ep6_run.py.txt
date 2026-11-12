"""CPU-only, exclusive log/receipt wrapper; never retries."""
import argparse
import subprocess
import sys
import time
from .common import ROOT, ref, write
from .ep6_common import OUT

def main():
    p=argparse.ArgumentParser();p.add_argument("name");p.add_argument("args",nargs=argparse.REMAINDER)
    a=p.parse_args();dest=OUT/"execution"/a.name;dest.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,"-B"]+a.args
    write(dest/"started.json",dict(command=cmd,started=time.time(),gpu=False))
    with (dest/"output.log").open("x",encoding="utf8") as f:
        code=subprocess.call(cmd,cwd=str(ROOT),stdout=f,stderr=subprocess.STDOUT)
    write(dest/"result.json",dict(returncode=code,passed=code==0,ended=time.time(),log=ref(dest/"output.log")))
    print(a.name,"exit",code,flush=True)
    sys.exit(code)

if __name__=="__main__": main()
