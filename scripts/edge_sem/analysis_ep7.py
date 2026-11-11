"""EP7 complete-only P2 fold report; historical 8H contrast is descriptive."""
import argparse
import csv
from collections import Counter
from pathlib import Path
import statistics
from . import execution as ex
from .io import read,write,ref,checked
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.experiment.run import _job_directory
from scripts.DFG.dfg_v2.benchmark_v2.retry import successful_attempt
from scripts.DFG.experiments.common import metrics


def summarize(path,output):
    path=Path(path);plan=ex.load(path,"verify")
    expected={(t,f) for t in ex.TASKS for f in range(10)}
    if (plan["scope"]!="formal" or len(plan["jobs"])!=20
        or {(j["task_id"],j["fold"]) for j in plan["jobs"]}!=expected
        or any(j["edge_profile"]!="G3R" for j in plan["jobs"])):
        raise ValueError("EP7 requires the complete 20-fold G3R matrix")
    source_path=checked(plan["source_h8_plan"]);source=h8.load(source_path)
    rows=[];pooled={t:[] for t in ex.TASKS};identities={t:set() for t in ex.TASKS}
    accepted=[]
    for j in plan["jobs"]:
        current=ex.verify_one(path,plan,j)
        old=[x for x in source["jobs"] if x["task_id"]==j["task_id"] and x["fold"]==j["fold"] and x["seed"]==1 and x["profile"]=="G3R"]
        if len(old)!=1:raise ValueError("8H baseline missing or ambiguous")
        folder=_job_directory(source_path.parent,old[0]);attempt=successful_attempt(folder)
        if attempt is None:raise ValueError("8H baseline receipt missing")
        previous=h8.verify_one(source_path,source,old[0],attempt)
        a,b=current["result"],previous["result"]
        predictions=read(Path(current["attempt"])/"outer_test_predictions.json")
        old_predictions=read(Path(previous["attempt"])/"outer_test_predictions.json")
        key=lambda r:(r["file"],r["original_graph_node_id"])
        old_table={key(r):r for r in old_predictions}
        if len(old_table)!=len(old_predictions) or set(old_table)!={key(r) for r in predictions}:raise ValueError("8H/P2 identities differ")
        if any(r["target"]!=old_table[key(r)]["target"] for r in predictions):raise ValueError("8H/P2 targets differ")
        if identities[j["task_id"]] & {key(r) for r in predictions}:raise ValueError("OOF duplicates")
        identities[j["task_id"]].update(key(r) for r in predictions);pooled[j["task_id"]].extend(predictions)
        for ck in ("best","last"):
            rows.append(dict(task_id=j["task_id"],fold=j["fold"],checkpoint=ck,
                p2_bf1=a["outer_test"][ck]["buggy_f1"],p2_macro_f1=a["outer_test"][ck]["macro_f1"],
                p2_precision=a["outer_test"][ck]["precision"],p2_recall=a["outer_test"][ck]["recall"],
                p2_confusion=a["outer_test"][ck]["tn_fp_fn_tp"],
                old_8h_bf1=b["outer_test"][ck]["buggy_f1"],
                delta_bf1_pp=a["outer_test"][ck]["buggy_f1"]-b["outer_test"][ck]["buggy_f1"],
                p2_best_epoch_1based=a["best_epoch"]+1,old_8h_best_epoch_1based=b["best_epoch"]+1,
                p2_epochs=a["history_rows"],old_8h_epochs=b["history_rows"],seconds=a["seconds"],
                peak_allocated_mib=a["resources"]["peak_allocated_mib"],peak_reserved_mib=a["resources"]["peak_reserved_mib"],
                initial_equal_8h=j["initial"]["state_sha256"]==j["historical_initial"]["state_sha256"]))
        accepted.append(dict(current=ref(Path(current["attempt"])/"receipt.json"),historical=ref(attempt/"receipt.json")))
    stats={}
    for task in ex.TASKS:
        stats[task]={}
        for ck in ("best","last"):
            selected=[r for r in rows if r["task_id"]==task and r["checkpoint"]==ck]
            values=[r["p2_bf1"] for r in selected];diff=[r["delta_bf1_pp"] for r in selected]
            stats[task][ck]=dict(mean_bf1=statistics.mean(values),sample_sd_bf1=statistics.stdev(values),
                mean_delta_bf1_pp=statistics.mean(diff),sample_sd_delta_pp=statistics.stdev(diff),
                improved=sum(v>0 for v in diff),tied=sum(v==0 for v in diff),declined=sum(v<0 for v in diff),
                best_epoch_distribution=dict(Counter(r["p2_best_epoch_1based"] for r in selected)),
                pooled_oof=metrics([r["target"] for r in pooled[task]],[r[ck] for r in pooled[task]]))
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    write(output/"folds.json",rows)
    with (output/"folds.csv").open("x",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
        w.writerows([dict(r,p2_confusion=json_confusion(r["p2_confusion"])) for r in rows])
    result=dict(passed=True,plan=ref(path),fits=20,summary=stats,receipts=accepted,
        comparisons="descriptive only; stopping and fresh-anchor initialization may both differ from historical 8H",
        independent_seed_replicates=False,unit="HCG node",primary_checkpoint="best")
    write(output/"summary.json",result);write(output/"summary.seal.json",dict(summary=ref(output/"summary.json")))
    return result

def json_confusion(row):return ",".join(str(x) for x in row)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--plan",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();summarize(a.plan,a.output)
