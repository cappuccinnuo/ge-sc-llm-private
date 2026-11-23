"""Verify both frozen-policy partitions have exactly their preassigned unit IDs before combining."""
from collections import Counter
from contextlib import ExitStack
import json
from population import OUT, load, population, save, sha256


def main():
    units = list(population()[0])
    assert len(units) == 9138 and not (OUT/"full_partition_stop.json").exists()
    frozen = load(OUT/"policy.json")
    checks, streams, counts = [], [], Counter()
    target = OUT/"real_full.jsonl"
    with ExitStack() as handles:
        for part in (0,1):
            prefix = "real_full_part" + str(part)
            path = OUT/(prefix + ".jsonl")
            summary = load(OUT/(prefix + "_summary.json"))
            assert sha256(path) == summary["rows_sha256"] and summary["units"] == len(units[part::2])
            assert summary["policies"] == [frozen["policy"]] and summary["limit"] == frozen["limit"]
            checks.append(summary)
            streams.append(handles.enter_context(path.open("rb")))
        with target.open("xb") as joined:
            for i, uid in enumerate(units):
                raw = next(streams[i % 2])
                item = json.loads(raw)
                assert raw.endswith(b"\n") and item["unit_id"] == uid and item["rule"] == frozen["policy"]
                assert item["limit"] == frozen["limit"]
                joined.write(raw)
                counts[item["d3"]] += 1
            assert not any(f.read(1) for f in streams)
    save(OUT/"real_full_summary.json",dict(units=len(units),policies=[frozen["policy"]],limit=frozen["limit"],
         rows_sha256=sha256(target),index_sha256=frozen["index_sha256"],partitions=checks,
         counts=[dict(policy=frozen["policy"],d3=k,units=v) for k,v in sorted(counts.items())],
         sum_worker_seconds=sum(s["elapsed_seconds"] for s in checks)))
    print("verified full population", len(units), dict(counts), flush=True)


if __name__ == "__main__":
    main()
