"""Complete the remaining frozen package checks after recognizing the NewArray definition layout."""
from collections import Counter
import json
from pathlib import Path
import sys
import traceback

DEST = Path(__file__).resolve().parent
sys.path.insert(0,str(DEST.parent))
sys.path.insert(0,str(DEST.parent/"yul_continuation"))
from resume import archived, check_switch
from resume_migrations import checked, evaluate, load_inputs, restore_scores, setup, sha
from witness import save


def main():
    p = DEST.parent
    auth = json.loads((DEST/"authorization.json").read_bytes())
    checked(p/"yul_continuation/definition_review.json",auth["request_sha256"])
    stop = json.loads(checked(p/"yul_continuation/stop.json",auth["stop_sha256"]))
    closed = [json.loads(s) for f,h in auth["closed_outputs"].items() for s in checked(p/f,h).splitlines()]
    done = {r["unit_id"] for r in closed}
    uid0 = stop["unit_id"]
    assert uid0==auth["stopped_pair"] and len(done)==len(closed)==auth["previously_accepted"]
    assert all(r["score"]["exact"] and r["migration"]["exact"] for r in closed)
    order, observations, _, stored = load_inputs()
    todo = [uid for uid in order if uid not in done and uid!=uid0]
    assert len(todo)==auth["remaining_new_pairs"] and uid0 not in done
    assert all("exact" not in stored[uid] and "migration" not in stored[uid] for uid in todo)
    stored[uid0]=dict(exact=archived(stop["graph"]),migration=archived(stop["migration_graph"]))
    prior=dict(score=stop["score"],migration=stop["migration"]["raw_migration_score"])
    setup(restore_scores)
    assert restore_scores.LOCAL.name=="definition_continuation"
    counts, calls = Counter(), Counter()
    with (DEST/"package_scores.jsonl").open("x",encoding="utf8") as stream:
        for i,uid in enumerate([uid0]+todo,1):
            try:
                obs=observations[uid]
                restore_scores.STAGE=obs["cohort"]
                row=evaluate(uid,obs,stored[uid],prior if uid==uid0 else None)
                if (row.get("stop")=="migration_restoration" and uid in auth["approved_yul_units"] and
                        row["migration"]["migration_counters"].get("reason")=="ir_operation_type_or_operand_differ"):
                    row=check_switch(row,obs)
                if "stop" in row:
                    save(DEST/"stop.json",row)
                    raise ValueError("Unmatched "+row["stop"]+" at "+uid)
                if i==1:
                    changes=row["migration"]["migration_counters"]["renamed"]
                    assert changes["TMP_303"]=="TMP_200" and changes["TMP_366"]=="TMP_263"
                    assert row["graph"]["origin"]==row["migration_graph"]["origin"]=="sealed"
                    print("Both NewArray definitions validated on sealed graphs",flush=True)
                assert row["score"]["exact"] and row["migration"]["exact"]
            except Exception as error:
                if not (DEST/"stop.json").exists():
                    save(DEST/"stop.json",dict(unit_id=uid,reason=str(error),traceback=traceback.format_exc()))
                raise
            counts["passed"]+=1
            counts["raw_exact"]+=int(row["migration"]["raw_migration_score"]["exact"])
            for k in ("graph","migration_graph"):
                ref=row[k]
                counts[k+"_"+ref["origin"]]+=1
                if ref["origin"]=="new":calls.update(ref["invocations"])
            stream.write(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n")
            stream.flush()
            if i%15==0:print(i,"of",len(todo)+1,"validated",flush=True)
    assert counts["graph_new"]==counts["migration_graph_new"]==len(todo)
    assert len(done)+counts["passed"]==len(order)==114
    save(DEST/"acceptance.json",dict(preserved=len(done),counts=counts,tool_invocations=calls,
         combined=len(order),scores_sha256=sha((DEST/"package_scores.jsonl").read_bytes())))
    print("All package migrations completed",counts,calls,flush=True)
if __name__=="__main__":main()
