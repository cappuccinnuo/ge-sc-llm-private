"""Combine the original observations and two disjoint new draws without pooling old/new edit identities."""
from collections import Counter, defaultdict
import csv
from batch import *

def acc(stats,key,item,phase):
    st=stats[key]
    st[phase+"_sampled"]+=1
    st[phase+"_"+item["outcome"]]+=1
    if phase=="original":
        st["before_included"]+=int(item["old_outcome"]=="included")
        st["promoted"]+=int(item["outcome"]=="included" and item["old_outcome"]!="included")
        st["removed"]+=int(item["outcome"]!="included" and item["old_outcome"]=="included")

def tsv(name,records):
    with (OUT/name).open("x",encoding="utf8",newline="") as fp:
        fields=list(records[0]);wr=csv.DictWriter(fp,fieldnames=fields,delimiter="\t",lineterminator="\n")
        wr.writeheader();wr.writerows(records)

def main():
    old=json.loads(frozen(OLD/"benchmark_counts.json"))
    base_rows={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    counts=Counter();operators=defaultdict(Counter);strata=defaultdict(Counter);splits=defaultdict(Counter)
    control=json.loads(frozen(OLD/"control_acceptance.json"))
    checked(OLD/"control_plan.json",control["plan_sha256"])
    checked(OLD/"controls.jsonl",control["receipts_sha256"])
    checked(control["external_seal_path"],control["external_seal_sha256"])
    assert control["passed"]==200 and all(r["passed"] for r in rows(OLD/"controls.jsonl"))
    seen=set();toolcalls=defaultdict(Counter);packages=Counter();all_samples=0
    for stage,path in (("original","original_reclassified.jsonl.gz"),("new","new_observations.jsonl.gz"),("supplement","supplement_observations.jsonl.gz")):
        if stage!="original":
            checked(OUT/path,load(stage+"_execution.json")["observations_sha256"])
        for r in rows(OUT/path):
            phase="original" if stage=="original" else "new"
            identity=(phase,r["operator"],r["unit_id"])
            assert identity not in seen and r["seed"]==20261122
            seen.add(identity);all_samples+=1
            data=base_rows[r["unit_id"]]
            assert all(r[k]==data[k] for k in ("corpus","series","split","group"))
            counts[stage,r["outcome"]]+=1
            calls=toolcalls[stage]
            calls["selected_solc"]+=int(r["selected_attempted"])
            calls["environment_solc"]+=r["environment_solc_calls"]
            calls["environment_slither"]+=r["environment_slither_calls"]
            acc(operators,r["operator"],r,phase)
            acc(strata,(r["operator"],r["corpus"],r["series"]),r,phase)
            acc(splits,r["split"],r,phase)
            if stage!="original" and r["operator"]=="unresolved_package_import":
                packages[r["corpus"],r["package"],r["outcome"]]+=1
    available=Counter()
    for r in load("new_sampling.json")["strata"]:
        available[r["operator"],r["corpus"],r["series"]]+=r.get("applicable",0)
    for r in rows(OUT/"supplement_plan.jsonl.gz"):
        available[r["operator"],r["corpus"],r["series"]]+=1
    for (o,c,s),count in available.items():
        strata[o,c,s]["new_operator_applicable"]=count
        operators[o]["new_operator_applicable"]+=count
    keys=("before_included","original_sampled","original_included","promoted","removed","new_operator_applicable",
        "new_sampled","new_included","new_not_triggered","new_resolved_by_environment","final_included")
    def expand(st):
        st["final_included"]=st["original_included"]+st["new_included"]
        return {key:st[key] for key in keys}
    all_ops=[dict(operator=op,**expand(operators[op])) for op in old["operators"]]
    assert len(all_ops)==22
    tsv("operators.tsv",all_ops)
    tsv("strata.tsv",[dict(operator=o,corpus=c,series=s,**expand(st)) for (o,c,s),st in sorted(strata.items())])
    assert all_samples==old["planned"]+load("new_sampling.json")["planned"]+load("supplement_sampling.json")["added"]
    assert sum(r["original_sampled"] for r in all_ops)==17432
    assert sum(r["before_included"] for r in all_ops)==11858
    assert not any(r["removed"] for r in all_ops)
    assert toolcalls["original"]==Counter(old["tool_calls"])
    totals={k:sum(r[k] for r in all_ops) for k in keys}
    totals["sampled"]=all_samples
    saved("population.json",dict(base_population=len(base_rows),observation_counts=[dict(cohort=c,outcome=o,units=n)
        for (c,o),n in sorted(counts.items())],old_control_passes=control["passed"],old_control_sha256=control["receipts_sha256"],
        totals=totals,by_operator=all_ops,by_split={key:expand(st) for key,st in sorted(splits.items())},
        package_counts=[dict(corpus=c,package=p,outcome=o,units=n) for (c,p,o),n in sorted(packages.items())],
        tool_calls=dict(toolcalls),historical_calls_reclassified_only=True))
    print("sampled",all_samples,"included",totals["final_included"],"promoted",totals["promoted"])
if __name__=="__main__":main()
