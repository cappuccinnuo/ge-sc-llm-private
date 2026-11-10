"""EP0b provenance, immutable-input access and append-only run outputs."""
import subprocess
from collections import defaultdict
from .common import ROOT, ref, read, checked, write, key

OUT = ROOT / "scripts/edge_sem/artifacts/ep0b_v1"
EP0 = ROOT / "scripts/edge_sem/artifacts/ep0_v1"
TASKS = ("reentrancy_node", "access_control_node",
         "reentrancy_contract", "access_control_contract")


def prepare():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    OUT.mkdir(parents=True, exist_ok=False)
    plan = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json"
    load(plan)
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=str(ROOT), text=True).split("\0")
    frozen = [ref(ROOT / p) for p in files if p.endswith(".py") and
              (p.startswith(("scripts/DFG/", "scripts/node_sem/", "sco_models/",
                             "process_graphs/", "experiments/"))
               or p in ("node_classifier.py", "graph_classifier.py", "infer_smart_contract.py"))
              and "/artifacts/" not in p]
    prior = [ref(p) for p in sorted(EP0.rglob("*")) if p.is_file()]
    docs = {name: ref(ROOT/name) for name in ("HANDOVER.md",
        "docs/training_changes_2026-10-07.md", "scripts/edge_sem/PROGRESS.md",
        "scripts/edge_sem/RECON.md")}
    write(OUT/"before.json", dict(
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip(),
        prompt=ref(ROOT/"scripts/edge_sem/PROMPTS.md"), plan=ref(plan),
        seal=ref(plan.with_name("plan.seal.json")), input_inventory=ref(EP0/"inputs.json"),
        frozen_code=frozen, dfg_code_refs=_code_refs(), prior_artifacts=prior, documents=docs))
    print("EP0b prepared; no graphs, parameters or training artifacts written", flush=True)


def contexts(task):
    from scripts.node_sem.facts_io import load_context
    ctx = load_context(task)
    recorded = read(EP0/"inputs.json")["tasks"][task]
    for name, row in recorded["graph_refs"].items():
        checked(row)
        assert ctx["provenance"]["graphs"][name]["sha256"] == row["sha256"]
    for row in recorded["sources"].values():
        checked(row)
    return ctx


def file_views(context):
    from scripts.node_sem.facts import _raw_projection
    from scripts.node_sem.facts_ast import AstSemantics
    from scripts.DFG.dfg_v2.projection_view import ProjectionView
    from scripts.DFG.projection import Projector
    graph = context["graphs"]["F3"]
    groups = defaultdict(list)
    for nid, attrs in graph.nodes(data=True):
        if attrs["node_type"] != "env_source":
            groups[attrs["source_file"]].append(nid)
    for file, source in sorted(context["source_text"].items()):
        sub = graph.subgraph(groups[file])
        view = ProjectionView(source, file)
        sem = AstSemantics(view)
        raw = _raw_projection(view, Projector(sub, view))
        inverse = {key(node): nid for nid, node in raw.items()}
        yield file, source, sub, sem, raw, inverse


def anchor(node):
    return None if node is None else list(key(node))


if __name__ == "__main__":
    prepare()
