"""EP7 immutable baseline, runtime provenance and append-only records."""
import subprocess
from pathlib import Path
from .common import ROOT, PLAN, ref, read, write, checked

OUT = ROOT / "scripts/edge_sem/artifacts/ep7_v1"
TASKS = ("reentrancy_node", "access_control_node")
DOCS = ("HANDOVER.md", "docs/training_changes_2026-10-07.md", "scripts/edge_sem/PROGRESS.md")


def prepare():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    OUT.mkdir(parents=True, exist_ok=False)
    load(PLAN)
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=str(ROOT), text=True).split("\0")
    frozen = [ref(ROOT / p) for p in tracked if p and (ROOT / p).is_file()
        and p.endswith(".py") and "/artifacts/" not in p
        and (p.startswith(("scripts/DFG/", "scripts/node_sem/", "sco_models/", "process_graphs/", "experiments/"))
             or p in ("node_classifier.py", "graph_classifier.py", "infer_smart_contract.py"))]
    prior = [ref(p) for p in sorted(OUT.parent.rglob("*")) if p.is_file() and OUT not in p.parents]
    snapshots = []
    for name in tracked:
        if not name.startswith("scripts/edge_sem/") or not name.endswith(".py") or "/artifacts/" in name:
            continue
        source = ROOT / name
        dest = OUT / "baseline" / (name.replace("/", "__") + ".txt")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            stream.write(source.read_bytes())
        snapshots.append(dict(original=ref(source), snapshot=ref(dest)))
    write(OUT / "before.json", dict(
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip(),
        prompt=ref(ROOT / "scripts/edge_sem/PROMPTS.md"), plan=ref(PLAN),
        frozen_code=frozen, dfg_code_refs=_code_refs(), prior_artifacts=prior,
        edge_sources=snapshots, documents={name: ref(ROOT / name) for name in DOCS},
        synchronization="Windows Git fetch through existing proxy, then WSL Git merge --ff-only origin/edge-sem; already up to date",
        gpu_executed=False, formal_training_authorized=False))
    print("EP7 baseline preserved", len(frozen), len(prior), flush=True)


if __name__ == "__main__":
    prepare()
