"""Reconstruct sealed CP4 edits and independently classify the two observations."""
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from batch import ordered_work, OLD, checked, frozen, json, output_rows, rows, saved, sha
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.evaluation.benchmark import base_contents, classify_trigger
from compile_repair.evaluation.report import classify_record, primary_causes


def apply_verified(raw, patches, provenance):
    if provenance:
        return apply_patches(raw, patches)
    for patch in patches:
        if not 0 <= patch.start <= patch.end <= len(raw) or raw[patch.start:patch.end] != patch.expected:
            raise ValueError("Patch does not explain observed bytes")
        raw = raw[:patch.start] + patch.replacement + raw[patch.end:]
    return raw, None


def restore_sample(base, sources, receipt, migration=False, provenance=True):
    path = Path(receipt["mutation_path"])
    manifest = json.loads(checked(path, receipt["mutation_sha256"]))
    for field in ("operator", "seed", "split", "group", "corpus", "series"):
        if manifest[field] != receipt[field]:
            raise ValueError("Sample identity differs: " + field)
    if (manifest["base_unit"] != base["unit_id"] or manifest["version"] != base["version"] or
            manifest["settings"] != base["settings"] or manifest["truth_graph_sha256"] != base["graph_sha256"]):
        raise ValueError("Sample detached from truth record")
    if manifest["original_sha256"] != {n: sha(data) for n, data in sources.items()}:
        raise ValueError("Original closure differs")
    edits = manifest["edits"] if "edits" in manifest else [manifest["edit"]]
    by_file = defaultdict(list)
    for edit in edits:
        by_file[edit["file"]].append(edit)
    damaged = dict(sources)
    restored = dict(sources)
    first, second = {}, {}
    for name, changes in by_file.items():
        raw = sources[name]
        patches = []
        for edit in changes:
            a, b = edit["start"], edit["end"]
            expected = raw[a:b]
            if sha(expected) != edit["original_bytes_sha256"]:
                raise ValueError("Original edit range differs: " + name)
            replacement = checked(edit["new_bytes_path"], edit["new_bytes_sha256"])
            if len(replacement) != edit["new_length"]:
                raise ValueError("Replacement length differs: " + name)
            patches.append(Patch(a, b, expected, replacement, receipt["operator"]))
        if any(l.start < r.end for l, r in zip(patches, patches[1:])):
            raise ValueError("Original edit ranges overlap or are out of order")
        result, first[name] = apply_verified(raw, patches, provenance)
        deleted = any(edit["action"] == "delete_file" for edit in changes)
        if deleted:
            if result or len(changes) != 1 or (path.parent / "damaged" / name).exists():
                raise ValueError("Recorded deletion still has a file: " + name)
            del damaged[name]
        else:
            damaged[name] = result
        # A migrated importer keeps its observed package-form import. A removed
        # dependency is recovered from its verified inverse in either mode.
        inverse = [] if migration and not deleted else [
            Patch(p.start, p.start + len(p.replacement), p.replacement, p.expected, "inverse")
            for p in reversed(patches)]
        restored[name], second[name] = apply_verified(result, inverse, provenance)
        if (not migration or deleted) and restored[name] != raw:
            raise ValueError("Inverse differs from original: " + name)
    if manifest["damaged_sha256"] != {n: sha(data) for n, data in damaged.items()}:
        raise ValueError("Damaged closure differs")
    for name, digest in manifest["damaged_sha256"].items():
        checked(path.parent / "damaged" / (name or "input.sol"), digest)
    if migration:
        renames = manifest["file_renames"]
        moved = {renames.get(name, name): data for name, data in restored.items()}
        if len(moved) != len(restored):
            raise ValueError("Migration collides with another input")
        restored = moved
    return manifest, damaged, restored, first, second


def reclassify(base, observation):
    record = json.loads(checked(observation["result_path"], observation["result_sha256"]))
    folder = Path(observation["mutation_path"]).parent
    journal = checked(folder / "invocations.jsonl", observation["journal_sha256"])
    selected = [row for row in (json.loads(line) for line in journal.splitlines())
                if row.get("kind") == "selected_solc"]
    if len(selected) != int(observation["selected_attempted"]):
        raise ValueError("Selected invocation count differs")
    if record["status"] != observation["environment_status"] or record["reason"] != observation["environment_reason"]:
        raise ValueError("Environment receipt differs")
    selected_categories = []
    if selected:
        call = selected[0]
        if call["timed_out"] or call["compiler"]["version"] != base["version"] or call["returncode"] != observation["selected_returncode"]:
            raise ValueError("Selected invocation identity differs")
        if call["returncode"]:
            probe = dict(status="unrepaired", reason="selected_probe", inputs=record["inputs"],
                         attempts=[dict(stage="environment", version=base["version"], solc=call)])
            selected_categories = sorted({row["category"] for row in classify_record(probe)})
    failures = classify_record(record)
    primary = primary_causes(record, failures)["categories"]
    outcome = classify_trigger(observation["stage"], observation["operator"], SimpleNamespace(status=record["status"]),
                               primary, selected_categories)
    return dict(old_outcome=observation["outcome"], outcome=outcome, selected_categories=selected_categories,
                environment_categories=primary, environment_any_categories=sorted({r["category"] for r in failures}))


def observe_old(obs):
    base = BASES[obs["unit_id"]]
    restore_sample(base, base_contents(base), obs, provenance=False)
    return dict(obs, cohort="original", **reclassify(base, obs))


def main():
    global BASES
    for name in ("sample_plan.jsonl.gz", "sample_receipts.jsonl.gz", "bases.jsonl.gz"):
        frozen(OLD / name)
    BASES = {row["unit_id"]: row for row in rows(OLD / "bases.jsonl.gz")}
    plan = {(r["operator"], r["unit_id"]): r for r in rows(OLD / "sample_plan.jsonl.gz")}
    if len(plan) != 17432:
        raise ValueError("Unexpected frozen sample count")
    seen = set()
    counts = Counter()
    def replay():
        for n, obs in enumerate(ordered_work(observe_old, rows(OLD / "sample_receipts.jsonl.gz"), 4), 1):
            key = (obs["operator"], obs["unit_id"])
            if key in seen or any(obs[k] != v for k, v in plan[key].items()) or obs["seed"] != 20261122:
                raise ValueError("Observation and seeded plan differ")
            seen.add(key)
            counts[(key[0], obs["corpus"], obs["series"], obs["old_outcome"], obs["outcome"])] += 1
            yield obs
            if n % 1000 == 0:
                print("verified", n, flush=True)
    output_rows("original_reclassified.jsonl.gz", replay())
    if seen != set(plan):
        raise ValueError("Incomplete replay")
    saved("original_transitions.json", dict(count=len(seen), seed=20261122,
        rows=[dict(operator=o, corpus=c, series=v, previous=a, current=b, units=n)
              for (o,c,v,a,b), n in sorted(counts.items())]))
    print("verified all", len(seen), flush=True)


if __name__ == "__main__":
    main()
