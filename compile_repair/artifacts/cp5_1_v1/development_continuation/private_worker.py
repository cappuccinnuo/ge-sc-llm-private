"""Keep an ordinary Windows WSL client connected while an independent private tmux worker runs."""
import json
from pathlib import Path
import os
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from population import LOCAL, ROOT, load, save, sha256

CONTROL=LOCAL/"control_v1"
SOCKET=CONTROL/"worker.sock"
SESSION="cp51continuationv1"
TMUX="/usr/bin/tmux"
PYTHON="/home/zhao/miniconda3/envs/compile-repair-production/bin/python"


def worker():
    assert os.getuid()==1000 and os.environ.get("TMUX","").split(",",1)[0]==str(SOCKET)
    with (CONTROL/"worker.log").open("xb") as log:
        child=subprocess.run([PYTHON,"-B","-u",str(HERE/"launch_verified.py")],cwd=ROOT,
                             stdout=log,stderr=subprocess.STDOUT)
    # This is outside the batch seal and is allowed to be written after the seal itself.
    save(CONTROL/"worker_exit.json",dict(returncode=child.returncode,completed=time.time(),
         log_sha256=sha256(CONTROL/"worker.log")))
    return child.returncode


def keeper():
    assert os.getuid()==1000 and Path(sys.executable).resolve()==Path(PYTHON).resolve()
    assert load(HERE/"prefix_verification.json")["rows"]==6940
    assert all(load(HERE/"windows_guard_live.json")["measured"].values())
    assert not any((HERE/n).exists() for n in ("service_claim.json","controller_claim.json","worker_claim.json"))
    CONTROL.mkdir(mode=0o700,exist_ok=False)
    save(CONTROL/"launch_claim.json",dict(pid=os.getpid(),socket=str(SOCKET),session=SESSION,
         auth_sha256=sha256(HERE/"authorization.json"),launch_guard_sha256=sha256(HERE/"launch_verified.py")))
    prefix=[TMUX,"-f","/dev/null","-S",str(SOCKET)]
    subprocess.run(prefix+["new-session","-d","-s",SESSION,"-c",str(ROOT),
                           PYTHON,"-B","-u",str(Path(__file__).resolve()),"worker"],check=True)
    print("Private tmux worker started",flush=True)
    exit_file=CONTROL/"worker_exit.json"
    while not exit_file.exists():
        state=subprocess.run(prefix+["has-session","-t",SESSION],capture_output=True)
        if state.returncode and not exit_file.exists():
            raise RuntimeError("Worker exited without a completion receipt; preserved without retry")
        if not exit_file.exists():
            time.sleep(12)
    return load(exit_file)["returncode"]


if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="worker":
        raise SystemExit(worker())
    if len(sys.argv)!=1:
        raise ValueError("Unexpected keeper invocation")
    raise SystemExit(keeper())
