"""CP2.4 read-only acceptance audit of already-run tests and CLI evidence."""
import gzip
import hashlib
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    with (OUT / name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")

def execute():
    results = {}
    raw_equivalence = {}
    for environment in ("production", "mando"):
        receipt = json.loads((OUT / ("pytest_" + environment + ".json")).read_text())
        assert receipt["returncode"] == 0
        evidence = json.loads(gzip.decompress(
            (OUT / ("test_evidence_" + environment + ".json.gz")).read_bytes()))
        keys = [key for key in evidence if key.startswith("test_cp24_equivalence") and key.endswith("equivalence.json")]
        assert len(keys) == 1
        value = json.loads(evidence[keys[0]])
        raw_equivalence[environment] = value
        counts = Counter(row["group"] for row in value["records"])
        assert counts["mando"] == 846
        assert all(row["interval_equal"] and row["patches_equal"] and row["all_plan_fields_equal"]
                   for row in value["records"])
        results[environment] = {"counts": dict(counts), "excluded": value["excluded"],
                                "plan_fields": value["plan_fields"],
                                "plan_comparisons": 2 * len(value["records"]),
                                "evidence_key": keys[0], "all_equal": True}
    assert raw_equivalence["production"] == raw_equivalence["mando"]
    results["environments_equal"] = True
    write("equivalence.json", results)
    receipt = json.loads((OUT / "pytest_production.json").read_text())
    temp = Path(receipt["temporary_directory"])
    folders = [p for p in temp.iterdir() if p.is_dir() and not p.is_symlink()
               and p.name.startswith("test_real_cp24_cli")]
    assert len(folders) == 1
    store = folders[0] / "cli"
    seal = json.loads((store / "seal.json").read_text())
    assert len(seal["implementation_sha256"]) == 14
    assert all(sha(ROOT / p) == h for p, h in seal["implementation_sha256"].items())
    assert all(sha(store / p) == h for p, h in seal["files"].items())
    records = [json.loads(line) for line in (store / "manifest.jsonl").read_text().splitlines()]
    assert [r["status"] for r in records] == ["success", "success", "unrepaired", "unrepaired"]
    assert [r["selected_version"] for r in records[:2]] == ["0.8.0", "0.5.0"]
    assert [r["plan"]["interval"] for r in records[:2]] == [
        [[0, 8, 0], [0, 9, 0]], [[0, 5, 0], [0, 6, 0]]]
    for record in records[:2]:
        source = Path(record["inputs"][0]["path"])
        assert sha(source) == record["inputs"][0]["sha256"]
        assert (store / "units" / record["unit_id"] / "input.sol").read_bytes() == source.read_bytes()
        assert record["attempts"][-1]["solc"]["returncode"] == 0
        assert record["attempts"][-1]["slither"]["d3"]
        assert record["attempts"][-1]["slither"]["profile"] == "production"
        assert all(p["level"] == "none" and p["changes"] == [] for p in record["provenance"].values())
    assert [r["attempts"][0]["error_first_line"] for r in records[2:]] == [
        "F: unterminated pragma directive", "F: unsupported pragma expression"]
    invocations = [json.loads(line) for line in (store / "invocations.jsonl").read_text().splitlines()]
    assert len(invocations) == 4
    assert {r["unit_id"] for r in invocations} == {"input_0001", "input_0002"}
    archive = OUT / "cli_acceptance_store.tar.gz"
    assert not archive.exists()
    with tarfile.open(str(archive), "w:gz") as tf:
        for p in sorted(store.rglob("*")):
            if p.is_file():
                tf.add(str(p), arcname=str(p.relative_to(store)), recursive=False)
    with tarfile.open(str(archive), "r:gz") as tf:
        members = tf.getmembers()
        for member in members:
            assert hashlib.sha256(tf.extractfile(member).read()).hexdigest() == sha(store / member.name)
    write("cli_acceptance.json", {"passed": True, "records": records,
        "source_store": str(store), "invocations": len(invocations),
        "solc_calls": sum(r["kind"] == "solc" for r in invocations),
        "slither_calls": sum(r["kind"] == "slither" for r in invocations),
        "archive": archive.name, "archive_sha256": sha(archive), "archive_members": len(members),
        "seal_sha256": sha(store / "seal.json"), "implementation_sha256": seal["implementation_sha256"]})
    receipts = {}
    for mode in ("production", "mando", "dfg"):
        record = json.loads((OUT / ("pytest_" + mode + ".json")).read_text())
        assert record["returncode"] == 0
        raw = gzip.decompress((OUT / ("pytest_" + mode + ".log.gz")).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == record["log_sha256"]
        summary = [line for line in raw.decode().splitlines() if " passed" in line][-1]
        receipts[mode] = {"returncode": record["returncode"],
                         "summary": summary, "elapsed_seconds": record["elapsed_seconds"]}
    write("test_acceptance.json", {"passed": True, "tests": receipts, "cost_usd": 0, "llm_calls": 0})
    print(json.dumps({"equivalence": {k:v for k,v in results.items() if k != "mando"},
                      "tests": receipts, "cli_store_members": len(members)}, indent=2))

if __name__ == "__main__":
    execute()
