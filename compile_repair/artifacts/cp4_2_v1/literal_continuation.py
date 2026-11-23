"""Continue the fixed plan, preserving literal mismatches only with a full byte-level explanation."""
from collections import Counter
import json
from pathlib import Path
from move import OUT, OLD, SCRATCH, rows, sha, base_contents, load_trusted_compilers, measure, write
from literal_exception import explain

def main():
    auth=json.loads((OUT/"literal_authorization.json").read_bytes())
    assert sha((OUT/"creation_literal_request.json").read_bytes())==auth["request_sha256"]
    plan=json.loads((OUT/"move_plan.json").read_bytes())["rows"]
    updates={x["unit_id"]:x for x in json.loads((OUT/"natspec_request.json").read_bytes())["rows"]}
    done=list(rows(OUT/"moves_final.jsonl"))
    assert len(done)==76 and done[-1]["unit_id"]==auth["stop"] and not any(r.get("stop") for r in done[:-1])
    assert [r["unit_id"] for r in done]==[r["unit_id"] for r in plan[:76]]
    bases={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    compilers=load_trusted_compilers()[0]
    counts,corpora=Counter(),Counter();exceptions=[]
    with (OUT/"moves_accepted.jsonl").open("x",encoding="utf8") as fp:
        for i,r in enumerate(plan):
            uid=r["unit_id"];base=bases[uid]
            if i<len(done):
                row=done[i]
                counts["existing_measured"]+=1
            else:
                if uid in updates:
                    site=r["site"];start=updates[uid]["start"];raw=base_contents(base)[site["file"]]
                    assert sha(raw[start:site["start"]])==updates[uid]["comment_sha256"]
                    r=dict(r,site=dict(site,start=start,body_sha256=sha(raw[start:site["end"]]),function_start=site["start"]))
                row=measure(base,r,compilers[r["version"]],output_root=SCRATCH.parent/"literal_continuation")
                counts["new_trials"]+=1
            if row.get("stop"):
                try:
                    assert row["stop"]=="movement_score" and row["score"]["counter_correspondence"]["status"]=="rejected"
                    detail=explain(row,base)
                except Exception as exc:
                    write("unexplained_move_stop.json",dict(row=row,reason=str(exc),error_type=type(exc).__name__))
                    raise
                exceptions.append(detail)
                row=dict(row,outcome="verified_creation_literal_difference")
            else:
                row=dict(row,outcome="all_kept_facts_equal")
            fp.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n");fp.flush()
            s=row["score"];counts["measured"]+=1;counts[row["outcome"]]+=1;corpora[row["corpus"]]+=1
            counts["projects"]+=bool(base["project_root"])
            counts["raw_kept_below_one"]+=s["raw"]["kept"]["ratio"]<1
            counts["raw_any_below_one"]+=any(s["raw"][k]["ratio"]!=1 for k in ("kept","calls","cfg_edges"))
            counts[s["counter_correspondence"]["status"]]+=1
            if (i+1)%25==0:print("Measured",i+1,flush=True)
    assert counts["measured"]==len(plan)==200 and counts["new_trials"]==124
    write("known_creation_differences.json",exceptions)
    write("move_summary.json",dict(counts=counts,corpora=corpora,rows_file="moves_accepted.jsonl",
                                   rows_sha256=sha((OUT/"moves_accepted.jsonl").read_bytes())))
    print(counts,corpora)
if __name__=="__main__":main()
