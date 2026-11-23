"""Evaluate CP4.1 included samples and CP5.1's independently triggered moved-file samples."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import time

from evidence import POLICIES, steps_facts, verified_index
from evaluate_units import freeze
from moved_benchmark import OPERATOR, bases, damaged_files
from population import ART, LOCAL, OUT, load, save
from compile_repair.core.store import emit, read_checked_json, sha256
from compile_repair.evaluation.benchmark import base_contents, dependency_repair_observation
from compile_repair.evaluation.report import dependency_benchmark_summary
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers
sys.path.insert(0, str(ART / "cp5_v1"))
from benchmark_inputs import samples
sys.path.insert(0, str(ART / "cp4_1_v1"))
from replay import restore_sample


def rows(path):
    with path.open(encoding="utf8") as fp:
        yield from map(json.loads, fp)


def checked_rows(path, digest):
    assert sha256(path) == digest
    return list(rows(path))


def run(mode):
    from types import SimpleNamespace
    start = time.monotonic()
    check_profile("production")
    db = verified_index()
    catalog = bases()
    tools, versions, _ = load_trusted_compilers()
    plan = samples()
    if mode == "dev":
        selected = [r for r in plan if r["operator"] == "unresolved_package_import" and r["split"] == "dev"]
        assert len(selected) == 8
        policies, limit, name = POLICIES, None, "package_dev"
    else:
        policy = load(OUT / "policy.json")
        assert policy["status"] == "frozen" and policy["index_sha256"] == db.seal["index_sha256"]
        policies, limit, name = [policy["policy"]], policy["limit"], "benchmark"
        movement = load(OUT / "moved_summary.json")
        moved = checked_rows(OUT/"moved_triggers.jsonl", movement["observations_sha256"])
        included = [r for r in moved if r["outcome"] == "included"]
        assert len(included) == movement["exact_inverses"]
        selected = plan + included
        assert len(plan) == 2264
    results, duplicated = [], []
    local = LOCAL / name
    local.mkdir(parents=True, exist_ok=False)
    path = OUT / (name + ".jsonl")
    with path.open("x", encoding="utf8") as log:
        for row in selected:
            if mode == "full" and (OUT/"evaluation_stop.json").exists():
                raise RuntimeError("Evaluation stopped at a peer integrity check")
            uid = row["unit_id"]
            base = catalog[uid]
            if row["operator"] == OPERATOR:
                manifest, original, damaged, _, folder = damaged_files(base, row)
                injury = {}
            else:
                original = base_contents(base)
                manifest, damaged, _, injury, _ = restore_sample(base, original, row)
                folder = Path(row["mutation_path"]).parent / "damaged"
            for policy in policies:
                output = local / policy / row["operator"] / uid
                result = dependency_repair_observation(base, manifest, original, damaged, injury, folder,
                    tools, versions, db, policy, output, dependency_limit=limit)
                rec = load(output / "units" / uid / "result.json")
                facts = steps_facts(output, uid, SimpleNamespace(**rec))
                result.update(mechanical=facts["mechanical"], compiled_combinations=facts["compiled_combinations"],
                              mutation_sha256=row["mutation_sha256"])
                assert result["score"]["removed_by_repair"] == 0 and bool(result["score"]["compiled"]) == facts["d3"]
                emit(log, result)
                results.append(result)
                if result["score"]["compiled"] and row["operator"] in ("io_error","missing_relative_file","closure_version_conflict"):
                    detail = load(output / "units" / uid / "repair_steps.json")
                    duplicated.append(dict(unit_id=uid, operator=row["operator"], split=row["split"],
                         accepted=[s for s in detail if s.get("accepted")], mutation_sha256=row["mutation_sha256"]))
            if len(results) % 50 == 0:
                print(mode, len(results), "observations", round(time.monotonic()-start), "s", flush=True)
    assert len(results) == len(selected) * len(policies)
    save(OUT/(name+"_summary.json"), dict(units=len(selected), policies=policies, limit=limit,
         rows_sha256=sha256(path), negative_control_successes=duplicated,
         scores={p:dependency_benchmark_summary(r for r in results if r["policy"]==p) for p in policies},
         elapsed_seconds=time.monotonic()-start))
    print(name, len(results), "observations", flush=True)


def choose():
    dev, bench = defaultdict(list), defaultdict(list)
    for r in checked_rows(OUT/"real_dev.jsonl", load(OUT/"real_dev_summary.json")["rows_sha256"]):
        dev[r["rule"]].append(r)
    for r in checked_rows(OUT/"package_dev.jsonl", load(OUT/"package_dev_summary.json")["rows_sha256"]):
        bench[r["policy"]].append(r)
    selected = freeze(verified_index(), dev, bench)
    print(selected["policy"], "K", selected["limit"], flush=True)


def summarize():
    from compile_repair.evaluation.report import aggregate_attributions
    from population import population
    targets, historic = population()
    full = checked_rows(OUT/"real_full.jsonl", load(OUT/"real_full_summary.json")["rows_sha256"])
    assert {r["unit_id"] for r in full} == set(targets) and len(full)==9138
    groups, mechanical = Counter(), Counter()
    contributions = Counter()
    for r in full:
        if r["d3"]:
            for step in set(r["accepted_steps"]):
                contributions[r["corpus"], step] += 1
        historic[r["unit_id"]] = dict(historic[r["unit_id"]], status=r["status"], primary=r["primary"],
                                      any_categories=r["any_categories"])
        tier = max((v["tier"] for v in r["releases"].values()), default="no_release")
        groups[r["corpus"],r["last_step"],tier,r["d3"],r["truncated"]] += 1
        mechanical.update(r["mechanical"])
    reference = checked_rows(OUT/"real_masked.jsonl", load(OUT/"real_masked_summary.json")["rows_sha256"])
    masked = {}
    for p in POLICIES:
        group = [r for r in reference if r["rule"]==p]
        assert len(group)==73 and len({k for r in group for k in [targets[r["unit_id"]]["group"]]})==1
        masked[p] = dict(units=len(group), d3=sum(r["d3"] for r in group),
                         versions=sum(r["reference"]["all_versions"] for r in group),
                         version_or_bytes=sum(r["reference"]["all_version_or_bytes"] for r in group),
                         truncated=sum(r["truncated"] for r in group))
    categories = [c["category"] for c in load(ART/"cp4_1_v1/d6_priority.json")["categories"]]
    save(OUT/"external_summary.json", dict(units=len(full), d3=sum(r["d3"] for r in full),
        truncated=sum(r["truncated"] for r in full), mechanical=mechanical, masked_t1_by_policy=masked,
        successful_units_by_accepted_step=[dict(corpus=c, step=s, units=v) for (c,s),v in sorted(contributions.items())],
        groups=[dict(corpus=k[0], step=k[1], tier=k[2], d3=k[3], truncated=k[4], units=n) for k,n in sorted(groups.items())],
        failure_table=aggregate_attributions(historic.values(), categories), cost_usd=0, llm_calls=0))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "freeze":
        choose()
    elif mode == "summarize":
        summarize()
    elif mode in ("dev", "full"):
        run(mode)
    else:
        raise ValueError("Unknown measurement stage")
