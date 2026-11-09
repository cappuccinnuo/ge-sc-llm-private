"""Final NS-P9 read-only verification; checks predictions again without any model."""
import argparse
import hashlib
import subprocess
from pathlib import Path
from .summary import (ART, BASE, DEFAULT, BATCHES, SELECTED, Sources, read, write,
                      reference, same, aligned_rows, node_key, node_join, compare_prior_tables)
from scripts.DFG.dfg_v2.experiment.stats import aggregate_metrics


def verify(root=DEFAULT):
    root=Path(root);sources=Sources()
    complete=read(sources.root(root/"report_complete.json"))
    sources.refs(complete["artifacts"]);sources.check(complete["report"])
    unique={}
    for path in (root/"collection_attempt3/reports/source_audit.json",
                 root/"cases_attempt2/source_audit.json",root/"edge_review/source_audit.json",
                 root/"reports/finalization_sources.json"):
        for r in read(path):
            if r["path"]in unique and r["sha256"]!=unique[r["path"]]["sha256"]:
                raise ValueError("Conflicting source digest")
            unique[r["path"]]=r
    for r in unique.values():sources.check(r)
    labels={};tables={};splits={}
    for batch in BATCHES:
        batchroot=ART/("batch_"+batch+"_v1")
        plan=sources.json(read(batchroot/"plan.seal.json")["plan"])
        report=read(batchroot/"reports/report.json")
        if not same(aggregate_metrics(read(batchroot/"reports/fold_metrics.json")),report["aggregates"]):
            raise ValueError("Source aggregate differs")
        done=read(batchroot/"complete.json")
        for ref in done["receipts"]:
            rc=sources.json(ref);j=rc["job"]
            task,config,fold=j["task_id"],j["name"],j["fold"]
            if not task.endswith("_node")or j["profile"]!="G3R"or config not in SELECTED:continue
            splitkey=task,fold
            if splitkey in splits and not same(splits[splitkey],j["split"]):raise ValueError("Cross-configuration split differs")
            splits[splitkey]=j["split"]
            if task not in labels:labels[task]=sources.json(j["label_view"])[task]
            predicted=next(r for r in rc["artifacts"]if r["path"].endswith("/fit/outer_test_predictions.json"))
            rows=aligned_rows(sources.json(predicted),j,{task:labels[task]})
            dest=tables.setdefault(task,{}).setdefault(config,{})
            for row in rows:
                key=node_key(row)
                if key in dest:raise ValueError("Duplicate OOF identity")
                dest[key]=dict(row,fold=fold)
    joined=[]
    for task in sorted(tables):
        joined.extend(dict(r,task_id=task)for r in node_join(tables[task]))
    if not same(joined,read(root/"reports/positive_nodes.json")):
        raise ValueError("Final positive tables differ")
    old=compare_prior_tables(joined,sources)
    prefixes=read(root/"document_prefixes.json")
    for name,r in prefixes.items():
        data=Path(name).read_bytes()
        if hashlib.sha256(data[:r["bytes"]]).hexdigest()!=r["sha256"]:
            raise ValueError("Historical document prefix changed")
    changed=subprocess.check_output(["git","diff","--name-only"],text=True).splitlines()
    if set(changed)-set(prefixes):
        raise ValueError("Tracked historical files changed: "+str(changed))
    from scripts.DFG.dfg_v2.benchmark_v2 import execution
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    h8=BASE.parents[0]/"DFG/experiments/artifacts/dfg_v2/prompt8h_v1"
    execution.load(h8/"plan.json")
    if _code_refs()!=read(h8/"runtime_resume_v2.json")["runtime"]:raise ValueError("Frozen runtime changed")
    write(root/"source_inventory.json",sorted(sources.verified.values(),key=lambda r:r["path"]))
    result=dict(passed=True,source_files=len(sources.verified),
        source_bytes=sum(r["bytes"]for r in sources.verified.values()),
        all_original_sources_rehashed=True,positive_nodes_bit_exact=True,
        identity_includes=["task","fold","file","source_sha256","source_id","original_graph_node_id","node_type"],
        prior_tables=old,old_document_prefixes_unchanged=True,old_tracked_code_unchanged=True,
        frozen_8H_load=True,frozen_computation_files=len(_code_refs()),
        formal_training=0,formal_model_evaluations=0,new_features=0,LLM_calls=0)
    write(root/"verification/final_readonly.json",result)
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(DEFAULT));print(verify(p.parse_args().root))
