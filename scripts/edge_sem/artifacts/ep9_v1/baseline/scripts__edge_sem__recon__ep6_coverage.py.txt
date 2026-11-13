
"""EP6 graph-space coverage; counts include only genuinely renamed files."""
from collections import Counter
from .common import read,write,checked
from .ep6_common import OUT,TASKS
from scripts.node_sem.facts_io import load_context
from scripts.edge_sem.attrs import edge_rows
from scripts.edge_sem.build_f4 import load_edges

def main():
    summary=read(OUT/"anonymous_gate/summary.json")
    if not summary["passed"]:raise ValueError("Anonymous gate failed")
    records=[read(checked(r)) for r in summary["files"]]
    results={}
    for task in TASKS:
        ctx=load_context(task)
        m=read(OUT/"attributes"/task/"manifest.json")
        rows=edge_rows(ctx["graphs"]["F3"],load_edges(checked(m["f4_manifest"])))
        selected=[r for r in records if r["task_id"]==task]
        renamed={r["file"] for r in selected if r["status"]=="renamed"}
        total=Counter();covered=Counter();reasons=Counter()
        for row in rows:
            groups=[row["relation"]]
            if row["relation"]=="CALL_SITE":groups.append("CALL_SITE:"+row["data"]["kind"])
            if row["relation"]=="GUARDS":
                groups.extend("GUARDS:"+kind for kind in row["data"]["kind"])
            for group in groups:
                total[group]+=1
                if row["file"] in renamed:covered[group]+=1
        for r in selected:
            if r["status"]=="fallback":
                for issue in r["fallback_issues"]:
                    reasons[str(issue.get("reason",issue.get("kind",issue)) if isinstance(issue,dict) else issue)]+=1
        results[task]=dict(files=len(selected),renamed_files=len(renamed),
            covered_edges=sum(row["file"] in renamed for row in rows),all_edges=len(rows),
            by_relation={k:dict(renamed=covered[k],total=v,fraction=covered[k]/v) for k,v in total.items()},
            fallback_reason_distribution=dict(reasons))
    write(OUT/"anonymous_gate/coverage.json",dict(tasks=results,
        note="Fallback is an unchanged-text control, not evidence for genuine renaming; GUARDS kind counts may overlap."))
    write(OUT/"prerequisites.json",dict(passed=True,
        checks={k:__import__("scripts.edge_sem.io",fromlist=["ref"]).ref(OUT/p) for k,p in
                (("f4","f4_delta.json"),("attributes","attribute_delta.json"),("anonymous","anonymous_gate/summary.json"),
                 ("coverage","anonymous_gate/coverage.json"),("tests","execution/prerequisite_tests/result.json"))}))
    print(results,flush=True)

if __name__=="__main__":main()
