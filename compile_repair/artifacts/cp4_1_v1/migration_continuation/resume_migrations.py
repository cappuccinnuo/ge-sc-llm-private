"""Validate and finish the approved package migrations. Run from the repository root in production."""
from collections import Counter
import json
from pathlib import Path
import sys
import time

DEST = Path(__file__).resolve().parent
sys.path.insert(0, str(DEST.parent))
from batch import HERE, OLD, checked, frozen, load, rows, sha
from check_receipts import verify_files
from package_supplement import setup
from replay import restore_sample
import restore_scores
from compile_repair.evaluation.benchmark import base_contents, score_graphs

OPERATOR = "unresolved_package_import"
STOPPED = ("cp3_15136", "cp3_15167")


RESULTS = DEST / "results"


def save(name, value):
    with (RESULTS / name).open("x", encoding="utf8") as fp:
        json.dump(value, fp, ensure_ascii=False, indent=2)
        fp.write("\n")


def load_inputs():
    sealed = load("migration_stop_seal.json")["batch_files_excluding_this_seal"]
    names = ("migration_counter_review.json", "package_union_plan.jsonl.gz", "migration_stop_inventory.json",
             "migration_stop_receipts.jsonl.gz", "new_observations.jsonl.gz", "supplement_observations.jsonl.gz",
             "new_scores.jsonl.gz", "supplement_scores.jsonl.gz", "new_restoration_stop.json", "supplement_restoration_stop.json")
    for name in names:
        checked(HERE/name, sealed[name]["sha256"])
    auth = json.loads((DEST/"authorization.json").read_bytes())
    assert auth["request_sha256"] == sealed["migration_counter_review.json"]["sha256"]
    frozen(OLD/"bases.jsonl.gz")
    plan = list(rows(HERE/"package_union_plan.jsonl.gz"))
    observed, prior, inventory = {}, {}, {}
    for cohort in ("new", "supplement"):
        for row in rows(HERE/(cohort+"_observations.jsonl.gz")):
            if row["operator"] == OPERATOR:
                assert row["outcome"] == "included" and row["unit_id"] not in observed
                observed[row["unit_id"]] = row
        for row in rows(HERE/(cohort+"_scores.jsonl.gz")):
            if row["operator"] == OPERATOR:
                prior[row["unit_id"]] = row
        stop = load(cohort+"_restoration_stop.json")
        prior[stop["unit_id"]] = stop
    for row in rows(HERE/"migration_stop_receipts.jsonl.gz"):
        if row["operator"] == OPERATOR:
            assert row["unit_id"] not in inventory and row["mutation_sha256"] == observed[row["unit_id"]]["mutation_sha256"]
            inventory[row["unit_id"]] = row
    order = [row["unit_id"] for row in plan]
    assert len(order) == len(set(order)) == 114 and set(order) == set(inventory) == set(observed)
    for row in plan:
        receipt = observed[row["unit_id"]]
        assert all(row[k] == receipt[k] for k in ("site_sha256","seed","package","corpus","group","split"))
    return order, observed, prior, inventory


def graph_for(base, source, observation, saved_receipts, mode, remap=None):
    ref = saved_receipts.get(mode)
    if ref:
        graph, receipt = restore_scores.verify_graph(base,ref["result_path"],ref["result_sha256"],ref["graph_sha256"])
        assert ref == receipt
        origin = "sealed"
    else:
        graph, receipt = restore_scores.compile_restoration(base,source,observation,mode,remap)
        origin = "new"
    path = Path(receipt["result_path"])
    result = json.loads(checked(path,receipt["result_sha256"]))
    attempt = result["attempts"][-1]
    project = attempt["slither"]["project"]
    remappings = list(base["remappings"])
    if remap and remap not in remappings:
        remappings.append(remap)
    assert project["remappings"] == remappings and not project["issues"]
    assert attempt["slither"]["profile"] == "production" and attempt["solc"]["cwd"] == project["root"]
    verify_files(project, source)
    journal = path.parents[2]/"invocations.jsonl"
    raw = journal.read_bytes()
    counts = Counter(j["kind"] for j in map(json.loads,raw.splitlines()))
    assert counts["solc"] and counts["slither"]
    return graph, dict(receipt,origin=origin,journal_sha256=sha(raw),journal_path=str(journal),invocations=dict(counts))


