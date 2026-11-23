"""Audit local stop evidence and test CONNECT configuration with socket creation disabled."""
import base64
import hashlib
import json
from pathlib import Path
import os
import socket
from unittest.mock import patch

from population import CP5, OUT, load, save, sha256
from resume_registry import HOST, connection, route

PROXY = "http://172.18.144.1:17897"


def check_configuration(grant):
    with patch.dict(os.environ, {"CP5_HTTPS_PROXY": PROXY}), \
         patch.object(socket, "socket", side_effect=AssertionError("offline only")), \
         patch.object(socket, "create_connection", side_effect=AssertionError("offline only")), \
         patch.object(socket, "getaddrinfo", side_effect=AssertionError("offline only")):
        for item in grant["releases"]:
            conn = connection()
            try:
                assert conn.sock is None and conn.host == "172.18.144.1" and conn.port == 17897
                assert conn._tunnel_host == HOST and conn._tunnel_port == 443 and conn._context.check_hostname
                assert route(item["url"]) == "/zeppelin-solidity/-/zeppelin-solidity-" + item["version"] + ".tgz"
            finally:
                conn.close()


def main():
    grant = load(OUT / "launcher_authorization.json")
    check_configuration(grant)
    first = OUT / "five_get_1.6.0.json"
    journal = OUT / "download_last_five.jsonl"
    log = OUT / "guarded_five_runtime.log"
    assert sorted(OUT.glob("five_get_*.json")) == [first] and not journal.read_bytes()
    assert load(first)["url"] == grant["releases"][0]["url"]
    assert "KeyError: 'CP5_HTTPS_PROXY'" in log.read_text() and "conn = connection()" in log.read_text()
    prior = (CP5 / "d23/download.jsonl").read_text().splitlines()
    more = [r for r in (OUT / "download_remaining.jsonl").read_text().splitlines() if json.loads(r)["verified"]]
    rows = list(map(json.loads, prior + more))
    folder = Path(load(OUT/"authorization.json")["storage"])/"archives"
    assert len(rows) == len(set(folder.iterdir())) == 167
    assert set(folder.iterdir()) == {Path(r["path"]) for r in rows}
    for r in rows:
        raw = Path(r["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == r["sha256"]
        assert "sha512-"+base64.b64encode(hashlib.sha512(raw).digest()).decode() == r["integrity"]
    save(OUT/"guard_stop.json", dict(reason="The retained WSL shell did not set CP5_HTTPS_PROXY. The guard reached the first exclusive marker, then failed reading os.environ before socket creation or any HTTP GET.",
         last_execution_authorization=sha256(OUT/"launcher_authorization.json"),
         original_claim_sha256=sha256(OUT/"five_execution_claim.json"), first_marker_sha256=sha256(first),
         original_journal_sha256=sha256(journal), trace_sha256=sha256(log), verified=len(rows),
         packed_bytes=sum(r["packed_bytes"] for r in rows), first_release_claimed="1.6.0",
         observed_gets=0, other_claimed=0, offline_configuration_checks=5, direct_network_during_preflight=False,
         verified_configuration=dict(proxy=PROXY,tunnel_host=HOST,tunnel_port=443,verify_tls_hostname=True),
         new_run_requires_user_decision=True, failed_attempt_retained=True))
    print("167 dual hashes; 5 socket-disabled configuration checks; zero GETs", flush=True)


if __name__ == "__main__":
    main()
