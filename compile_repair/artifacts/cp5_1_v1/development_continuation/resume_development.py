"""Complete only the eight development observations in the explicitly approved interruption receipt."""
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from evidence import POLICIES, steps_facts, verified_index
from population import LOCAL, OUT, ROOT, entry, load, population, save
from compile_repair.core.store import ArtifactStore, emit, sha256
from compile_repair.evaluation.report import classify_record, primary_causes
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers


def observe(target, rule, compilers, db, destination):
    started = time.monotonic()
    uid = target["unit_id"]
    unit, project, inventory = entry(target)
    store = ArtifactStore(destination / rule / uid)
    with store.journal("invocations.jsonl") as journal:
        result = repair_unit(unit, compilers, store, journal, project=project, project_index=inventory,
                             offline_index=db, dependency_policy=rule, dependency_limit=None, mask_versions=False)
    seconds = time.monotonic() - started
    facts = steps_facts(store.path, uid, result)
    record = asdict(result)
    failures = classify_record(record)
    return dict(unit_id=uid, rule=rule, split=target["split"], corpus=target["corpus"], limit=None,
                entry_sha256=target["entry_sha256"], status=result.status, reason=result.reason,
                seconds=seconds, primary=primary_causes(record, failures),
                any_categories=sorted({r["category"] for r in failures}), **facts)


def main():
    started = time.monotonic()
    assert Path(sys.executable).resolve() == Path("/home/zhao/miniconda3/envs/compile-repair-production/bin/python").resolve()
    auth = load(HERE/"authorization.json")
    review = load(OUT/"development_interrupt.json")
    verification = load(HERE/"prefix_verification.json")
    prefix = OUT/"real_dev.jsonl"
    assert sha256(OUT/"development_interrupt.json") == auth["request_sha256"]
    assert review["prefix_sha256"] == auth["prefix_sha256"] == verification["prefix_sha256"] == sha256(prefix)
    assert sha256(HERE/"original_6940.jsonl.gz") == verification["backup_sha256"]
    assert verification["rows"] == auth["retain_completed"] == 6940
    assert not (OUT/"policy.json").exists() and not (OUT/"real_dev_summary.json").exists()
    assert not (OUT/"stage_runs.jsonl").stat().st_size
    for file,rec in load(OUT/"checkpoint_audit.json")["changed"].items():
        assert sha256(ROOT/"compile_repair"/file) == rec["sha256"]
    check_profile("production")
    db = verified_index()
    compilers, _, _ = load_trusted_compilers()
    population_by_id, _ = population()
    source_plan = [(r["unit_id"],p) for r in population_by_id.values() if r["split"]=="dev" for p in POLICIES]
    order = [tuple(auth["one_incomplete_pair_repeated_once"])] + [tuple(pair) for pair in auth["seven_not_previously_started"]]
    assert order == source_plan[6940:] == [(r["unit_id"],r["policy"]) for r in review["remaining"]]
    partial = LOCAL/"real_dev"/order[0][1]/order[0][0]/"invocations.jsonl"
    assert sha256(partial) == review["remaining"][0]["journal_sha256"]
    with partial.open("rb") as f:
        old_calls = list(map(json.loads,f))
    assert len(old_calls)==31 and all(x["kind"]=="solc" and not x["timed_out"] for x in old_calls)
    destination = LOCAL/"development_continuation"/"real_dev"
    destination.mkdir(parents=True,exist_ok=False)
    save(HERE/"worker_claim.json",dict(pid=os.getpid(), authorization_sha256=sha256(HERE/"authorization.json"),
         verified_prefix=verification["prefix_sha256"], order=order, code_hashes={
             name:sha256(OUT/name) for name in ("evaluate_units.py","evidence.py","population.py")}))
    new_table=HERE/"remaining_eight.jsonl"
    with new_table.open("x",encoding="utf8") as output:
        for uid, rule in order:
            save(HERE/(uid+"_"+rule+"_claim.json"),dict(unit_id=uid,policy=rule,unix_time=time.time()))
            row=observe(population_by_id[uid],rule,compilers,db,destination)
            emit(output,row)
            output.flush()
            os.fsync(output.fileno())
            print(uid,rule,row["status"],row["d3"],flush=True)
    new_bytes = new_table.read_bytes()
    fresh=[json.loads(line) for line in new_bytes.splitlines()]
    assert new_bytes.endswith(b"\n") and [(r["unit_id"],r["rule"]) for r in fresh]==order
    original=prefix.read_bytes()
    assert original.endswith(b"\n") and hashlib.sha256(original).hexdigest()==verification["prefix_sha256"]
    all_rows=[json.loads(line) for line in original.splitlines()]+fresh
    assert len(all_rows)==6948 and [(r["unit_id"],r["rule"]) for r in all_rows]==source_plan
    assert all(r["split"]=="dev" and r["limit"] is None and not r["truncated"] for r in all_rows)
    for r in fresh:
        assert sha256(Path(r["result_path"]))==r["result_sha256"]
    combined = hashlib.sha256(original+new_bytes).hexdigest()
    save(HERE/"merge_claim.json",dict(prefix_sha256=verification["prefix_sha256"],suffix_sha256=sha256(new_table),
         expected_combined_sha256=combined,previous_rows=6940,new_rows=8))
    with prefix.open("ab") as f:
        assert f.tell()==len(original)
        f.write(new_bytes)
        f.flush()
        os.fsync(f.fileno())
    assert sha256(prefix)==combined
    counts=Counter((r["rule"],r["d3"]) for r in all_rows)
    new_wall=time.monotonic()-started
    total=sum(r["seconds"] for r in all_rows)
    save(HERE/"resume_summary.json",dict(completed=8,reused=6940,result_rows=6948,
         row_wall_seconds_sum=total,new_batch_wall_seconds=new_wall,old_incomplete_solc_calls=len(old_calls),
         old_incomplete_solc_seconds=sum(r["elapsed_seconds"] for r in old_calls),old_journal_sha256=sha256(partial),
         new_rows_sha256=sha256(new_table),combined_sha256=combined,archive_sha256=verification["backup_sha256"]))
    save(OUT/"real_dev_summary.json",dict(units=2316,policies=POLICIES,limit=None,rows_sha256=combined,
         counts=[dict(policy=k[0],d3=k[1],units=v) for k,v in sorted(counts.items())],
         elapsed_seconds=total,elapsed_seconds_basis="sum of wall time of the 6948 completed per-unit observations; excludes interruption and idle time",
         continuation_summary_sha256=sha256(HERE/"resume_summary.json"),index_sha256=db.seal["index_sha256"]))
    print("6940 retained, 8 completed, 6948 ordered observations",flush=True)


if __name__=="__main__":
    main()
