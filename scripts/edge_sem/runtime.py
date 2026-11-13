"""Explicit EP7 training source set; diagnostics/tests are excluded."""
from pathlib import Path
from .io import ROOT,ref,checked,read,write
from scripts.DFG.dfg_v2.experiment.run import _code_refs

MODULES=(
 "__init__.py","materialize.py","init.py","model.py","model_relations.py",
 "model_attrs.py","hgt_edge.py","forward.py","placebo.py","attrs.py","attr_sources.py",
 "attr_batch.py","attr_stats.py","build_f4.py","call_resolve.py","guard_edges.py","guard_source.py",
 "io.py","support.py","checkpoint.py","input_guard.py","supervision.py","trainer.py",
 "execution.py","runtime.py","protocol_p2.py","pilot.py","feature_views.py",
 "analysis_ea.py","recon/ep8_run.py",
 "analysis_eb.py","recon/ep9_run.py",
)

def runtime_refs():
    result=dict(_code_refs())
    for name in MODULES:
        path=ROOT/"scripts/edge_sem"/name
        result[str(path.relative_to(ROOT))]=ref(path)["sha256"]
    return result

def snapshot_runtime(folder):
    versions=runtime_refs();snapshots={}
    for name,sha in versions.items():
        if not name.startswith("scripts/edge_sem/"):continue
        dest=Path(folder)/(name.replace("/","__")+".txt")
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open("xb") as f:f.write((ROOT/name).read_bytes())
        snapshots[name]=ref(dest)
        if snapshots[name]["sha256"]!=sha:raise ValueError("Runtime changed during snapshot")
    return versions,snapshots

def verify_snapshot(plan,execute):
    if execute and plan["runtime"]!=runtime_refs():raise ValueError("Sealed runtime changed")
    expected={n:v for n,v in plan["runtime"].items() if n.startswith("scripts/edge_sem/")}
    if set(expected)!=set(plan["runtime_snapshots"]):raise ValueError("Missing EdgeSem runtime snapshot")
    for name,row in plan["runtime_snapshots"].items():
        checked(row)
        if row["sha256"]!=expected[name]:raise ValueError("Archived runtime source differs")
