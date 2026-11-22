"""Seal completed restoration receipts after both migration scoring stops. Never start a tool."""
from collections import Counter
from batch import *
from restore_scores import verify_graph

base={row["unit_id"]:row for row in rows(OLD/"bases.jsonl.gz")}
summary={}
output=[]
for stage in ("new","supplement"):
    checked(OUT/(stage+"_observations.jsonl.gz"),load(stage+"_execution.json")["observations_sha256"])
    included=[r for r in rows(OUT/(stage+"_observations.jsonl.gz")) if r["outcome"]=="included"]
    written={(r["operator"],r["unit_id"]):r for r in rows(OUT/(stage+"_scores.jsonl.gz"))}
    stop=load(stage+"_restoration_stop.json")
    counts=Counter()
    for obs in included:
        uid,op=obs["unit_id"],obs["operator"]
        folder=LOCAL/"restored"/stage/op/uid
        key=op,uid
        row=dict(cohort=stage,unit_id=uid,operator=op,mutation_sha256=obs["mutation_sha256"],complete_prior_score=key in written)
        for manner in ("exact","migration") if op=="unresolved_package_import" else ("exact",):
            store=folder/manner
            path=store/"units"/manner/"result.json"
            if not store.exists():continue
            if not path.is_file():raise ValueError("Interrupted physical receipt: "+str(store))
            expected=None
            old_score=written.get(key) or (stop if stop["unit_id"]==uid and stop["operator"]==op else None)
            if old_score:expected=old_score["graph" if manner=="exact" else "migration_graph"]["graph_sha256"]
            graph,ref=verify_graph(base[uid],path,sha(path.read_bytes()),expected)
            assert ref["d3"]
            row[manner]=ref
            counts[manner+"_physical_receipts"]+=1
        if key in written:counts["scored"]+=1
        output.append(row)
    summary[stage]=dict(included=len(included),stop=stop["unit_id"],records=counts,
        first_pass_score_file_sha256=sha((OUT/(stage+"_scores.jsonl.gz")).read_bytes()))
output_rows("migration_stop_receipts.jsonl.gz",output)
saved("migration_stop_inventory.json",dict(by_cohort=summary,sha256=sha((OUT/"migration_stop_receipts.jsonl.gz").read_bytes()),
    reason="Both initial scoring workers hit the first unmatched strict migration score; all completed receipts, including in-flight workers, are indexed."))
print(json.dumps(summary,sort_keys=True))
