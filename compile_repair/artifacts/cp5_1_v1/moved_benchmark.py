"""Freeze moved relative-file samples, measure their primary trigger, and verify the exact inverse."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

from population import ART, CP5, LOCAL, OUT, checked_rows, load, save
from compile_repair.core.store import ArtifactStore, emit, read_checked_json, sha256
from compile_repair.evaluation.benchmark import (
    _materialize_closure, assess_mutation, base_contents, environment_observation,
    relative_move_site, score_graphs, stratified_sample)
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers

OPERATOR = "missing_relative_file_moved"
SEED = 20261122


def bases():
    digest = load(CP5 / "self_summary.json")["base_catalog_sha256"]
    rows = checked_rows(ART / "cp4_v1/bases.jsonl.gz", digest)
    assert len(rows) == 16136
    return {r["unit_id"]: r for r in rows}


def plan():
    start = time.monotonic()
    pools, counts = defaultdict(list), Counter()
    catalog = bases()
    moves = {}
    for uid, base in catalog.items():
        counts[(base["corpus"], base["series"], "bases")] += 1
        if not base["project_root"]:
            continue
        ref = base["result"]
        record = read_checked_json(ref["result_path"], ref["result_sha256"])
        root = Path(base["project_root"])
        names = {Path(f["path"]).relative_to(root).as_posix(): f["sha256"] for f in record["inputs"]}
        project = load(Path(ref["result_path"]).with_name("project.json"))
        site = relative_move_site(base, names, project["imports"])
        if site is not None:
            name, _, _, dest, _, _ = site
            moves[uid] = dict(source=name, destination=dest, sha256=names[name])
            counts[(base["corpus"], base["series"], "applicable")] += 1
            pools[base["corpus"]].append(base)
    selected = []
    for corpus, pool in sorted(pools.items()):
        for base in stratified_sample(pool, 200, SEED, OPERATOR):
            uid = base["unit_id"]
            item = {k: base[k] for k in ("unit_id", "corpus", "series", "group", "split")}
            selected.append(dict(item, move=moves[uid], seed=SEED, operator=OPERATOR))
            counts[(corpus, base["series"], "sampled")] += 1
    assert selected and len({r["unit_id"] for r in selected}) == len(selected)
    save(OUT / "moved_plan.json", selected)
    save(OUT / "moved_sampling.json", dict(seed=SEED, cap_per_corpus=200, bases=len(catalog),
         applicable=len(moves), selected=len(selected), splits=Counter(r["split"] for r in selected),
         strata=[dict(corpus=c, series=s, kind=k, units=n) for (c,s,k),n in sorted(counts.items())],
         plan_sha256=sha256(OUT / "moved_plan.json"), elapsed_seconds=time.monotonic()-start))
    print("moved plan", len(moves), "eligible", len(selected), "selected", flush=True)


def damaged_files(base, receipt):
    path = Path(receipt["mutation_path"])
    manifest = read_checked_json(path, receipt["mutation_sha256"])
    original = base_contents(base)
    assert manifest["base_unit"] == base["unit_id"] and manifest["truth_graph_sha256"] == base["graph_sha256"]
    assert manifest["original_sha256"] == {name: hashlib.sha256(raw).hexdigest() for name,raw in original.items()}
    assert manifest["operator"] == OPERATOR and manifest["target"] == "missing_relative_file"
    move = manifest["move"]
    old, new = move["source"], move["destination"]
    assert new == ".cp5_moved/" + Path(old).name and new not in original and old != next(iter(original))
    assert manifest["file_renames"] == {old: new} and move["sha256"] == manifest["original_sha256"][old]
    root = path.parent / "damaged"
    assert not (root / old).exists() and not (root / old).is_symlink()
    physical = {}
    for name, digest in manifest["damaged_sha256"].items():
        p = root / name
        raw = p.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        physical[name] = raw
    inverse = dict(physical)
    inverse[old] = inverse.pop(new)
    assert inverse == original
    return manifest, original, physical, inverse, root


def inverse_check(base, observation, compilers, versions):
    manifest, original, physical, inverse, root = damaged_files(base, observation)
    destination = LOCAL / "moved" / base["unit_id"] / "inverse"
    store = ArtifactStore(destination)
    entry, project = _materialize_closure(base, inverse, store, "input")
    closure = {Path(f.path).relative_to(project.root).as_posix(): f.sha256 for f in project.files}
    assert not project.issues and closure == manifest["original_sha256"]
    with store.journal("invocations.jsonl") as journal:
        rec = environment_observation(base, entry, project, compilers, versions, store, journal, "inverse")
    record = store.path / "units/inverse/result.json"
    assert rec.status == "success" and rec.selected_version == base["version"] and list(rec.settings) == base["settings"]
    last = rec.attempts[-1]
    graph = record.with_name("graph.json")
    actual = read_checked_json(graph, last["slither"]["graph_sha256"])
    truth = read_checked_json(base["graph_path"], base["graph_sha256"])
    # Only the physical filename changed. Both transport directions used identical source bytes.
    score = score_graphs(truth, actual, original, inverse, inverse, {}, {}, last["solc"]["returncode"], last["slither"]["d3"])
    receipt = dict(unit_id=base["unit_id"], result_path=str(record), result_sha256=sha256(record),
                   graph_sha256=sha256(graph), truth_sha256=base["graph_sha256"], mutation_sha256=observation["mutation_sha256"],
                   version=rec.selected_version, settings=list(rec.settings), score=score)
    store.write_json("inverse.json", receipt)
    assert last["slither"]["graph_usable"] and score["exact"]
    assert all(score[k]["ratio"] == 1 for k in ("kept", "cfg_edges", "calls"))
    return receipt


def measure():
    check_profile("production")
    compilers, versions, _ = load_trusted_compilers()
    selected = read_checked_json(OUT / "moved_plan.json", load(OUT / "moved_sampling.json")["plan_sha256"])
    catalog = bases()
    outcomes = Counter()
    count = 0
    start = time.monotonic()
    with (OUT / "moved_triggers.jsonl").open("x", encoding="utf8") as observations, \
         (OUT / "moved_inverse.jsonl").open("x", encoding="utf8") as scores:
        for row in selected:
            uid = row["unit_id"]
            base = catalog[uid]
            sources = base_contents(base)
            imports = load(Path(base["result"]["result_path"]).with_name("project.json"))["imports"]
            site = relative_move_site(base, sources, imports)
            assert (site[0], site[3]) == (row["move"]["source"], row["move"]["destination"])
            assert hashlib.sha256(sources[site[0]]).hexdigest() == row["move"]["sha256"]
            obs = assess_mutation(base, OPERATOR, SEED, sources, site, compilers, versions, LOCAL / "moved" / uid / "trigger")
            emit(observations, obs)
            outcomes[obs["outcome"]] += 1
            if obs["outcome"] == "included":
                emit(scores, inverse_check(base, obs, compilers, versions))
                count += 1
            if sum(outcomes.values()) % 25 == 0:
                print("observed", sum(outcomes.values()), "exact inverses", count, flush=True)
    assert sum(outcomes.values()) == len(selected) and count == outcomes["included"]
    save(OUT / "moved_summary.json", dict(selected=len(selected), outcomes=outcomes, exact_inverses=count,
         plan_sha256=sha256(OUT/"moved_plan.json"), observations_sha256=sha256(OUT/"moved_triggers.jsonl"),
         inverses_sha256=sha256(OUT/"moved_inverse.jsonl"), elapsed_seconds=time.monotonic()-start))
    print(dict(outcomes), "exact inverses", count, flush=True)


if __name__ == "__main__":
    {"plan": plan, "measure": measure}[sys.argv[1]]()
