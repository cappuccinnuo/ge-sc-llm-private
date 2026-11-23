"""Use the same 200 functions with leading documentation attached, retaining valid results."""
import json
from collections import Counter
from move import OUT, SCRATCH, OLD, rows, write, measure, load_trusted_compilers, base_contents, sha


def main():
    auth=json.loads((OUT/"natspec_authorization.json").read_bytes())
    scope=json.loads((OUT/"natspec_request.json").read_bytes())
    assert sha((OUT/"natspec_request.json").read_bytes())==auth["request_sha256"]
    previous={r["unit_id"]:r for r in rows(OUT/"moves.jsonl") if "stop" not in r}
    updated={r["unit_id"]:r for r in scope["rows"]}
    selected=json.loads((OUT/"move_plan.json").read_bytes())["rows"]
    bases={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    compilers=load_trusted_compilers()[0]
    counts,corpora=Counter(),Counter()
    with (OUT/"moves_final.jsonl").open("x",encoding="utf8") as fp:
        for r in selected:
            uid=r["unit_id"]
            if uid in previous and uid not in updated:
                row=previous[uid]
                counts["reused"]+=1
            else:
                if uid in updated:
                    site=r["site"];start=updated[uid]["start"]
                    raw=base_contents(bases[uid])[site["file"]]
                    assert sha(raw[start:site["start"]])==updated[uid]["comment_sha256"]
                    fragment=raw[start:site["end"]]
                    r=dict(r,site=dict(site,start=start,body_sha256=sha(fragment),function_start=site["start"]))
                row=measure(bases[uid],r,compilers[r["version"]],output_root=SCRATCH.parent/"documented_moves")
                counts["new_calls"]+=1
            fp.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n");fp.flush()
            if row.get("stop"):
                write("documented_move_stop.json",row)
                raise ValueError((uid,row["stop"]))
            score=row["score"]
            counts["passed"]+=1;corpora[r["corpus"]]+=1
            counts["project"]+=bool(bases[uid]["project_root"])
            counts["raw_kept_below_one"]+=score["raw"]["kept"]["ratio"]<1
            counts["raw_any_below_one"]+=any(score["raw"][k]["ratio"]<1 for k in ("kept","cfg_edges","calls"))
            counts[score["counter_correspondence"]["status"]]+=1
    assert counts["passed"]==len(selected)==200 and counts["reused"]==46 and counts["new_calls"]==154
    write("move_summary.json",dict(counts=counts,corpora=corpora,adjusted_edit_ranges=len(updated),
                                   rows_sha256=sha((OUT/"moves_final.jsonl").read_bytes())))
    print(counts,corpora)
if __name__=="__main__":main()
