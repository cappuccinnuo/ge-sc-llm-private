"""Measure uncapped dev policies and run the frozen policy or masked-lock reference on real units."""
from collections import Counter
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import sys
import time

from evidence import POLICIES, lock_reference, steps_facts, verified_index
from population import ART, LOCAL, OUT, entry, load, population, save
from compile_repair.core.store import ArtifactStore, emit, sha256
from compile_repair.evaluation.report import aggregate_attributions, classify_record, primary_causes
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers


def freeze(index, dev, benchmarks):
    """Rank by real D3 successes, then all comparable benchmark outcomes, before any test run."""
    from compile_repair.evaluation.report import dependency_benchmark_summary
    population_by_id, _ = population()
    expected = {k for k,v in population_by_id.items() if v["split"] == "dev"}
    comparison = {}
    for policy in POLICIES:
        rows = dev[policy]
        assert len(expected) == len(rows) == 2316 and {r["unit_id"] for r in rows} == expected
        assert all(r["split"] == "dev" and r["limit"] is None and not r["truncated"] for r in rows)
        assert len(benchmarks[policy]) == 8 and all(r["split"] == "dev" for r in benchmarks[policy])
        small = dependency_benchmark_summary(benchmarks[policy])["dev"]["unresolved_package_import"]
        comparison[policy] = dict(real_d3=sum(r["d3"] for r in rows), real_units=len(rows), package_dev=small)
    best_real = max(s["real_d3"] for s in comparison.values())
    leaders = [p for p in POLICIES if comparison[p]["real_d3"] == best_real]
    def measures(p):
        small = comparison[p]["package_dev"]
        return (small["compiled"], small["main"]["kept"]["pooled_ratio"], small["original_package_files"]["equal"])
    # If the secondary criteria genuinely trade off, publish the alternatives for a user decision.
    best = tuple(max(values) for values in zip(*(measures(p) for p in leaders)))
    winners = [p for p in leaders if measures(p) == best]
    if not winners:
        save(OUT/"policy_tradeoff.json", dict(leaders=leaders, comparison=comparison))
        raise ValueError("Secondary development metrics trade off; a choice needs review")
    selected = winners[0]
    rows = dev[selected]
    successful = [r for r in rows if r["d3"]]
    # Include partial dependency rounds that subsequently allowed step 4 to succeed.
    # Retain all examined positions in successful closest-series searches, including later alternatives.
    cap = max((r["compiled_combinations"] for r in successful), default=0)
    if cap == 0:
        save(OUT/"limit_review.json", dict(reason="no successful dev unit compiled a release", comparison=comparison,
             counts=Counter(r["compiled_combinations"] for r in rows)))
        raise ValueError("No measured successful release position for a production cap")
    summaries = {}
    for p, group in dev.items():
        summaries[p] = dict(histogram=Counter(r["compiled_combinations"] for r in group),
             first_d3_positions=Counter(r["first_d3"] for r in group if r["first_d3"] is not None),
             selected_positions=Counter(r["selected_ordinal"] for r in group if r["selected_ordinal"] is not None),
             total_unit_seconds=sum(r["seconds"] for r in group), total_step3_seconds=sum(r["step3_seconds"] for r in group))
    data = dict(status="frozen", policy=selected, limit=cap, tied=winners,
                identical_outcome_tie_order=list(POLICIES), comparison=comparison, uncapped_measurements=summaries,
                limit_basis="Maximum actually compiled combinations over successful dev units for the chosen policy.",
                index_sha256=index.seal["index_sha256"], dev_measurement_sha256=sha256(OUT/"real_dev.jsonl"),
                package_measurement_sha256=sha256(OUT/"package_dev.jsonl"))
    save(OUT/"policy.json", data)
    return data


def real(mode, partition=None):
    start = time.monotonic()
    check_profile("production")
    db = verified_index()
    tools, _, _ = load_trusted_compilers()
    targets, _ = population()
    policy = load(OUT/"policy.json") if mode != "dev" else None
    if policy:
        assert policy["status"] == "frozen" and policy["index_sha256"] == db.seal["index_sha256"]
    masked = mode == "masked"
    policies = POLICIES if mode in ("dev", "masked") else (policy["policy"],)
    # The reference uses the same frozen limit for every policy.
    limit = None if mode == "dev" else policy["limit"]
    selections = [r for r in targets.values() if mode == "full" or (r["tier"] == "T1" if masked else r["split"] == "dev")]
    expected = {"dev":2316, "masked":73, "full":9138}[mode]
    assert len(selections) == expected
    name = "real_" + mode
    if partition is not None:
        if mode != "full" or partition not in (0, 1):
            raise ValueError("Only the frozen full run has two disjoint partitions")
        name += "_part" + str(partition)
        selections = selections[partition::2]
        expected = len(selections)
    destination = LOCAL / name
    destination.mkdir(exist_ok=False, parents=True)
    counts = Counter()
    out = OUT / (name+".jsonl")
    with out.open("x", encoding="utf8") as stream:
        for target in selections:
            if mode != "dev" and ((OUT/"full_partition_stop.json").exists() or (OUT/"evaluation_stop.json").exists()):
                raise RuntimeError("A peer reported an error. Current completed receipts are retained.")
            uid = target["unit_id"]
            for rule in policies:
                began = time.monotonic()
                unit, project, inventory = entry(target)
                store = ArtifactStore(destination/rule/uid)
                with store.journal("invocations.jsonl") as journal:
                    result = repair_unit(unit, tools, store, journal, project=project, project_index=inventory,
                                         offline_index=db, dependency_policy=rule, dependency_limit=limit, mask_versions=masked)
                seconds = time.monotonic() - began
                facts = steps_facts(store.path, uid, result)
                record = asdict(result)
                failures = classify_record(record)
                row = dict(unit_id=uid, rule=rule, split=target["split"], corpus=target["corpus"], limit=limit,
                    entry_sha256=target["entry_sha256"], status=result.status, reason=result.reason,
                    seconds=seconds, primary=primary_causes(record, failures),
                    any_categories=sorted({r["category"] for r in failures}), **facts)
                if masked:
                    row["reference"] = lock_reference(target, facts, db)
                emit(stream, row)
                counts[(rule, row["d3"])] += 1
                if sum(counts.values()) % 100 == 0:
                    print(mode, sum(counts.values()), "observations", round(time.monotonic()-start), "s", flush=True)
    assert sum(counts.values()) == expected * len(policies)
    save(OUT/(name+"_summary.json"), dict(units=expected, policies=policies, limit=limit,
         rows_sha256=sha256(out), counts=[dict(policy=k[0], d3=k[1], units=v) for k,v in sorted(counts.items())],
         elapsed_seconds=time.monotonic()-start, index_sha256=db.seal["index_sha256"]))
    print(mode, expected, "units", dict(counts), flush=True)


if __name__ == "__main__":
    if sys.argv[1] in ("full0", "full1"):
        part = int(sys.argv[1][-1])
        try:
            real("full", part)
        except Exception as exc:
            stop = OUT/"full_partition_stop.json"
            if not stop.exists():
                try:
                    save(stop, dict(partition=part, error=type(exc).__name__, detail=str(exc)))
                except FileExistsError:
                    pass
            raise
    else:
        real(sys.argv[1])
