"""Collect completed EP4 receipts; never uses statistics to alter features."""
import argparse
from collections import Counter
from pathlib import Path
from scripts.edge_sem.io import read, ref, checked, write, ROOT
from .ep4_common import OUT, TASKS

def collect(attributes):
    root=Path(attributes).resolve()
    batch=read(root/"summary.json")
    tasks={}
    for task in TASKS:
        manifest=read(checked(batch["tasks"][task]))
        stats=read(checked(batch["stats"][task]))
        diagnostics=read(checked(manifest["diagnostics"]))
        gaps=Counter(g for r in diagnostics["edges"] for g in r["source_gaps"])
        unknown=Counter(reason for r in diagnostics["edges"] for values in r["unknown_fields"].values() for reason in values)
        tasks[task]=dict(manifest=batch["tasks"][task],stats=batch["stats"][task],
            totals=stats["totals"],by_relation=stats["by_relation"],
            diagnostic_edges=len(diagnostics["edges"]),source_gaps=dict(gaps),
            unknown_reasons=dict(unknown),cfg=diagnostics["cfg"],
            fact_provenance=manifest["facts"])
    executions={}
    for p in sorted((OUT/"execution").glob("*.json")):
        if p.name.endswith(".started.json"):continue
        r=read(p)
        if "log" in r:checked(r["log"])
        executions[p.stem]=dict(receipt=ref(p),**r)
    result=dict(stage="EP4",attributes=ref(root/"summary.json"),
        selection=read(checked(batch["selection"])),tasks=tasks,execution=executions,
        rebuild={t:read(OUT/"rebuild"/(t+".json")) for t in TASKS+("reentrancy_contract","access_control_contract")},
        frozen_baseline=ref(OUT/"before.json"),training_executed=False,gpu_executed=False)
    write(OUT/"summary.json",result)
    print("EP4 result summary recorded",flush=True)
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--attributes",required=True)
    args=parser.parse_args();collect(args.attributes)
