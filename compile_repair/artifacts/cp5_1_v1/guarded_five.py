"""Limited five-release continuation after the separately authorized TLS stop."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
OLD = OUT.parent / "cp5_v1"
sys.path.insert(0, str(OLD))
from registry_metadata import HOST, connection, digest, journal, read, route, write


def integrity(data):
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")



LAUNCHER_AUTH_SHA = "52d91fbb9496d198f2f6ee7f0edab944175e484aec76ad1736b7247a0bc246d7"


def durable_record(path, value):
    with path.open("x", encoding="utf8") as fp:
        json.dump(value, fp, ensure_ascii=False, sort_keys=True)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    fd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def claim(remaining):
    grant = read(OUT / "launcher_authorization.json")
    assert digest((OUT / "launcher_authorization.json").read_bytes()) == LAUNCHER_AUTH_SHA
    assert grant["status"] == "approved" and grant["requests_per_url"] == 1 and grant["cost_cap_usd"] == 0
    assert grant["previous_authorization_sha256"] == digest((OUT / "last_five_authorization.json").read_bytes())
    assert grant["original_resume_sha256"] == digest((OUT / "authorization.json").read_bytes())
    assert grant["launcher_stop_sha256"] == digest((OUT / "launcher_stop.json").read_bytes())
    assert grant["original_script_sha256"] == digest((OUT / "continue_five.py").read_bytes())
    assert tuple(r["url"] for r in grant["releases"]) == tuple(r["registry_url"] for _, r in remaining)
    assert len({r["url"] for r in grant["releases"]}) == len(remaining) == 5
    if ((OUT / "download_last_five.jsonl").exists() or (OUT / "last_five_runtime.log").exists()
            or any(OUT.glob("five_get_*.json"))):
        raise RuntimeError("Earlier pre-request journal or URL claim exists")
    for pid in Path("/proc").glob("[0-9]*"):
        try:
            args = (pid / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if args and b"python" in os.path.basename(args[0]) and any(os.path.basename(a) == b"continue_five.py" for a in args[1:]):
            raise RuntimeError("Original transfer worker is active")
    durable_record(OUT / "five_execution_claim.json",
                   dict(authorization_sha256=LAUNCHER_AUTH_SHA, urls=[r["url"] for r in grant["releases"]],
                        pid=os.getpid(), max_requests_per_url=1, unix_time=time.time()))


def main():
    auth = read(OUT / "authorization.json")
    original = read(OLD / "d23/authorization.json")
    request = read(OLD / "d23_download_request.json")
    limits = auth["limits"]
    assert auth["status"] == "approved" and digest((OLD / "d23_download_request.json").read_bytes()) == auth["request_sha256"] == original["request_sha256"]
    assert digest((OLD / "d23/authorization.json").read_bytes()) == auth["d23_authorization_sha256"]
    assert digest((OLD / "d23/transport_stop.json").read_bytes()) == auth["stop_sha256"]
    before = (OLD / "d23/download.jsonl").read_bytes()
    assert digest(before) == auth["prior_receipts_sha256"]
    extra = read(OUT / "last_five_authorization.json")
    stopped = read(OUT / "transport_stop.json")
    assert extra["status"] == "approved" and extra["stop_sha256"] == digest((OUT/"transport_stop.json").read_bytes())
    assert extra["limits"] == limits and extra["requests_per_url"] == 1
    attempt = (OUT/"download_remaining.jsonl").read_bytes()
    assert digest(attempt) == stopped["resume_journal_sha256"]
    part = list(map(json.loads, attempt.splitlines()))
    assert len(part) == 19 and not part[-1]["verified"] and part[-1]["partial_bytes"] == 0
    records = list(map(json.loads, before.splitlines())) + part[:-1]
    plan = [(name, r) for name, pkg in request["by_package"].items() for r in pkg["releases"]]
    root = Path(auth["storage"])
    folder = root / "archives"
    assert root.resolve() == root and not (root / "archives.json").exists()
    assert len(records) == extra["prior_verified"] == 167 and len(plan) == 172
    assert set(folder.iterdir()) == {Path(r["path"]) for r in records}
    for (name, release), r in zip(plan, records):
        raw = Path(r["path"]).read_bytes()
        assert r["package"] == name and r["version"] == release["version"] and r["verified"]
        assert r["url"] == release["registry_url"] and r["sha256"] == digest(raw)
        assert len(raw) == r["packed_bytes"] and integrity(raw) == r["integrity"] == release["integrity"]
    total = sum(r["packed_bytes"] for r in records)
    assert total == extra["prior_packed_bytes"]
    remaining = plan[len(records):]
    assert len(remaining) == len(extra["releases"]) == 5
    assert all(a == dict(package=n, version=r["version"], url=r["registry_url"], integrity=r["integrity"])
               for a, (n, r) in zip(extra["releases"], remaining))
    claim(remaining)
    start = time.monotonic()
    with (OUT / "download_last_five.jsonl").open("x", encoding="utf8") as log:
        for name, r in remaining:
            url = r["registry_url"]
            target = folder / (digest((name + "@" + r["version"]).encode()) + ".tgz")
            row = dict(package=name, version=r["version"], url=url, path=str(target),
                       expected_integrity=r["integrity"], registry_unpacked_bytes=r["unpacked_bytes"])
            durable_record(OUT / ("five_get_" + r["version"] + ".json"), dict(
                authorization_sha256=LAUNCHER_AUTH_SHA, package=name, version=r["version"], url=url,
                expected_sha512=r["integrity"], state="claimed_before_connect_or_get", unix_time=time.time()))
            conn = connection()
            began = time.monotonic()
            try:
                conn.request("GET", route(url), headers={"Host":HOST, "Connection":"close", "Accept-Encoding":"identity",
                                                         "User-Agent":"CompileRepair-CP5/1"})
                response = conn.getresponse()
                row["http_status"] = response.status
                if response.status != 200:
                    raise ValueError("Unexpected npm HTTP status " + str(response.status))
                limit = min(limits["per_release_packed_limit_bytes"], limits["total_packed_limit_bytes"] - total)
                if int(response.getheader("Content-Length") or 0) > limit:
                    raise ValueError("Declared size exceeds the approved packed limit")
                count = 0
                with target.open("xb") as fp:
                    while count < limit:
                        block = response.read(min(1024**2, limit - count))
                        if not block:
                            break
                        fp.write(block)
                        count += len(block)
                    if count == limit and not response.isclosed():
                        raise ValueError("Transfer reached a packed limit without confirmed EOF")
                data = target.read_bytes()
                if len(data) != count or integrity(data) != r["integrity"] or r["packed_bytes"] not in (None,count):
                    raise ValueError("Release size or SHA512 mismatch")
                row.update(verified=True, packed_bytes=count, integrity=integrity(data), sha256=digest(data))
                records.append(row)
                total += count
            except Exception as exc:
                row.update(verified=False, error=type(exc).__name__, detail=str(exc),
                           partial_bytes=target.stat().st_size if target.is_file() else 0)
                raise
            finally:
                row["elapsed_seconds"] = round(time.monotonic()-began, 3)
                journal(log, row)
                log.flush()
                os.fsync(log.fileno())
                conn.close()
    assert len(records) == 172 and total <= limits["total_packed_limit_bytes"]
    for record in records:
        data = Path(record["path"]).read_bytes()
        assert record["sha256"] == digest(data) and record["integrity"] == integrity(data)
    catalog = root / "archives.json"
    write(catalog, dict(schema=1, authorization_sha256=auth["d23_authorization_sha256"], packages=20,
                        resume_authorization_sha256=digest((OUT/"authorization.json").read_bytes()),
                        last_five_authorization_sha256=digest((OUT/"last_five_authorization.json").read_bytes()),
                        launcher_authorization_sha256=LAUNCHER_AUTH_SHA,
                        releases=records, total_packed_bytes=total, cost_usd=0,
                        per_release_unpacked_limit_bytes=limits["per_release_unpacked_regular_file_limit_bytes"],
                        total_unpacked_limit_bytes=limits["total_unpacked_regular_file_limit_bytes"]))
    write(OUT/"download_summary.json", dict(verified=172, resumed=23, final_continuation=5, total_packed_bytes=total,
          continued_packed_bytes=total-auth["prior_packed_bytes"], local_catalog=str(catalog),
          catalog_sha256=digest(catalog.read_bytes()), elapsed_seconds=time.monotonic()-start, cost_usd=0))
    print("verified",len(records),"archives",total,"bytes",flush=True)


if __name__ == "__main__":
    main()
