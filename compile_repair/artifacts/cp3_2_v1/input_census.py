"""Read-only CP3.2 acceptance oracle. Keep one observation per original unit."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from compile_repair.evaluation.survey import solidity_snippet_evidence

BASE = "992bec09"
ART = ROOT / "compile_repair" / "artifacts"
INVENTORY = ART / "cp3_continue_v1" / "unit_inventory.jsonl"
OLD = ART / "cp3_1_v1" / "unit_attributions.jsonl.gz"
WRAPPERS = ART / "cp3_1_v1" / "wrapper_scan.json"
REVIEW = ART / "cp3_1_review_v1" / "trace_parser_units.json"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def frozen(path):
    rel = path.relative_to(ROOT).as_posix()
    original = subprocess.check_output(["git", "show", BASE + ":" + rel], cwd=str(ROOT))
    if path.read_bytes() != original:
        raise ValueError("Frozen artifact changed: " + rel)
    return original


def reject_constant(value):
    raise ValueError("Invalid JSON constant")


def observe(raw):
    stripped = raw.strip()
    if stripped.startswith(b"\xef\xbb\xbf"):
        stripped = stripped[3:].strip()
    if stripped.startswith(b"{{") and stripped.endswith(b"}}"):
        stripped = stripped[1:-1]
    if stripped[:1] in b'{["-0123456789tfn' and stripped:
        try:
            obj = json.loads(stripped, parse_constant=reject_constant)
        except (ValueError, RecursionError):
            pass
        else:
            if isinstance(obj, dict):
                if "language" in obj and obj["language"] != "Solidity":
                    return {"kind": "non_solidity_input", "language": obj["language"]}
                sources = obj.get("sources")
                if obj.get("language") == "Solidity" and isinstance(sources, dict):
                    missing = sum(not (isinstance(entry, dict) and isinstance(entry.get("content"), str))
                                  for entry in sources.values())
                    return {"kind": "standard_json_input", "source_count": len(sources),
                            "missing_source_count": missing}
                for entries in (sources, obj):
                    if isinstance(entries, dict) and all(
                            isinstance(v, dict) and isinstance(v.get("content"), str)
                            for v in entries.values()):
                        return {"kind": "standard_json_input", "source_count": len(entries),
                                "missing_source_count": 0}
                if obj.get("language") == "Solidity":
                    return {"kind": "solidity", "language": "Solidity"}
            return {"kind": "unclassified_json"}
    fact = solidity_snippet_evidence(raw)
    return dict(fact, kind="solidity" if fact["is_solidity"] else "non_solidity_input")


def run(dest):
    started = time.monotonic()
    inventory = [json.loads(line) for line in frozen(INVENTORY).splitlines()]
    previous = {r["unit_id"]: r for r in
                (json.loads(line) for line in gzip.decompress(frozen(OLD)).splitlines())}
    wrapper_ids = set(json.loads(frozen(WRAPPERS))["hits"])
    review_ids = {r["unit_id"] for r in json.loads(frozen(REVIEW))}
    assert len(inventory) == len({r["unit_id"] for r in inventory}) == 31307
    assert len(previous) == 31071 and sum(r["status"] == "success" for r in previous.values()) == 21223
    facts, cache = {}, {}
    output = dest / "input_observations.jsonl.gz"
    with output.open("xb") as file, gzip.GzipFile(filename="", fileobj=file, mode="wb", mtime=0) as stream:
        for row in inventory:
            raw = Path(row["path"]).read_bytes()
            sha = digest(raw)
            if sha != row["entry_sha256"]:
                raise ValueError("Input SHA256 mismatch: " + row["unit_id"])
            if sha not in cache:
                cache[sha] = observe(raw)
            uid = row["unit_id"]
            facts[uid] = cache[sha]
            receipt = dict(unit_id=uid, corpus=row["corpus"], entry_sha256=sha, evidence=facts[uid])
            stream.write((json.dumps(receipt, sort_keys=True) + "\n").encode())
    counts = defaultdict(Counter)
    newly_excluded, success_conflicts, mando_conflicts, old_excluded_conflicts = [], [], [], []
    new_wrappers = {u for u, fact in facts.items() if fact["kind"] == "standard_json_input"}
    for row in inventory:
        uid, corpus = row["unit_id"], row["corpus"]
        fact = facts[uid]
        kind = fact["kind"]
        positive = kind in ("solidity", "standard_json_input")
        counts[corpus][kind] += 1
        old = previous.get(uid)
        sample = dict(unit_id=uid, corpus=corpus, entry_sha256=row["entry_sha256"], evidence=fact)
        if old:
            assert (corpus, row["entry_sha256"]) == (old["corpus"], old["entry_sha256"])
            if old["status"] == "success" and not positive:
                success_conflicts.append(dict(sample, prior_result=old["selected_result"]))
            if kind == "non_solidity_input":
                newly_excluded.append(dict(sample, prior_status=old["status"],
                                           prior_primary=old["primary"]["categories"],
                                           prior_any=old["any_categories"]))
        else:
            assert corpus == "SOChecker" and not row["language_evidence"]["is_solidity"]
            if kind != "non_solidity_input" or any(fact.get(k) != v for k, v in row["language_evidence"].items()):
                old_excluded_conflicts.append(sample)
        if corpus == "MANDO" and not positive:
            mando_conflicts.append(sample)
    assert len([r for r in inventory if r["corpus"] == "MANDO"]) == 846
    gate = not (success_conflicts or mando_conflicts or old_excluded_conflicts)
    summary = dict(base_commit=BASE, scanned=len(facts), unique_sha256=len(cache), by_corpus=counts,
                   eligible_before=len(previous), prior_successes=21223, mando_inputs=846,
                   prior_excluded=len(inventory)-len(previous), success_conflicts=success_conflicts,
                   mando_conflicts=mando_conflicts, exclusion_conflicts=old_excluded_conflicts,
                   newly_excluded=newly_excluded, previous_wrappers=len(wrapper_ids),
                   wrapper_additions=sorted(new_wrappers-wrapper_ids), wrapper_losses=sorted(wrapper_ids-new_wrappers),
                   review_22_classified=sum(facts[u]["kind"]=="non_solidity_input" for u in review_ids),
                   documentation_gate_passed=gate, elapsed_seconds=round(time.monotonic()-started, 3),
                   inputs={str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (INVENTORY, OLD, WRAPPERS, REVIEW)},
                   observations_sha256=digest(output.read_bytes()), solc_invocations=0, slither_invocations=0)
    with (dest/"input_gate.json").open("x") as fp:
        json.dump(summary, fp, indent=2, ensure_ascii=False)
        fp.write("\n")
    print("scanned", len(facts), "success conflicts", len(success_conflicts), "MANDO conflicts",
          len(mando_conflicts), "old exclusions changed", len(old_excluded_conflicts),
          "new exclusions", len(newly_excluded), "wrapper additions", len(new_wrappers-wrapper_ids),
          "gate passed", gate, flush=True)
    return 0 if gate else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    sys.exit(run(parser.parse_args().out))
