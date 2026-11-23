"""One authorized transfer per remaining D23 URL, retaining the complete original byte budget."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
OLD = OUT.parent / "cp5_v1"
sys.path.insert(0, str(OLD))
from registry_metadata import HOST, connection, digest, journal, read, route, write


def integrity(data):
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")


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
    records = list(map(json.loads, before.splitlines()))
    plan = [(name, r) for name, pkg in request["by_package"].items() for r in pkg["releases"]]
    root = Path(auth["storage"])
    folder = root / "archives"
    assert root.resolve() == root and not (root / "archives.json").exists()
    assert len(records) == auth["prior_count"] == 149 and len(plan) == 172
    assert set(folder.iterdir()) == {Path(r["path"]) for r in records}
    for (name, release), r in zip(plan, records):
        raw = Path(r["path"]).read_bytes()
        assert r["package"] == name and r["version"] == release["version"] and r["verified"]
        assert r["url"] == release["registry_url"] and r["sha256"] == digest(raw)
        assert len(raw) == r["packed_bytes"] and integrity(raw) == r["integrity"] == release["integrity"]
    total = sum(r["packed_bytes"] for r in records)
    assert total == auth["prior_packed_bytes"]
    remaining = plan[len(records):]
    assert len(remaining) == len(auth["releases"]) == 23
    assert all(a == dict(package=n, version=r["version"], url=r["registry_url"], integrity=r["integrity"])
               for a, (n, r) in zip(auth["releases"], remaining))
    start = time.monotonic()
    with (OUT / "download_remaining.jsonl").open("x", encoding="utf8") as log:
        for name, r in remaining:
            url = r["registry_url"]
            target = folder / (digest((name + "@" + r["version"]).encode()) + ".tgz")
            row = dict(package=name, version=r["version"], url=url, path=str(target),
                       expected_integrity=r["integrity"], registry_unpacked_bytes=r["unpacked_bytes"])
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
                conn.close()
    assert len(records) == 172 and total <= limits["total_packed_limit_bytes"]
    for record in records:
        data = Path(record["path"]).read_bytes()
        assert record["sha256"] == digest(data) and record["integrity"] == integrity(data)
    catalog = root / "archives.json"
    write(catalog, dict(schema=1, authorization_sha256=auth["d23_authorization_sha256"], packages=20,
                        resume_authorization_sha256=digest((OUT/"authorization.json").read_bytes()),
                        releases=records, total_packed_bytes=total, cost_usd=0,
                        per_release_unpacked_limit_bytes=limits["per_release_unpacked_regular_file_limit_bytes"],
                        total_unpacked_limit_bytes=limits["total_unpacked_regular_file_limit_bytes"]))
    write(OUT/"download_summary.json", dict(verified=172, resumed=23, total_packed_bytes=total,
          continued_packed_bytes=total-auth["prior_packed_bytes"], local_catalog=str(catalog),
          catalog_sha256=digest(catalog.read_bytes()), elapsed_seconds=time.monotonic()-start, cost_usd=0))
    print("verified",len(records),"archives",total,"bytes",flush=True)


if __name__ == "__main__":
    main()
