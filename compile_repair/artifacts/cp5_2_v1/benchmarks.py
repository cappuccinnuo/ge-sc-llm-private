"""Rebuild historical scores from their original bytes and examine new repair outcomes separately."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import sys

from measure import (active, ART, HERE, LOCAL, OLD, bases, check_profile, emit, frozen, jsonline, load,
                     read_checked_json, save, sha256, steps_facts, typed_record, verified_index)
from evaluate_benchmark import samples, restore_sample
from moved_benchmark import OPERATOR, damaged_files
from compile_repair.evaluation.benchmark import (base_contents, dependency_repair_observation,
    score_dependency_repair)
from compile_repair.toolchain.solc import load_trusted_compilers


def inputs():
    refs = {(r["unit_id"],r["operator"]):r for r in samples()}
    meta = load(OLD/"moved_summary.json")
    path = OLD/"moved_triggers.jsonl"
    assert sha256(path) == meta["observations_sha256"]
    import json
    for r in map(json.loads,path.read_bytes().splitlines()):
        assert r["outcome"] == "included"
        refs[r["unit_id"],r["operator"]] = r
    assert len(refs) == 2664
    return refs


def contents(base, ref):
    if ref["operator"] == OPERATOR:
        manifest, original, work, _, folder = damaged_files(base, ref)
        return manifest, original, work, {}, folder
    original = base_contents(base)
    manifest, work, _, injury, _ = restore_sample(base, original, ref)
    return manifest, original, work, injury, Path(ref["mutation_path"]).parent/"damaged"


def old_directory(row):
    recorded = Path(row["result_path"])
    unit = recorded.parent if recorded.parent.name == row["unit_id"] else recorded.parents[1]
    assert unit.name == row["unit_id"] and unit.parent.name == "units"
    rec = read_checked_json(recorded,row["result_sha256"])
    assert sha256(unit/"result.json") == row["result_sha256"]
    return unit.parents[1], typed_record(rec)


def run(mode):
    catalog, refs = bases(), inputs()
    baseline = frozen("benchmark")
    if mode == "scores":
        operators = {"standard_json_input","unresolved_package_import",OPERATOR}
        baseline = [r for r in baseline if r["operator"] in operators]
        assert len(baseline) == 950+114+400
    else:
        check_profile("production")
        compilers, versions, _ = load_trusted_compilers()
        index = verified_index()
    counts = Counter()
    with jsonline("benchmark_"+mode) as out:
        for i, row in enumerate(baseline, 1):
            active()
            uid, op = row["unit_id"], row["operator"]
            base = catalog[uid]
            ref = refs[uid,op]
            assert ref["mutation_sha256"] == row["mutation_sha256"]
            manifest, original, work, injury, folder = contents(base,ref)
            if mode == "scores":
                directory, record = old_directory(row)
                args = (base,manifest,original,work,injury,directory,record,"oldest",21)
                prior = score_dependency_repair(*args,file_level=False)
                assert prior["score"] == row["score"] and prior["graph_sha256"] == row["graph_sha256"], (uid,op)
                new = score_dependency_repair(*args)
                if "previous_wrapper_score" in new["score"]:
                    assert new["score"]["previous_wrapper_score"] == prior["score"], (uid,op,"prior wrapper")
                output = dict(unit_id=uid, operator=op, corpus=base["corpus"], split=base["split"],
                              graph_sha256=row["graph_sha256"], result_sha256=row["result_sha256"],
                              prior_score=prior["score"], score=new["score"])
            else:
                dest = LOCAL / "benchmark" / op / uid
                new = dependency_repair_observation(base,manifest,original,work,injury,folder,
                      compilers,versions,index,"oldest",dest,dependency_limit=21)
                facts = steps_facts(dest,uid,SimpleNamespace(**load(dest/"units"/uid/"result.json")))
                equal = (facts["d3"],new["graph_sha256"]) == (row["status"]=="success", row["graph_sha256"])
                output = dict(new, prior_status=row["status"], prior_sha256=row["graph_sha256"],
                              prior_score=row["score"], equal=equal, mechanical=facts["mechanical"])
            emit(out,output)
            if mode == "rerun" and op != OPERATOR and not equal:
                raise ValueError("Other operator D3/graph SHA differs: {} {}".format(uid,op))
            counts[op,bool(row["score"]["exact"]),bool(new["score"]["exact"])] += 1
            if i%100 == 0:
                print(mode,i,flush=True)
    save(HERE/("benchmark_"+mode+".json"),dict(rows=len(baseline),
         counts=[[*k,v] for k,v in sorted(counts.items())],sha256=sha256(HERE/("benchmark_"+mode+".jsonl"))))


if __name__ == "__main__":
    run(sys.argv[1])
