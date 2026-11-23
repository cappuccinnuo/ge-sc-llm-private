"""Continue the original fixed plan, joining earlier receipts by unit ID and graph hash."""
from collections import Counter
import json
from pathlib import Path
from move import OUT, OLD, SCRATCH, rows, sha, base_contents, load_trusted_compilers, measure, write
from check_delivery import read, digest
from literal_exception import explain as explain_literal
from observed_yul import explain as explain_yul

def collect():
    approval=read("yul_authorization.json")
    assert approval["request_sha256"]==digest(OUT/"observed_yul_positions.json")
    assert read("checkpoint_79.json")["remaining"]==121
    sealed=read("checkpoint_seal.json")["batch_files_excluding_self"]
    for filename in ("move_plan.json","natspec_request.json","moves_accepted.jsonl","unexplained_move_stop.json",
                     "literal_rest_of_graph.json","observed_yul_positions.json"):
        assert digest(OUT/filename)==sealed[filename]
    plan=read("move_plan.json")["rows"]
    updates={x["unit_id"]:x for x in read("natspec_request.json")["rows"]}
    history=list(rows(OUT/"moves_accepted.jsonl"))+[read("unexplained_move_stop.json")["row"]]
    assert len(history)==79 and [r["unit_id"] for r in history]==[r["unit_id"] for r in plan[:79]]
    bases={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    compilers=load_trusted_compilers()[0]
    counts,corpora=Counter(),Counter()
    proofs=[]
    with (OUT/"moves_completed.jsonl").open("x",encoding="utf8") as f:
        for i,r in enumerate(plan):
            uid=r["unit_id"]
            base=bases[uid]
            if i<len(history):
                row=history[i]
                counts["previous_trials"]+=1
            else:
                if uid in updates:
                    site=r["site"];start=updates[uid]["start"];raw=base_contents(base)[site["file"]]
                    assert sha(raw[start:site["start"]])==updates[uid]["comment_sha256"]
                    r=dict(r,site=dict(site,start=start,body_sha256=sha(raw[start:site["end"]]),function_start=site["start"]))
                row=measure(base,r,compilers[r["version"]],output_root=SCRATCH.parent/"position_continuation")
                counts["new_trials"]+=1
            if not row.get("stop"):
                outcome="all_kept_facts_equal"
            elif i in (75,78):
                outcome,proof_name={75:("verified_creation_literal_difference","literal_rest_of_graph.json"),
                                    78:("yul_source_start_raw","observed_yul_positions.json")}[i]
                proof=read(proof_name)
                assert proof["unit_id"]==uid and proof["unchanged_official_score"]==row["score"]
                proofs.append(dict(proof,kind=outcome))
            else:
                reasons={}
                if row["stop"]=="movement_score":
                    for outcome,explain in (("verified_creation_literal_difference",explain_literal),
                                            ("yul_source_start_raw",explain_yul)):
                        try:
                            proof=explain(row,base)
                        except (AssertionError,KeyError,ValueError,IndexError) as exc:
                            reasons[outcome]=type(exc).__name__+": "+str(exc)
                        else:
                            proofs.append(dict(proof,kind=outcome));break
                    else:
                        outcome="unexplained"
                else:outcome="unexplained"
                if outcome=="unexplained":
                    write("position_continuation_stop.json",dict(row=row,prior_completed=i,reasons=reasons))
                    raise RuntimeError("stopped "+uid)
            row=dict(row,outcome=outcome)
            f.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n");f.flush()
            s=row["score"]
            counts["measured"]+=1;counts[outcome]+=1;corpora[row["corpus"]]+=1
            counts["projects"]+=bool(base["project_root"])
            counts["raw_kept_below_one"]+=s["raw"]["kept"]["ratio"]<1
            counts["raw_any_below_one"]+=any(s["raw"][k]["ratio"]<1 for k in ("kept","calls","cfg_edges"))
            counts[s["counter_correspondence"]["status"]]+=1
            if (i+1)%25==0:print("Measured",i+1,flush=True)
    assert counts["measured"]==len(plan)==200 and counts["new_trials"]==121
    write("measured_differences.json",proofs)
    write("move_summary.json",dict(counts=counts,corpora=corpora,rows_file="moves_completed.jsonl",
                                   rows_sha256=digest(OUT/"moves_completed.jsonl")))
    print(counts,corpora)
if __name__=="__main__":collect()
