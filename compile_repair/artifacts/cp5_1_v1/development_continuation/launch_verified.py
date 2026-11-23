"""Verify the live guarded WSL route inside the transient user service, then enter the approved study."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from population import LOCAL, load, save, sha256


def main():
    assert os.getuid() == 1000
    assert not (HERE/"controller_claim.json").exists()
    prefix = load(HERE/"prefix_verification.json")
    grant = load(HERE/"wsl_restart_authorization.json")
    windows = load(HERE/"windows_guard_live.json")
    assert grant["prefix_verification_sha256"] == sha256(HERE/"prefix_verification.json") and prefix["rows"]==6940
    assert all(windows["measured"].values())
    cgroup = Path("/proc/self/cgroup").read_text().strip()
    # User systemd is available, but its session D-Bus socket is absent on this installation.
    # The alternative transport has a private tmux socket and does not share a user terminal.
    if "cp51continuationv1.service" in cgroup:
        runtime = {"kind":"systemd-user-unit", "name":"cp51continuationv1.service"}
    else:
        sock = LOCAL / "control_v1" / "worker.sock"
        assert os.environ.get("TMUX","").split(",",1)[0] == str(sock)
        session = subprocess.check_output(["/usr/bin/tmux","-S",str(sock),"display-message","-p",
                                           "-t",os.environ["TMUX_PANE"],"#{session_name}"],text=True).strip()
        assert session == "cp51continuationv1"
        runtime = {"kind":"dedicated-user-tmux", "session":session, "socket":str(sock)}
    save(HERE/"service_claim.json",dict(pid=os.getpid(),uid=os.getuid(),cgroup=cgroup,runtime=runtime,
        invocation_id=os.environ.get("INVOCATION_ID"),hostname=socket.gethostname(),started=time.time(),
        authorization_sha256=sha256(HERE/"authorization.json"),previous_windows_check_sha256=sha256(HERE/"windows_guard_live.json")))
    config=json.loads(Path("/mnt/c/ProgramData/ClaudeClashGuard/config.json").read_text(encoding="utf-8-sig"))
    gateway=subprocess.check_output(["ip","route","show","default"],text=True).split()[2]
    service=subprocess.run(["systemctl","is-active","claude-clash-guard.service"],capture_output=True,text=True,timeout=12)
    assert gateway==config["BridgeHost"] and service.stdout.strip()=="active"
    proxy="http://"+gateway+":17897"
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({"https":proxy,"http":proxy}))
    with opener.open("https://www.cloudflare.com/cdn-cgi/trace",timeout=18) as reply:
        body=reply.read(16384).decode()
    observed=re.search(r"^ip=([^\r\n]+)",body,re.M)
    try:
        with socket.create_connection(("1.1.1.1",443),timeout=4):
            blocked=False
    except OSError:
        blocked=True
    expected=bool(observed and observed.group(1)==config["PreflightIP"])
    data=dict(utc=time.time(), gateway_matches_guard=(gateway==config["BridgeHost"]),
              wsl_proxy_expected_egress=expected,wsl_direct_blocked=blocked,
              guard_service=service.stdout.strip(),previous_nft_read=windows["wsl_nft_chains"],
              windows_check_sha256=sha256(HERE/"windows_guard_live.json"),new_package_downloads=0,
              service_claim_sha256=sha256(HERE/"service_claim.json"))
    save(HERE/"wsl_guard_live.json",data)
    if not expected or not blocked:
        raise RuntimeError("The protected WSL proxy or direct-path check failed before entering the study")
    command=HERE/"controller.py"
    os.execv(sys.executable,[sys.executable,"-B","-u",str(command)])


if __name__=="__main__":
    main()
