"""Run a measured stage once and preserve its first exit, including a shared stop on failure."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def write(path, record):
    with path.open("x", encoding="utf8") as f:
        json.dump(record,f,indent=2,sort_keys=True)
        f.write("\n")


def main():
    name, script, *params = sys.argv[1:]
    stop = OUT/"measurement_stop.json"
    if stop.exists():
        raise SystemExit("A previous stage requires review")
    freeze = json.loads((OUT.parent/"frozen_suites/source_freeze.json").read_bytes())["modules"]
    assert all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest() == v for k,v in freeze.items())
    path = OUT/(script + ".py")
    command = [sys.executable,"-B","-u",str(path),*params]
    info = dict(name=name,command=command,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                script_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    write(OUT/(name+"_start.json"),info)
    began=time.monotonic()
    with (OUT/(name+".log")).open("x",encoding="utf8") as log:
        ran = subprocess.run(command,cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT)
    status = dict(info,elapsed_seconds=time.monotonic()-began,returncode=ran.returncode)
    write(OUT/(name+"_exit.json"),status)
    if ran.returncode:
        try:write(stop,status)
        except FileExistsError:pass
    print(name,ran.returncode,flush=True)
    raise SystemExit(ran.returncode)


if __name__ == "__main__":
    main()
