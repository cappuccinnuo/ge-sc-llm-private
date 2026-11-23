"""One authorized transfer with a checked proxy and an exclusive, durable claim before every GET."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
sys.path.insert(0, str(OUT))
from guard_stop_audit import PROXY, check_configuration
from guarded_five import durable_record
from resume_registry import HOST, connection, digest, route

AUTH_SHA256 = "7b6add206d127730c4f3c8f2d7540777738e8bdbf7c5c8b2fc07e16e242c0d30"
OLD = OUT.parent / "cp5_v1"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return digest(path.read_bytes())


def sri(raw):
    return "sha512-" + base64.b64encode(hashlib.sha512(raw).digest()).decode("ascii")


def prepare():
    assert sha(HERE/"authorization.json") == AUTH_SHA256
    grant = read(HERE/"authorization.json")
    assert grant["status"] == "approved" and grant["executions"] == grant["requests_per_url"] == 1
    assert grant["cost_cap_usd"] == 0 and os.environ.get("CP5_HTTPS_PROXY") == grant["proxy"] == PROXY
    assert sha(OUT/"guard_stop.json") == grant["stop_sha256"] and sha(OUT/"launcher_authorization.json") == grant["prior_grant_sha256"]
    for name, expected in grant["prior_files"].items():
        assert sha(OUT/name) == expected
    assert sorted(p.name for p in OUT.glob("five_get_*.json")) == ["five_get_1.6.0.json"]
    assert (OUT/"download_last_five.jsonl").stat().st_size == 0
    assert not (HERE/"claim.json").exists() and not (HERE/"receipts.jsonl").exists() and not list(HERE.glob("get_*.json"))
    assert not (OUT/"download_summary.json").exists()
    original = read(OUT/"authorization.json")
    limited = read(OUT/"last_five_authorization.json")
    assert limited["releases"] == grant["releases"] and original["limits"] == limited["limits"] == grant["limits"]
    assert sha(OLD/"d23_download_request.json") == original["request_sha256"]
    assert sha(OLD/"d23/authorization.json") == original["d23_authorization_sha256"]
    assert sha(OLD/"d23/download.jsonl") == original["prior_receipts_sha256"]
    assert sha(OUT/"download_remaining.jsonl") == read(OUT/"transport_stop.json")["resume_journal_sha256"]
    root = Path(original["storage"])
    assert root.resolve() == root and not (root/"archives.json").exists() and not (root/"index").exists()
    first = list(map(json.loads,(OLD/"d23/download.jsonl").read_bytes().splitlines()))
    second = list(map(json.loads,(OUT/"download_remaining.jsonl").read_bytes().splitlines()))
    assert len(first)==149 and len(second)==19 and not second[-1]["verified"] and second[-1]["partial_bytes"]==0
    records = first + second[:-1]
    request = read(OLD/"d23_download_request.json")
    expected = [(k,v) for k,pkg in request["by_package"].items() for v in pkg["releases"]]
    assert len(expected)==172 and len(records)==grant["verified_before"]==167
    assert {Path(r["path"]) for r in records} == set((root/"archives").iterdir())
    for row,(package,release) in zip(records, expected):
        raw = Path(row["path"]).read_bytes()
        assert row["verified"] and row["url"]==release["registry_url"] and row["version"]==release["version"] and row["package"]==package
        assert row["sha256"]==digest(raw) and row["integrity"]==sri(raw)==release["integrity"] and len(raw)==row["packed_bytes"]
    assert sum(r["packed_bytes"] for r in records)==grant["packed_bytes_before"]==88571115
    remaining = expected[len(records):]
    assert grant["releases"] == [dict(package=p,version=r["version"],url=r["registry_url"],integrity=r["integrity"]) for p,r in remaining]
    assert len({g["url"] for g in grant["releases"]})==len(remaining)==5
    check_configuration(grant)
    return grant, original, root, records, remaining


def download(package, release, folder, cap, log):
    version = release["version"]
    url = release["registry_url"]
    target = folder / (digest((package+"@"+version).encode())+".tgz")
    row = dict(package=package,version=version,url=url,path=str(target),expected_integrity=release["integrity"],
               registry_unpacked_bytes=release["unpacked_bytes"])
    started = time.monotonic()
    conn = None
    try:
        conn = connection()
        assert conn.sock is None and conn.host == "172.18.144.1" and conn.port == 17897
        assert conn._tunnel_host == HOST and conn._tunnel_port == 443 and conn._context.check_hostname
        path = route(url)
        durable_record(HERE/("get_"+version+".json"), dict(url=url, integrity=release["integrity"],
                       auth_sha256=AUTH_SHA256, phase="before_get", unix_time=time.time()))
        conn.request("GET", path, headers={"Host":HOST,"Connection":"close","Accept-Encoding":"identity",
                                          "User-Agent":"CompileRepair-CP5/1"})
        res = conn.getresponse()
        row["http_status"] = res.status
        if res.status != 200:
            raise ValueError("Unexpected registry status " + str(res.status))
        declared = res.getheader("Content-Length")
        if declared is not None and not 0 <= int(declared) <= cap:
            raise ValueError("Declared size exceeds authorized packed limit")
        count = 0
        with target.open("xb") as fp:
            while count < cap:
                data = res.read(min(1024**2,cap-count))
                if not data:
                    break
                fp.write(data)
                count += len(data)
            if count==cap and not res.isclosed():
                raise ValueError("Packed limit reached without confirmed EOF")
        raw = target.read_bytes()
        assert len(raw)==count and sri(raw)==release["integrity"] and release["packed_bytes"] in (None,count)
        if declared is not None:
            assert int(declared)==count
        row.update(verified=True, packed_bytes=count, sha256=digest(raw), integrity=sri(raw))
        return row
    except Exception as exc:
        row.update(verified=False,error=type(exc).__name__,detail=str(exc),
                   partial_bytes=target.stat().st_size if target.exists() else 0)
        raise
    finally:
        row["elapsed_seconds"]=round(time.monotonic()-started,3)
        log.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
        log.flush()
        os.fsync(log.fileno())
        if conn is not None:
            conn.close()


def main():
    if sys.argv[1:] not in (["verify-local"], ["transfer"]):
        raise ValueError("Expected verify-local or transfer")
    grant, original, root, records, remaining = prepare()
    if sys.argv[1] == "verify-local":
        print("verified local inputs: 167 prior, five URLs, fixed proxy, no sockets",flush=True)
        return
    start = time.monotonic()
    limits = grant["limits"]
    total = grant["packed_bytes_before"]
    durable_record(HERE/"claim.json",dict(auth_sha256=AUTH_SHA256,script_sha256=sha(Path(__file__)),
                   proxy=PROXY,expected_releases=5,unix_time=time.time()))
    with (HERE/"receipts.jsonl").open("x",encoding="utf8") as log:
        for package, release in remaining:
            cap=min(limits["per_release_packed_limit_bytes"],limits["total_packed_limit_bytes"]-total)
            row=download(package,release,root/"archives",cap,log)
            records.append(row)
            total+=row["packed_bytes"]
    assert len(records)==172 and total<=limits["total_packed_limit_bytes"]
    for row in records:
        raw=Path(row["path"]).read_bytes()
        assert sha(Path(row["path"]))==row["sha256"] and sri(raw)==row["expected_integrity"]==row["integrity"]
    catalog=root/"archives.json"
    durable_record(catalog,dict(schema=1,authorization_sha256=original["d23_authorization_sha256"],packages=20,
                   resume_authorization_sha256=sha(OUT/"authorization.json"),configured_authorization_sha256=AUTH_SHA256,
                   releases=records,total_packed_bytes=total,cost_usd=0,
                   per_release_unpacked_limit_bytes=limits["per_release_unpacked_regular_file_limit_bytes"],
                   total_unpacked_limit_bytes=limits["total_unpacked_regular_file_limit_bytes"]))
    durable_record(OUT/"download_summary.json",dict(verified=172,resumed=23,final_continuation=5,
                   total_packed_bytes=total,continued_packed_bytes=total-original["prior_packed_bytes"],
                   local_catalog=str(catalog),catalog_sha256=sha(catalog),elapsed_seconds=time.monotonic()-start,cost_usd=0))
    print("verified",len(records),"archives",total,"bytes",flush=True)


if __name__=="__main__":
    main()
