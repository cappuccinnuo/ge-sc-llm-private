"""Join the five completed scores with the outstanding 109, reproducing each historical proof in its own counter namespace."""
import gzip
import json
import re
from collections import Counter
import rescore as job
from rescore import CP41, MIG, OLD, OUT, checked, rows, sha

TOKEN=re.compile(r"(?<![\w$])(?:TMP|REF|TUPLE)_[0-9]+(?![\w$])")

def main():
    early={r["unit_id"] for r in rows(MIG/"results/package_scores.jsonl")}
    existing={r["unit_id"]:r for r in rows(OUT/"migration.jsonl.gz")}
    assert len(early)==21 and len(existing)==5
    job.mode="migration"
    job.bases={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    job.observations={(r["operator"],r["unit_id"],r["mutation_sha256"]):r for f in ("new_observations","supplement_observations")
                      for r in rows(CP41/(f+".jsonl.gz")) if r["operator"]=="unresolved_package_import"}
    statuses=Counter();diffs=[]
    with (OUT/"migrations_final.jsonl.gz").open("xb") as stream,gzip.GzipFile(filename="",fileobj=stream,mode="wb",mtime=0) as fp:
        for row in job.source_rows():
            if row["operator"]!="unresolved_package_import":continue
            uid=row["unit_id"]
            result=existing[uid] if uid in existing else job.score(row)
            original=row["migration"]
            score=result["score"]
            proof=score["migration_counters"]
            old_shape=dict(proof)
            if uid in early:
                ref=row["graph"]
                truth=json.loads(checked(ref["graph_path"],ref["graph_sha256"]))
                names={t for n in truth["nodes"] for op in n["ir"] for t in TOKEN.findall(op)}
                tuples=sorted(n for n in names if n.startswith("TUPLE_"))
                assert len(names)==proof["counter_count"] and not set(tuples).intersection(proof["renamed"])
                old_shape["counter_count"]=len(names)-len(tuples)
                if tuples:diffs.append(dict(unit_id=uid,unchanged_tuples=tuples,original_count=old_shape["counter_count"],current_count=len(names)))
            assert old_shape==original["migration_counters"] and score["exact"],uid
            assert all(score[k]==v for k,v in original.items() if k!="migration_counters"),uid
            result.update(historical_full_proof=old_shape,matched_in_historical_namespace=True)
            statuses[score["counter_correspondence"]["status"]]+=1
            fp.write((json.dumps(result,sort_keys=True,separators=(",",":"))+"\n").encode())
    assert sum(statuses.values())==114 and len(diffs)==7
    with (OUT/"migration_summary.json").open("x",encoding="utf8") as fp:
        json.dump(dict(units=114,reused_new_scores=5,remaining_scored=109,raw_and_accepted_scores_equal=114,
                       reconstructed_historical_full_proofs_equal=114,kept_status=statuses,
                       unchanged_tuple_names_previously_outside_scope=diffs),fp,indent=2);fp.write("\n")
    print("114 migrations verified",statuses)
if __name__=="__main__":main()
