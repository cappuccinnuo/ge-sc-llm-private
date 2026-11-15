"""Read-only recomputation of captured CP2.1 replay evidence; no extraction."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from compile_repair.evaluation.survey import checked_json, SIX_C, REPORT_SHA, SEAL_SHA

def read(path):
    return json.loads(path.read_text())

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def counter(extraction, target, sha):
    values = Counter()
    for row in extraction["occurrences"]:
        for name in ("function","node","declaration"):
            assert row[name] is None or row[name]["filename"] == target
        key = [sha, [row["layer"], row["function_name"],
            row["function"]["start"] if row["function"] else None,
            row["modifier"], row["context_contract"], row["context_declarer"], row["inherited_context"],
            row["node"]["start"] if row["node"] else None,
            row["declaration"]["start"] if row["declaration"] else None,
            row["canonical_name"], row["fact"], row["tags"]]]
        values[json.dumps(key, sort_keys=True)] += 1
    return values

def execute():
    store = OUT.parent/"cp2_6c_v2"
    plan = read(store/"plan.json")
    old_plan = read(OUT.parent/"cp2_6c_v1/plan.json")
    assert plan == old_plan
    seal = read(store/"seal.json")
    assert all(digest((store/p).read_bytes()) == sha for p,sha in seal["files"].items())
    report = checked_json(SIX_C/"slither_full/report.json", REPORT_SHA)
    reference_seal = checked_json(SIX_C/"slither_full/report.seal.json", SEAL_SHA)
    assert reference_seal["report_sha256"] == REPORT_SHA
    lookup = {(name, r["file"], r["source_sha256"]):r
              for name, task in report["tasks"].items() for r in task["files"] if r["status"] == "compared"}
    comparisons = [json.loads(line) for line in (store/"comparison.jsonl").read_text().splitlines()]
    audit, unstable, failures = [], [], []
    for index, row in enumerate(comparisons, 1):
        job = plan["jobs"][index-1]
        assert row["path"] == job["source"] and row["version"] == job["version"]
        source = Path(row["path"])
        ref = lookup[(source.parts[-3]+"_contract", source.name, row["source_sha256"])]
        expected = counter(ref["slither_extraction"], job["replay_source"], row["source_sha256"])
        raw = gzip.decompress((store/"extractions"/("{:04d}.json.gz".format(index))).read_bytes())
        assert digest(raw) == row["extraction_sha256"]
        actual = counter(json.loads(raw), job["replay_source"], row["source_sha256"])
        assert (actual == expected) == row["equal"]
        assert dict(expected-actual) == row["only_reference"] and dict(actual-expected) == row["only_replay"]
        item = dict(index=index, path=row["path"], main_exact=row["equal"])
        if not row["equal"]:
            folder = store/row["additional_directory"]
            child = read(folder/"summary.json")
            invocation = read(store/(row["additional_directory"]+"_invocation.json"))
            assert invocation["returncode"] == 0 and invocation["cwd"] == str(ROOT)
            assert child["status"] == "complete" and len(child["samples"]) == 10
            assert [r["sample"] for r in child["samples"]] == list(range(1,11))
            samples = [actual]
            for observation in child["samples"]:
                raw = gzip.decompress((folder/observation["extraction"]).read_bytes())
                assert digest(raw) == observation["extraction_sha256"]
                samples.append(counter(json.loads(raw), job["replay_source"], row["source_sha256"]))
            keys = set(expected).union(*(set(s) for s in samples))
            failed, varying, stable = [], [], 0
            for key in sorted(keys):
                counts = [s.get(key,0) for s in samples]
                lo, hi, wanted = min(counts), max(counts), expected.get(key,0)
                record = dict(key=key, counts=counts, minimum=lo, maximum=hi, reference=wanted)
                if lo == hi:
                    stable += 1
                    if wanted != lo:
                        record["reason"] = "reference_only" if hi == 0 else "stable_mismatch"
                        failed.append(record)
                else:
                    fields = json.loads(key)[1]
                    record.update(layer=fields[0], function_name=fields[1], inherited_context=fields[6],
                                  kind=fields[10][2], context_contract=fields[4], context_declarer=fields[5])
                    varying.append(record)
                    if not lo <= wanted <= hi:
                        failed.append(dict(record, reason="outside_observed_range"))
            assert row["d20"] == dict(passed=not failed, samples=11, stable_keys=stable,
                                     unstable_keys=varying, failing_keys=failed)
            item.update(main_occurrences=sum(actual.values()), reference_occurrences=sum(expected.values()),
                        stable_keys=stable, sample_occurrence_totals=[sum(s.values()) for s in samples],
                        unstable_keys=varying, failing_keys=failed)
            unstable.extend(dict(path=row["path"], **r) for r in varying)
            for failure in failed:
                matches = [r for r in ref["slither_extraction"]["occurrences"]
                           if counter({"occurrences":[r]},job["replay_source"],row["source_sha256"]).get(failure["key"])]
                failures.append(dict(path=row["path"], source_sha256=row["source_sha256"],
                                     version=row["version"], reference_rows=matches, **failure))
        audit.append(item)
    summary = read(store/"summary.json")
    assert len(comparisons) == summary["compared"]
    assert sum(r["equal"] for r in comparisons) == summary["main_exact_files"]
    assert len(unstable) == summary["unstable_keys"]
    assert sum(len(r.get("failing_keys",[])) for r in audit) == len(summary["failing_keys"])
    result = dict(schema="cp2.1-captured-replay-audit-v1", passed=True,
        criterion_passed=summary["passed"], observed_files=len(comparisons),
        planned_files=len(plan["jobs"]), remaining=len(plan["jobs"])-len(comparisons),
        frozen_report_sha256=REPORT_SHA, frozen_seal_sha256=SEAL_SHA,
        extraction_calls_in_this_audit=0, extra_samples_in_this_audit=0,
        stable_rule_recomputed=True, unstable_keys=len(unstable),
        unique_unstable_keys=len({r["key"] for r in unstable}),
        inherited_unstable_keys=sum(r["inherited_context"] is True for r in unstable),
        non_inherited_unstable_keys=sum(r["inherited_context"] is False for r in unstable),
        failures=failures, files=audit)
    with (OUT/"captured_replay_audit.json").open("x", encoding="utf8") as stream:
        json.dump(result,stream,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ("files","failures")},indent=2))

if __name__ == "__main__":
    execute()
