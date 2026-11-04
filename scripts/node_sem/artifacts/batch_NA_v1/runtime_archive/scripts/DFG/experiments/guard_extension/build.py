"""CPU-only immutable build from archived overall_cv manifests (no training)."""
import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from scripts.labeling_v2.safe_graph import read_graph, write_graph
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.control_dependency.pipeline import augment, VERSION

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SOURCE = ROOT / "scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1"
DEFAULT_OUTPUT = ROOT / "scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1/build"
TASKS = ("reentrancy_author_contract", "access_control_author_contract",
         "reentrancy_author_node", "access_control_author_node")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write_json(path, data):
    with Path(path).open("x", encoding="utf8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def raw_support(graph, refs):
    """File-based edge counts; model-side reflected schema audited separately."""
    files = {data["source_file"] for _, data in graph.nodes(data=True)}
    by_file = {}
    for source, target, data in graph.edges(data=True):
        sf, tf = graph.nodes[source]["source_file"], graph.nodes[target]["source_file"]
        if sf != tf:
            raise ValueError("Cross-file graph edge; frozen protocol violated")
        canonical = (graph.nodes[source]["node_type"], data["edge_type"], graph.nodes[target]["node_type"])
        by_file.setdefault(sf, Counter())[canonical] += 1
    schema = sorted({c for counts in by_file.values() for c in counts})
    result = {"representation": "raw frozen HCG endpoint direction; adapter registration separately verified",
              "canonical_relations": [list(c) for c in schema], "folds": []}
    for info in refs:
        split = info["split"]
        train, val = set(split["train_files"]), set(split["val_files"])
        if train & val or train | val != files or not train or not val:
            raise ValueError("Frozen split and source identity mismatch")
        rows = []
        for c in schema:
            rows.append({"canonical": list(c),
                "train_edges": sum(by_file.get(f, {}).get(c,0) for f in train),
                "val_edges": sum(by_file.get(f, {}).get(c,0) for f in val)})
        controls = [x for x in rows if x["canonical"][1] == "CONTROL_DEPENDENCE"]
        result["folds"].append({"fold": info["fold"], "train_files": len(train), "val_files": len(val),
            "relations": rows,
            "control_train_edges": sum(x["train_edges"] for x in controls),
            "control_val_edges": sum(x["val_edges"] for x in controls),
            "control_registered_without_train": [x["canonical"] for x in controls if not x["train_edges"]]})
    return result


def model_context(base, enhanced):
    """Two-layer reachability from the actual adapter's edge tensors, no weights."""
    from collections import OrderedDict
    import torch
    from .model import reflected_input, ADAPTER_VERSION
    def adjacency(graph):
        rows, indices, raw = {}, {}, OrderedDict()
        for node, data in graph.nodes(data=True):
            typ = data["node_type"]
            indices[node] = len(rows.setdefault(typ, []))
            rows[typ].append(node)
        for source, target, data in graph.edges(data=True):
            c = (graph.nodes[source]["node_type"], data["edge_type"], graph.nodes[target]["node_type"])
            a,b = raw.setdefault(c, ([],[]))
            a.append(indices[source]); b.append(indices[target])
        data = reflected_input(OrderedDict((c,(torch.tensor(a,dtype=torch.int64),torch.tensor(b,dtype=torch.int64)))
                                           for c,(a,b) in raw.items()))
        adj = {node:set() for node in graph}
        for c,(source,target) in data.items():
            for a,b in zip(source.tolist(),target.tolist()):
                adj[rows[c[0]][a]].add(rows[c[2]][b])
        return adj,set(data)
    before, schema0 = adjacency(base)
    after, schema1 = adjacency(enhanced)
    new_count, changed_sources, changed_targets = 0, set(), set()
    outside_two_hops = 0
    controls = {}
    for a,b,d in enhanced.edges(data=True):
        if d["edge_type"] == "CONTROL_DEPENDENCE":
            controls.setdefault(a,set()).add(b)
    for source in before:
        old = set(before[source])
        for intermediate in before[source]: old.update(before[intermediate])
        new = set(after[source])
        for intermediate in after[source]: new.update(after[intermediate])
        delta = new-old-{source}
        if delta:
            new_count += len(delta); changed_sources.add(source); changed_targets.update(delta)
        outside_two_hops += len(controls.get(source,set())-old)
    return {"adapter_version":ADAPTER_VERSION,"actual_adapter_tensors_used":True,
        "ordinary_relations_reflected":True,"all_enhancement_relations_forward_only":True,
        "new_two_layer_pairs":new_count,"new_context_source_nodes":len(changed_sources),
        "new_context_target_nodes":len(changed_targets),
        "new_control_edges_outside_baseline_two_hops":outside_two_hops,
        "new_model_canonical_relations":[list(c) for c in sorted(schema1-schema0)],
        "meaning":"message topology reachability, not proof of new semantics or accuracy"}


def build(output=DEFAULT_OUTPUT, source_batch=DEFAULT_SOURCE):
    output, source_batch = Path(output).resolve(), Path(source_batch).resolve()
    if output.exists():
        raise ValueError("Build output is immutable; use a new attempt directory")
    new_runtime = sorted((ROOT / "scripts/DFG/control_dependency").rglob("*.py")) + [Path(__file__).resolve(), Path(__file__).with_name("model.py"), Path(__file__).with_name("__init__.py")]
    runtime_before = {str(p): sha256(p) for p in new_runtime}
    frozen = {}
    def check(path, expected=None):
        path = Path(path).resolve()
        observed = sha256(path)
        if expected is not None and observed != expected:
            raise ValueError("Frozen input drift: " + str(path))
        frozen[str(path)] = observed
        return path
    seal = read_json(check(source_batch / "plan.seal.json"))
    plan_path = check(source_batch / "plan.json", seal["sha256"])
    plan = read_json(plan_path)
    if plan["protocol"] != "paper_kfold" or plan["score_role"] != "cv_validation":
        raise ValueError("Unexpected historical protocol")
    # Read-only archive validation: new sidecar files do not rewrite the old seal.
    for path, expected in plan["runtime"].items():
        check(path, expected)
    kplans = [Path(path) for path, h in plan["frozen"].items()
              if h == plan["source_stage_k_plan_sha256"] and Path(path).name == "plan.json"]
    if len(kplans) != 1:
        raise ValueError("Missing/ambiguous Stage K provenance")
    kpath = check(kplans[0], plan["source_stage_k_plan_sha256"])
    kplan = read_json(kpath)
    ksealpath = kpath.with_name("plan.seal.json")
    kseal = read_json(check(ksealpath, plan["frozen"][str(ksealpath)]))
    if kseal["sha256"] != sha256(kpath):
        raise ValueError("Stage K plan seal mismatch")
    manifest = {"version": VERSION, "source_plan_path": str(plan_path),
        "source_plan_sha256": sha256(plan_path), "source_stage_k_plan_sha256": sha256(kpath),
        "protocol": "paper_kfold", "score_role": "cv_validation", "tasks": [],
        "labels_used_for_analysis": False, "training_executed": False,
        "historical_recorded_runtime_hashes_verified": True}
    output.mkdir(parents=True)
    for task_id in TASKS:
        refs = sorted([x for x in plan["tasks"] if x["task_id"] == task_id], key=lambda x:x["fold"])
        count = 5 if task_id.endswith("contract") else 10
        if [x["fold"] for x in refs] != list(range(count)):
            raise ValueError("Historical task folds missing/duplicated")
        infos = [read_json(check(x["manifest"], x["sha256"])) for x in refs]
        info = infos[0]
        old = info["graphs"]["HCG_DDG"]
        if any(x["graphs"]["HCG_DDG"] != old for x in infos):
            raise ValueError("Historical per-fold graph drift")
        graph_path = check(old["path"], old["sha256"])
        # Hash check precedes restricted deserialization, never unrestricted pickle.load.
        graph = read_graph(graph_path)
        if fingerprint(graph) != old["fingerprint"]:
            raise ValueError("Historical graph fingerprint mismatch")
        prepared = read_json(check(info["source_prepared_manifest"], info["source_prepared_manifest_sha256"]))
        check(info["labels_path"], info["labels_sha256"])
        check(info["source_splits_path"], info["source_splits_sha256"])
        source_manifests = [Path(path) for path in kplan["frozen"]
            if Path(path).name == "sources.json" and Path(path).parent.name == task_id]
        if len(source_manifests) != 1:
            raise ValueError("Missing/ambiguous recorded source metadata manifest")
        source_manifest = check(source_manifests[0], kplan["frozen"][str(source_manifests[0])])
        records = read_json(source_manifest)["sources"]
        files = {d["source_file"] for _,d in graph.nodes(data=True)}
        sources, metadata = {}, {}
        for name in sorted(files):
            if name not in records or name not in prepared["sources"]:
                raise ValueError("Source manifest lacks frozen graph file: " + name)
            rec = records[name]
            if rec["sha256"] != prepared["sources"][name]["sha256"]:
                raise ValueError("Source provenance differs between frozen stages")
            sources[name] = check(rec["path"], rec["sha256"]).read_bytes().decode("utf8")
            metadata[name] = rec.get("metadata")
        print("BUILD", task_id, "files", len(files), "nodes", len(graph), flush=True)
        start = time.perf_counter()
        enhanced, audit = augment(graph, sources, metadata)
        audit["model_context"] = model_context(graph, enhanced)
        elapsed = time.perf_counter()-start
        folder = output / task_id
        folder.mkdir()
        target = folder / "HCG_DDG_GUARD.gpickle"
        write_graph(enhanced, target)
        # A second restricted read verifies the serialized output exactly.
        if fingerprint(read_graph(target)) != fingerprint(enhanced):
            raise ValueError("Control graph serialization mismatch")
        coverage = folder / "coverage.json"
        invariants = folder / "invariants.json"
        support = folder / "support.json"
        write_json(coverage, audit)
        write_json(invariants, audit["invariants"])
        write_json(support, raw_support(enhanced, infos))
        row = {"task_id": task_id, "task": info["task"], "cohort": info["cohort"],
            "graph": {"path": str(target), "sha256": sha256(target), "fingerprint": fingerprint(enhanced),
                      "nodes": len(enhanced), "edges": enhanced.number_of_edges()},
            "source_graph": old, "source_task_manifest": refs[0]["manifest"],
            "source_task_sha256": refs[0]["sha256"],
            "source_metadata_manifest": str(source_manifest), "source_metadata_sha256": sha256(source_manifest),
            "coverage_path": str(coverage), "coverage_sha256": sha256(coverage),
            "invariants_path": str(invariants), "invariants_sha256": sha256(invariants),
            "support_path": str(support), "support_sha256": sha256(support),
            "build_seconds": elapsed, "file_count": len(files),
            "summary": {"added_control_edges": audit["invariants"]["added_control_edges"],
                        "projected_facts": len(audit["evidence"]), "context": audit["context"],
                        "model_context": audit["model_context"],
                        "file_status_counts": audit["file_status_counts"],
                        "function_status_counts": audit["function_status_counts"]}}
        manifest["tasks"].append(row)
        print("BUILT", task_id, json.dumps(row["summary"], sort_keys=True), flush=True)
        del graph, enhanced, audit
    # Protect historical artifacts and source even across a long CPU build.
    for path, expected in frozen.items():
        if sha256(path) != expected:
            raise ValueError("Input mutated during build: " + path)
    manifest["frozen_inputs"] = frozen
    runtime_after = {str(p): sha256(p) for p in new_runtime}
    if runtime_after != runtime_before:
        raise ValueError("Analysis source changed during build; preserve failed attempt and rebuild")
    manifest["analysis_runtime"] = runtime_before
    write_json(output / "manifest.json", manifest)
    write_json(output / "manifest.seal.json", {"sha256": sha256(output / "manifest.json")})
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-batch", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    build(args.output, args.source_batch)

if __name__ == "__main__":
    main()