def evaluate(uid, observation, inventory, prior):
    base = restore_scores.BASES[uid]
    raw = base_contents(base)
    truth = json.loads(checked(base["graph_path"],base["graph_sha256"]))
    manifest, damaged, repaired, first, second = restore_sample(base,raw,observation)
    physical, ref = graph_for(base,repaired,observation,inventory,"exact")
    exact = score_graphs(truth,physical,raw,damaged,repaired,first,second,0,True)
    if prior is not None and exact != prior["score"]:
        raise ValueError("The archived exact score changed")
    record = dict(unit_id=uid,cohort=observation["cohort"],corpus=base["corpus"],series=base["series"],
                  split=base["split"],operator=OPERATOR,package=manifest["package"],file_renames=manifest["file_renames"],
                  mutation_sha256=observation["mutation_sha256"],truth_graph_sha256=base["graph_sha256"],
                  graph=ref, score=exact)
    if not exact["exact"]:
        return dict(record, stop="exact_restoration")
    _, middle, moved, damage, repair = restore_sample(base,raw,observation,migration=True)
    physical, ref = graph_for(base,moved,observation,inventory,"migration",manifest["remapping"])
    result = score_graphs(truth,physical,raw,middle,moved,damage,repair,0,True,file_renames=manifest["file_renames"])
    record.update(migration=result, migration_graph=ref)
    if prior is not None and result["raw_migration_score"] != prior["migration"]:
        return dict(record,stop="archived_raw_migration_score_changed")
    if (result["migration_counters"]["status"] not in ("verified","identical") or not result["exact"]
            or any(result[k]["ratio"] != 1 for k in ("kept","cfg_edges","calls"))):
        return dict(record,stop="migration_restoration")
    return record


def main():
    start = time.monotonic()
    RESULTS.mkdir()
    order, observations, prior, inventory = load_inputs()
    setup(restore_scores)
    if restore_scores.LOCAL.name != "migration_continuation":
        raise ValueError("A new continuation scratch directory is required")
    # Establish the two first discrepancies, then audit all remaining physical
    # receipts before starting any new tool invocation.
    archived = [u for u in order if "migration" in inventory[u] and u not in STOPPED]
    missing = [u for u in order if "migration" not in inventory[u]]
    assert len(archived) == 7 and len(missing) == 105
    assert all(("exact" in inventory[u]) == ("migration" in inventory[u]) for u in order)
    sequence = list(STOPPED) + archived + missing
    counters, invocations = Counter(), Counter()
    with (RESULTS/"package_scores.jsonl").open("x",encoding="utf8") as stream:
        for i, uid in enumerate(sequence,1):
            observation = observations[uid]
            restore_scores.STAGE = observation["cohort"]
            try:
                row = evaluate(uid,observation,inventory[uid],prior.get(uid))
            except Exception as exc:
                import traceback
                row = dict(unit_id=uid,stop=type(exc).__name__,reason=str(exc),traceback=traceback.format_exc())
            if "stop" in row:
                save("stop.json",row)
                raise ValueError("First mismatch at {}: {}".format(uid,row["stop"]))
            for k in ("graph","migration_graph"):
                ref = row[k]
                counters[k+"_"+ref["origin"]] += 1
                if ref["origin"]=="new":
                    invocations.update(ref["invocations"])
            m = row["migration"]
            counters["raw_exact"] += int(m["raw_migration_score"]["exact"])
            counters["corrected_exact"] += int(m["exact"])
            counters["verified_renumbering"] += int(m["migration_counters"]["status"]=="verified")
            stream.write(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n")
            stream.flush()
            if i==2:
                print("Both frozen stops reproduced raw and passed the approved comparison", flush=True)
            if i==9:
                assert not invocations
                print("Reused all 9 exact and 9 migrated receipts before new compilations",flush=True)
            if i%20==0:
                print("Validated",i,"of",len(sequence),flush=True)
    assert counters["graph_new"] == counters["migration_graph_new"] == len(missing)
    assert counters["corrected_exact"] == len(order)
    save("migration_acceptance.json",dict(expected=len(order),passed=True,counts=dict(counters),
        new_invocations=dict(invocations),initial_stops=STOPPED,elapsed_seconds=round(time.monotonic()-start,3),
        scores_sha256=sha((RESULTS/"package_scores.jsonl").read_bytes())))
    print("All 114 migrations passed",dict(counters),dict(invocations),flush=True)


if __name__ == "__main__":
    main()
