"""Read-only original-view inputs and sealed layer evidence for NodeSem facts.

Historical plans identify immutable sources/graphs, not the new text policy.
No anonymous source, prediction, target file or feature array is loaded here.
"""
import hashlib
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.labeling_v2.safe_graph import read_graph

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json"
STORE = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json"


def load_context(task_id, plan_path=PLAN, store_path=STORE):
    plan_path, store_path = Path(plan_path), Path(store_path)
    if ref(plan_path) != read(plan_path.with_name("plan.seal.json"))["plan"]:
        raise ValueError("Historical input plan seal differs")
    if ref(store_path)["sha256"] != read(store_path.with_name("store.seal.json"))["store_sha256"]:
        raise ValueError("Graph store seal differs")
    plan, store = read(plan_path), read(store_path)
    task, stored = plan["tasks"][task_id], store["tasks"][task_id]
    graph_refs = {k: stored["graphs"][k]["graph"] for k in ("F0", "F3")}
    for key, profile in (("F0", "G0"), ("F3", "G3R")):
        if graph_refs[key]["sha256"] != task["profiles"][profile]["graph"]["sha256"]:
            raise ValueError("Plan/store graph identity differs")
    graphs = {k: read_graph(checked(v)) for k, v in graph_refs.items()}
    sources = task["record"]["sources"]
    source_text = {f: checked(r).read_text(encoding="utf8") for f, r in sources.items()}
    audit_ref = stored["graphs"]["F3"]["audit"]
    audit = read(checked(audit_ref))
    for f, src in source_text.items():
        if hashlib.sha256(src.encode("utf8")).hexdigest() != audit["source_hashes"][f]:
            raise ValueError("Source/evidence identity differs")
    for layer in ("L1", "L2", "L3"):
        if audit["layers"][layer].get("labels_used_for_analysis") is not False:
            raise ValueError("Layer evidence does not exclude targets")
    # Frozen text producer order is originals, then file/key-sorted auxiliaries.
    return dict(task_id=task_id, graphs=graphs, order=list(graphs["F0"]),
                sources=sources, source_text=source_text, audit=audit,
                provenance=dict(plan=ref(plan_path), store=ref(store_path),
                                audit=audit_ref, graphs=graph_refs),
                profiles={k: dict(graph_fingerprint=graph_fingerprint(g))
                          for k, g in graphs.items()})


def check_layer_edge(source, target, attrs, audit):
    relation = attrs.get("edge_type")
    layer = {"DATA_DEF_USE": "L1", "WRITES_STATE": "L2",
             "READS_STATE": "L2", "ENV_FLOW": "L3"}.get(relation)
    if layer is None:
        return []
    proof = audit["layers"][layer]["evidence"]
    field = "ddg_fact_indices" if layer == "L1" else "evidence_indices"
    indices = attrs.get(field)
    if not isinstance(indices, list) or not indices or len(set(indices)) != len(indices):
        raise ValueError("Invalid edge evidence index list")
    result = []
    for i in indices:
        if type(i) is not int or i < 0 or i >= len(proof):
            raise ValueError("Edge evidence index outside sealed array")
        ev = proof[i]
        if ev["source"] != source or ev["target"] != target:
            raise ValueError("Edge and evidence endpoints disagree")
        if layer == "L1":
            if ev.get("self_fact") is not False:
                raise ValueError("Self fact cannot justify edge")
        elif ev.get("status") != "projected":
            raise ValueError("Unprojected evidence on model edge")
        if layer == "L2" and ev["relation"] != relation:
            raise ValueError("State relation evidence differs")
        if layer == "L3" and ev["env_key"] != attrs.get("env_key"):
            raise ValueError("Environment evidence differs")
        result.append(ev)
    return result
