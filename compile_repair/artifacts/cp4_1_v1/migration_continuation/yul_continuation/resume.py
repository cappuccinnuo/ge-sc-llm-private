"""Reuse the 40 accepted rows and the stopped physical graph pair, then finish the frozen draw."""
from collections import Counter
import json
from pathlib import Path
import sys
import time
import traceback

DEST = Path(__file__).resolve().parent
sys.path.insert(0,str(DEST.parent))
from resume_migrations import (base_contents, checked, evaluate, load_inputs, restore_sample, restore_scores,
                               score_graphs, setup, sha)
from witness import save, witness


def archived(ref):
    checked(ref["journal_path"],ref["journal_sha256"])
    return {k:v for k,v in ref.items() if k not in ("origin","invocations","journal_path","journal_sha256")}


def check_switch(row, observation):
    uid = row["unit_id"]
    base = restore_scores.BASES[uid]
    original = base_contents(base)
    m, damaged, repaired, first, second = restore_sample(base,original,observation,migration=True)
    assert row["truth_graph_sha256"]==row["graph"]["graph_sha256"]==base["graph_sha256"]
    truth = json.loads(checked(base["graph_path"],base["graph_sha256"]))
    actual = json.loads(checked(row["migration_graph"]["graph_path"],row["migration_graph"]["graph_sha256"]))
    evidence = {side:witness(uid,side,row[key]) for side,key in (("truth","graph"),("repaired","migration_graph"))}
    result = score_graphs(truth,actual,original,damaged,repaired,first,second,0,True,
                          file_renames=m["file_renames"],migration_compilations=evidence)
    assert result["raw_migration_score"]==row["migration"]["raw_migration_score"]
    row["migration"] = result
    if result["exact"] and result["migration_counters"].get("yul_switches"):
        row.pop("stop")
    return row


def main():
    auth = json.loads((DEST/"authorization.json").read_bytes())
    parent = DEST.parent
    checked(parent/"tuple_continuation/yul_switch_review.json",auth["request_sha256"])
    stop = json.loads(checked(parent/"tuple_continuation/stop.json",auth["stop_sha256"]))
    closed = [json.loads(line) for file,h in auth["closed_outputs"].items() for line in checked(parent/file,h).splitlines()]
    done = {r["unit_id"] for r in closed}
    assert len(done)==len(closed)==auth["preserved_successes"] and all(r["migration"]["exact"] and r["score"]["exact"] for r in closed)
    uid0 = stop["unit_id"]
    order, observations, _, inventory = load_inputs()
    remaining = [uid for uid in order if uid not in done and uid!=uid0]
    assert uid0==auth["existing_stopped_pair"] and len(remaining)==auth["remaining_new_pairs"]
    assert all("exact" not in inventory[u] and "migration" not in inventory[u] for u in remaining)
    inventory[uid0] = dict(exact=archived(stop["graph"]),migration=archived(stop["migration_graph"]))
    old_raw = dict(score=stop["score"],migration=stop["migration"]["raw_migration_score"])
    setup(restore_scores)
    assert restore_scores.LOCAL.name=="yul_continuation"
    counts, calls = Counter(), Counter()
    start = time.monotonic()
    with (DEST/"package_scores.jsonl").open("x",encoding="utf8") as stream:
        for i,uid in enumerate([uid0]+remaining,1):
            obs=observations[uid]
            restore_scores.STAGE=obs["cohort"]
            try:
                row=evaluate(uid,obs,inventory[uid],old_raw if uid==uid0 else None)
                if (row.get("stop")=="migration_restoration" and uid in auth["allowed_units"]
                        and row["migration"]["migration_counters"].get("reason")=="ir_operation_type_or_operand_differ"):
                    row=check_switch(row,obs)
                if "stop" in row:
                    save(DEST/"stop.json",row)
                    raise ValueError("Unmatched "+row["stop"]+" at "+uid)
                if i==1:
                    assert row["graph"]["origin"]==row["migration_graph"]["origin"]=="sealed"
                    assert row["migration"]["migration_counters"]["yul_switches"]
                    print("Stopped graph pair passed on its original compiler witnesses",flush=True)
            except Exception as error:
                if not (DEST/"stop.json").exists():
                    save(DEST/"stop.json",dict(unit_id=uid,reason=str(error),traceback=traceback.format_exc()))
                raise
            counts["exact"]+=int(row["score"]["exact"])
            counts["migration"]+=int(row["migration"]["exact"])
            counts["raw_exact"]+=int(row["migration"]["raw_migration_score"]["exact"])
            counts["yul_switch_witnesses"]+=bool(row["migration"]["migration_counters"].get("yul_switches"))
            for key in ("graph","migration_graph"):
                ref=row[key]
                counts[key+"_"+ref["origin"]]+=1
                if ref["origin"]=="new":
                    calls.update(ref["invocations"])
            stream.write(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n")
            stream.flush()
            if i%15==0: print(i,"of",1+len(remaining),"validated",flush=True)
    assert counts["exact"]==counts["migration"]==len(remaining)+1
    assert counts["graph_new"]==counts["migration_graph_new"]==len(remaining)
    save(DEST/"acceptance.json",dict(accepted_before=len(done),continued=counts,combined=len(order),
         tool_invocations=calls,extra_solc_witnesses=len(list((DEST/"witnesses").glob("*/*/invocation.json"))),
         seconds=round(time.monotonic()-start,3),scores_sha256=sha((DEST/"package_scores.jsonl").read_bytes())))
    print("Complete",counts, calls,flush=True)


if __name__=="__main__":
    main()
