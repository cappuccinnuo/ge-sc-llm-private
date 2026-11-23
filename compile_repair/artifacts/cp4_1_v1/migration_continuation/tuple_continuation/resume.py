"""Continue only unfinished package checks under the separately approved TUPLE namespace."""
from collections import Counter
import json
from pathlib import Path
import sys
import time
import traceback

DEST = Path(__file__).resolve().parent
sys.path.insert(0, str(DEST.parent))
from resume_migrations import evaluate, load_inputs, restore_scores, setup
from batch import checked, sha


def save(name, value):
    with (DEST/name).open("x", encoding="utf8") as fp:
        json.dump(value, fp, indent=2, ensure_ascii=False)
        fp.write("\n")


def sealed_ref(ref):
    checked(ref["journal_path"], ref["journal_sha256"])
    return {k:v for k,v in ref.items() if k not in ("origin","journal_path","journal_sha256","invocations")}


def main():
    start = time.monotonic()
    auth = json.loads((DEST/"authorization.json").read_bytes())
    parent = DEST.parent
    checked(parent/"tuple_review.json",auth["request_sha256"])
    stop = json.loads(checked(parent/"results/stop.json",auth["input_stop_sha256"]))
    closed = [json.loads(s) for s in checked(parent/"results/package_scores.jsonl",auth["accepted_scores_sha256"]).splitlines()]
    passed = {r["unit_id"] for r in closed}
    assert len(passed)==len(closed)==auth["previously_passed"] and all(r["migration"]["exact"] and r["score"]["exact"] for r in closed)
    uid0 = stop["unit_id"]
    order, observed, _, stored = load_inputs()
    remaining = [uid for uid in order if uid not in passed and uid!=uid0]
    assert len(remaining)==auth["new_physical_pairs"] and uid0 not in passed and uid0 in order
    assert all("exact" not in stored[uid] and "migration" not in stored[uid] for uid in remaining)
    stored[uid0] = dict(exact=sealed_ref(stop["graph"]),migration=sealed_ref(stop["migration_graph"]))
    previous_raw = dict(score=stop["score"],migration=stop["migration"]["raw_migration_score"])
    setup(restore_scores)
    assert restore_scores.LOCAL.name=="tuple_continuation"
    counts, calls = Counter(), Counter()
    with (DEST/"package_scores.jsonl").open("x",encoding="utf8") as output:
        for i, uid in enumerate([uid0]+remaining,1):
            observation=observed[uid]
            restore_scores.STAGE=observation["cohort"]
            try:
                row=evaluate(uid,observation,stored[uid],previous_raw if uid==uid0 else None)
            except Exception as error:
                row=dict(unit_id=uid,stop=type(error).__name__,reason=str(error),traceback=traceback.format_exc())
            if "stop" in row:
                save("stop.json",row)
                raise ValueError("First unmatched restoration at "+uid+": "+row["stop"])
            m=row["migration"]
            tuples={k:v for k,v in m["migration_counters"]["renamed"].items() if k.startswith("TUPLE_")}
            if i==1:
                assert tuples=={"TUPLE_0":"TUPLE_1"} and row["migration_graph"]["origin"]=="sealed" and row["graph"]["origin"]=="sealed"
                print("cp3_03927 verified on the two previously generated graphs",flush=True)
            counts["with_tuple_changes"]+=bool(tuples)
            counts["raw_exact"]+=int(m["raw_migration_score"]["exact"])
            counts["exact"]+=int(row["score"]["exact"])
            counts["migration_exact"]+=int(m["exact"])
            for mode in ("graph","migration_graph"):
                ref=row[mode]
                counts[mode+"_"+ref["origin"]]+=1
                if ref["origin"]=="new":calls.update(ref["invocations"])
            output.write(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n")
            output.flush()
            if i%20==0:print("Validated",i,"of",len(remaining)+1,flush=True)
    assert counts["graph_new"]==counts["migration_graph_new"]==len(remaining)
    assert counts["exact"]==counts["migration_exact"]==len(remaining)+1
    save("acceptance.json",dict(previously_accepted=len(passed),continued=counts["exact"],combined=len(order),
         passed=True,counts=counts,observed_new_tool_calls=calls,elapsed_seconds=round(time.monotonic()-start,3),
         scores_sha256=sha((DEST/"package_scores.jsonl").read_bytes())))
    print("Complete",counts,calls,flush=True)


if __name__=="__main__":
    main()
