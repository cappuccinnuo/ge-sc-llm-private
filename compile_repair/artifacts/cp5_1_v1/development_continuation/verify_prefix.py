"""Verify the saved development prefix and preserve it byte-for-byte before any continuation."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
ROOT = BATCH.parents[2]
LOCAL = ROOT.parent / "compile-repair-local" / BATCH.name


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for buf in iter(lambda: source.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def main():
    start = time.monotonic()
    review = json.loads((BATCH / "development_interrupt.json").read_bytes())
    prefix = BATCH / "real_dev.jsonl"
    assert digest(prefix) == review["prefix_sha256"] and prefix.stat().st_size == review["prefix_bytes"]
    with gzip.open(BATCH / "population.jsonl.gz", "rt", encoding="utf8") as fp:
        expected = [(v["unit_id"], rule) for v in map(json.loads, fp) if v["split"] == "dev"
                    for rule in ("latest", "oldest", "closest")]
    output = HERE / "original_6940.jsonl.gz"
    assert not output.exists() and not (HERE / "prefix_verification.json").exists()
    backed = set()
    results, steps, byte_sum = 0, 0, 0
    with prefix.open("rb") as fp:
        for i,line in enumerate(fp):
            r = json.loads(line)
            key = r["unit_id"], r["rule"]
            assert key == expected[i] and key not in backed
            backed.add(key)
            d = LOCAL / "real_dev" / r["rule"] / r["unit_id"]
            unit = d / "units" / r["unit_id"]
            want = "/home/zhao/SmartContract/compile-repair-local/cp5_1_v1/real_dev/{0}/".format(r["rule"])
            want += r["unit_id"] + "/units/" + r["unit_id"] + "/result.json"
            assert r["result_path"] == want and (d / "invocations.jsonl").is_file()
            result = unit / "result.json"
            assert digest(result) == r["result_sha256"]
            results += 1
            byte_sum += result.stat().st_size
            s = unit / "repair_steps.json"
            if r["steps_sha256"] is None:
                assert not s.exists()
            else:
                assert digest(s) == r["steps_sha256"]
                steps += 1
                byte_sum += s.stat().st_size
    assert results == len(backed) == 6940 and len(expected) == 6948
    assert list(expected[results:]) == [(v["unit_id"],v["policy"]) for v in review["remaining"]]
    assert digest(prefix) == review["prefix_sha256"]
    with prefix.open("rb") as src, output.open("xb") as disk:
        with gzip.GzipFile(filename="", fileobj=disk, mode="wb", mtime=0) as dest:
            shutil.copyfileobj(src, dest, length=1024 * 1024)
    h = hashlib.sha256()
    with gzip.open(output, "rb") as src:
        for part in iter(lambda: src.read(1024 * 1024), b""):
            h.update(part)
    assert h.hexdigest() == review["prefix_sha256"]
    data = dict(rows=results, repair_steps_verified=steps, result_and_steps_bytes=byte_sum,
                ordered_prefix_of=6948, prefix_bytes=prefix.stat().st_size, prefix_sha256=h.hexdigest(),
                backup_sha256=digest(output), requested_remaining=review["remaining"],
                verification_seconds=time.monotonic()-start, measurements_rerun=0)
    with (HERE/"prefix_verification.json").open("x",encoding="utf8") as out:
        json.dump(data,out,sort_keys=True,indent=2)
        out.write("\n")
    print(results, "verified results,",steps,"verified step records", flush=True)


if __name__ == "__main__":
    main()
