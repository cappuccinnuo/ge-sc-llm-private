"""Summarize verified, read-only diagnostics; no model selection or new scoring rule."""
import argparse,csv,json,statistics
from pathlib import Path
from scripts.DFG.experiments.common import read_json,write_json,sha256
from .contract_readout import csv_write,TASKS,VARIANTS

def load(path):
    with Path(path).open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))

def number(row,key):return float(row[key])
def flag(row,key):return row[key]=="True"
def mean(xs):return statistics.mean(xs) if xs else None

def run(source,label_context,output):
    source,label_context,output=map(Path,(source,label_context,output))
    if output.exists():raise FileExistsError("New summary directory required")
    summary=read_json(source/"summary.json")
    if summary["status"]!="complete" or summary["checkpoints"]!=30 or summary["fits"]!=0:raise ValueError("Incomplete diagnostic")
    expected={(t,f,v) for t in TASKS for f in range(5) for v in VARIANTS}
    jobs=summary["jobs"]
    if len(jobs)!=30 or {(j["task_id"],j["fold"],j["variant"]) for j in jobs}!=expected:raise ValueError("Wrong 30-checkpoint matrix")
    # Verify every per-model table against its receipt, then compare consolidated exports.
    file_rows=[];node_rows=[]
    for job in summary["jobs"]:
        folder=source/job["task_id"]/("fold_"+str(job["fold"]))/job["variant"]
        receipt=read_json(folder/"receipt.json")
        if receipt!=job:raise ValueError("Receipt mismatch")
        if set(job["artifacts"])!={"files.csv","nodes.csv"}:raise ValueError("Wrong diagnostic artifact set")
        for name,digest in job["artifacts"].items():
            if sha256(folder/name)!=digest:raise ValueError("Table digest mismatch")
        file_rows.extend(load(folder/"files.csv"));node_rows.extend(load(folder/"nodes.csv"))
    if file_rows!=load(source/"contract_files.csv") or node_rows!=load(source/"node_contributions.csv"):raise ValueError("Consolidated table mismatch")
    if len(file_rows)!=768 or len(node_rows)!=95232:raise ValueError("Incomplete identity population")
    index={}
    for r in file_rows:
        k=tuple(r[x] for x in ("task_id","fold","file","source_sha256","variant"))
        if k in index:raise ValueError("Duplicate identity")
        index[k]=r
    paired=[]
    for r in file_rows:
        if r["variant"]!="HCG":continue
        key=tuple(r[x] for x in ("task_id","fold","file","source_sha256"))
        for variant in VARIANTS[1:]:
            v=index[key+(variant,)]
            if v["target"]!=r["target"] or v["nodes"]!=r["nodes"]:raise ValueError("Pair identity mismatch")
            paired.append(dict(task_id=r["task_id"],fold=r["fold"],file=r["file"],source_sha256=r["source_sha256"],
                baseline="HCG",variant=variant,target=r["target"],baseline_prediction=r["prediction"],prediction=v["prediction"],
                outcome=r["outcome"],margin_delta=number(v,"margin")-number(r,"margin"),
                probability_delta=number(v,"probability")-number(r,"probability"),
                max_local_margin_delta=number(v,"max_local_margin")-number(r,"max_local_margin")))
    groups=[]
    for task in TASKS:
        for variant in VARIANTS:
            for outcome in ("TP","TN","FP","FN"):
                rows=[r for r in file_rows if r["task_id"]==task and r["variant"]==variant and r["outcome"]==outcome]
                groups.append(dict(task_id=task,variant=variant,outcome=outcome,files=len(rows),
                    positive_local_evidence=sum(number(r,"positive_local_margin_nodes")>0 and flag(r,"reference_actual_class_agree") for r in rows),
                    reference_actual_class_disagreements=sum(not flag(r,"reference_actual_class_agree") for r in rows),
                    mixed_signs=sum(flag(r,"mixed_local_margin_signs") for r in rows),
                    mean_nodes=mean([number(r,"nodes") for r in rows]),median_nodes=statistics.median([number(r,"nodes") for r in rows]) if rows else None,
                    mean_margin=mean([number(r,"margin") for r in rows]),
                    mean_local_positive_fraction=mean([number(r,"positive_local_margin_nodes")/number(r,"nodes") for r in rows])))
    errors=[r for r in file_rows if r["outcome"] in ("FP","FN")]
    # Display contributions for every mistake, not just selected hard files. No new classification.
    top_nodes=[]
    for r in errors:
        matches=[n for n in node_rows if all(n[k]==r[k] for k in ("task_id","variant","file","source_sha256"))]
        if len(matches)!=int(r["nodes"]):raise ValueError("Node identity mismatch")
        ranked=sorted(matches,key=lambda n:(-number(n,"local_margin_with_shared_bias"),n["original_graph_node_id"]))
        for rank,n in enumerate(ranked[:3],1):top_nodes.append(dict(n,rank=rank,graph_outcome=r["outcome"],graph_margin=r["margin"]))
    label_audit=read_json(label_context/"audit.json")
    if label_audit["status"]!="passed" or label_audit["labels_altered"]:raise ValueError("Label context invalid")
    output.mkdir(parents=True)
    for name,rows in [("outcome_groups.csv",groups),("paired_file_changes.csv",paired),("all_graph_errors.csv",errors),("error_top_nodes.csv",top_nodes)]:csv_write(output/name,rows)
    numerical=dict(reference_class_disagreements=sum(not flag(r,"reference_actual_class_agree") for r in file_rows),
        old_logit_tolerance_failures=sum(not flag(r,"old_logit_tolerance_passed") for r in file_rows),
        old_margin_tolerance_failures=sum(not flag(r,"old_margin_tolerance_passed") for r in file_rows),
        max_float64_identity_error=max(abs(number(r,"float64_identity_error")) for r in file_rows),
        max_pooling_margin_residual=max(abs(number(r,"pooling_margin_residual")) for r in file_rows),
        max_head_margin_residual=max(abs(number(r,"head_margin_residual")) for r in file_rows),
        max_actual_reference_margin_residual=max(abs(number(r,"actual_minus_reference_margin")) for r in file_rows),
        max_logit_residual=max(number(r,"reconstruction_max_abs_error") for r in file_rows),
        max_historical_probability_error=max(j["probability_max_abs_error"] for j in summary["jobs"]),
        all_head_replays_exact=all(j["head_replay_exact"] for j in summary["jobs"]))
    write_json(output/"analysis.json",dict(status="complete",score_role="cv_validation",checkpoint="best",fits=0,
        source_summary_sha256=sha256(source/"summary.json"),label_context_audit_sha256=sha256(label_context/"audit.json"),
        file_rows=len(file_rows),node_rows=len(node_rows),groups=groups,numerical=numerical,
        changed_predictions=sum(r["baseline_prediction"]!=r["prediction"] for r in paired),
        changed_probabilities=sum(r["probability_delta"]!=0 for r in paired),comparison_rows=len(paired),
        total_seconds=summary["seconds"],max_peak_allocated_mib=max(j["peak_allocated_mib"] for j in summary["jobs"]),
        max_peak_reserved_mib=max(j["peak_reserved_mib"] for j in summary["jobs"]),
        inference_boundary="Contribution is a contextual contract-head reference score, not a node label or a causal explanation; mixed signs alone do not identify pooling failure."))
    print(json.dumps(dict(status="complete",groups=groups,numerical=numerical),indent=2))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--source",required=True);p.add_argument("--label-context",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();run(a.source,a.label_context,a.output)
if __name__=="__main__":main()
