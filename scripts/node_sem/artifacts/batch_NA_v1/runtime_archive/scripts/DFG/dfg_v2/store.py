"""Immutable graph-store orchestration; reuses frozen analyzers and HGT adapter.

The default four-task build constructs 20 CPU models for schema/parameter
inspection only. No forward, loss, optimizer or training is performed here.
F0 is always a byte-identical reference to the original input graph.
"""
import copy
import csv
import gc
import json
import resource
import time
from collections import Counter
from pathlib import Path

import networkx as nx

from sco_models import graph_utils as gu
from scripts.DFG.experiments.common import digest
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from scripts.DFG.integration.pipeline import computation_fingerprint
from scripts.labeling_v2.safe_graph import read_graph, write_graph
from . import ENV_SOURCE, FORWARD_RELATIONS, REVERSE_OF, forward_relations, has_reverse
from .inputs import load_manifest, load_task
from .l1_build import _runtime
from .model import make_model, validate_registration
from .model_input import build_dgl
from .pipeline import (GRAPH_RELATIONS, iter_build, key_for_profile,
                       layers_for_key, profiles_for_key)
from .tokens import TokenEncoder

STORE_VERSION = "dfg-v2-graph-store-v1"
DEFAULT_GRAPH_KEYS = ("F1", "F2", "F3")


def _selection(value, allowed, default, name):
    values = default if value is None else value
    if isinstance(values, str):
        values = values.split(",")
    values = list(values)
    if (not values or any(not isinstance(v, str) or not v or v not in allowed for v in values)
            or len(set(values)) != len(values)):
        raise ValueError("Invalid or duplicate " + name)
    return values


def _ref(path, graph):
    return dict(path=str(Path(path).resolve()), sha256=sha256(path),
                fingerprint=fingerprint(graph),
                computation_fingerprint=computation_fingerprint(graph),
                nodes=len(graph), edges=graph.number_of_edges())


def _directions(profile):
    return {name: has_reverse(profile, name) for name in sorted(forward_relations(profile))}


def _model_record(graph, task, profile):
    # make_model allocates/copies its own working graph. Never call forward.
    model = make_model(task, graph, profile, device="cpu")
    schema = validate_registration(model)
    canonical = [dict(canonical=list(c), edges=model.symmetrical_global_graph.num_edges(c))
                 for c in model.symmetrical_global_graph.canonical_etypes]
    record = dict(profile=profile, graph_key=key_for_profile(profile), device="cpu",
        node_feature=model.node_feature, input_width=model.in_size,
        hidden_size=model.hidden_size, layers=model.num_layers, heads=model.num_heads,
        reducer=model.dfg_reducer, schema=schema, canonical=canonical,
        parameter_count=sum(p.numel() for p in model.parameters()),
        forward_relations=sorted(forward_relations(profile)),
        reverse_relations=_directions(profile), model_forward_executed=False,
        training_executed=False, optimizer_steps=0)
    del model
    gc.collect()
    return record


def _schema_only(graph, profile):
    """Validate the stored schema from graph endpoints without allocating HGT."""
    private = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(graph)))
    dgl_graph, _ = build_dgl(private, profile, device="cpu")
    schema = dict(node_types=[dict(name=t, index=i) for i, t in enumerate(dgl_graph.ntypes)],
                  canonical_relations=[dict(canonical=list(c), index=i)
                                       for i, c in enumerate(dgl_graph.canonical_etypes)])
    schema["sha256"] = digest(schema)
    canonical = [dict(canonical=list(c), edges=dgl_graph.num_edges(c))
                 for c in dgl_graph.canonical_etypes]
    return schema, canonical


def _summary_row(task_id, key, graph, audit, models, baseline_canonical, elapsed):
    counts = Counter(d["edge_type"] for _, _, d in graph.edges(data=True))
    layer_audits = audit.get("layers", {})
    functions = [f for rec in layer_audits.get("L1", {}).get("files", {}).values()
                 for f in rec.get("analysis", {}).get("functions", [])]
    declarations = [d for rec in layer_audits.get("L2", {}).get("files", {}).values()
                    for d in rec.get("declarations", [])]
    supported = sum(f["status"] == "supported" for f in functions)
    anchored = sum(d["status"] == "matched" for d in declarations)
    new_canonical = {
        p: len({tuple(c["canonical"]) for c in m["canonical"]} - baseline_canonical)
        for p, m in models.items()}
    return dict(task_id=task_id, graph_key=key, profiles=",".join(models),
        nodes=len(graph), edges=graph.number_of_edges(),
        DATA_DEF_USE=counts["DATA_DEF_USE"], WRITES_STATE=counts["WRITES_STATE"],
        READS_STATE=counts["READS_STATE"], ENV_FLOW=counts["ENV_FLOW"],
        env_nodes=sum(d["node_type"] == ENV_SOURCE for _, d in graph.nodes(data=True)),
        new_canonical=max(new_canonical.values()) if new_canonical else 0,
        new_canonical_by_profile=json.dumps(new_canonical, sort_keys=True),
        L1_functions=len(functions), L1_supported=supported,
        L1_support_fraction=supported/len(functions) if functions else None,
        state_declarations=len(declarations), anchored_state_declarations=anchored,
        state_anchor_fraction=anchored/len(declarations) if declarations else None,
        cumulative_seconds=elapsed)


def build_store(manifest, tasks=None, graph_keys=DEFAULT_GRAPH_KEYS, output=None,
                max_iterations=100000):
    """Build requested graph keys plus F0; compute but do not save prerequisites.

    Source files are loaded once per task and layers are invoked once each.
    Existing analyzers still perform their own internal parsing.
    """
    if output is None:
        raise ValueError("An explicit new output directory is required")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing graph-store directory: " + str(output))
    manifest = Path(manifest).resolve()
    document = load_manifest(manifest, check_files=True)
    chosen = _selection(tasks, document["tasks"], document["tasks"], "tasks")
    requested = _selection(graph_keys, GRAPH_RELATIONS, DEFAULT_GRAPH_KEYS, "graph keys")
    maximum = max(requested, key=lambda k: len(layers_for_key(k)))
    selected_keys = set(requested) | {"F0"}
    input_ref = dict(path=str(manifest), sha256=sha256(manifest),
        seal_path=str(manifest.with_name("manifest.seal.json")),
        seal_sha256=sha256(manifest.with_name("manifest.seal.json")))
    runtime = _runtime()
    output.mkdir(parents=True)
    store = dict(version=STORE_VERSION, status="accepted", input_manifest=input_ref,
        requested_tasks=chosen, requested_graph_keys=requested,
        saved_graph_keys=[k for k in GRAPH_RELATIONS if k in selected_keys],
        runtime=runtime, runtime_start_end_equal=False, tasks={},
        training_executed=False, model_forward_executed=False, optimizer_steps=0,
        source_loading_policy="once per task; existing layers retain their internal parsing")
    summary_rows = []
    construct_count = 0
    for task_id in chosen:
        started = time.monotonic()
        record = document["tasks"][task_id]
        original, sources, metadata = load_task(record)
        original_path = checked(record["original_graph"]["path"], record["original_graph"]["sha256"])
        original_sha = sha256(original_path)
        original_fp = fingerprint(original)
        for field, actual in (("fingerprint", original_fp),
                              ("computation_fingerprint", computation_fingerprint(original))):
            if field in record["original_graph"] and record["original_graph"][field] != actual:
                raise ValueError("Original graph fingerprint mismatch: " + task_id)
        encoder = TokenEncoder(record["feature"]) if "L3" in layers_for_key(maximum) else None
        task_output = output / task_id
        task_output.mkdir()
        task_record = dict(task_id=task_id, category=record["category"], task=record["task"],
            input_task_digest=digest(record), graphs={}, source_load_calls=1,
            pipeline_iteration_calls=1, model_forward_executed=False,
            training_executed=False, sources_loaded=len(sources),
            missing_sources=list(record.get("missing_sources", [])))
        baseline_canonical = set()
        visited = []
        for key, graph, audit in iter_build(original, sources, metadata,
                layers_for_key(maximum), token_encoder=encoder, max_iterations=max_iterations):
            visited.append(key)
            if key not in selected_keys:
                continue
            print(task_id + " " + key + ": graph/schema only", flush=True)
            directory = task_output / key
            directory.mkdir()
            if key == "F0":
                path = original_path
            else:
                path = directory / "hcg.gpickle"
                write_graph(graph, path)
                reloaded = read_graph(path)
                if (fingerprint(reloaded) != fingerprint(graph)
                        or computation_fingerprint(reloaded) != computation_fingerprint(graph)):
                    raise AssertionError("Graph serialization changed content")
                del reloaded
            graph_ref = _ref(path, graph)
            audit_path = directory / "audit.json"
            write_json(audit_path, audit)
            models = {}
            for profile in profiles_for_key(key):
                models[profile] = _model_record(graph, record["task"], profile)
                construct_count += 1
            if key == "F0":
                baseline_canonical = {tuple(c["canonical"]) for m in models.values()
                                      for c in m["canonical"]}
            task_record["graphs"][key] = dict(graph=graph_ref,
                audit=dict(path=str(audit_path), sha256=sha256(audit_path)),
                forward_relations=sorted(GRAPH_RELATIONS[key]), profiles=models)
            summary_rows.append(_summary_row(task_id, key, graph, audit, models,
                baseline_canonical, time.monotonic()-started))
            if fingerprint(original) != original_fp:
                raise AssertionError("Original graph mutated by pipeline or model inspection")
        if visited != ["F" + str(i) for i in range(len(layers_for_key(maximum))+1)]:
            raise AssertionError("Pipeline layer order/coverage differs")
        if set(task_record["graphs"]) != selected_keys:
            raise AssertionError("Requested graph keys not all produced")
        checked(original_path, original_sha)
        if encoder is not None:
            encoder.verify_assets()
        task_record["seconds"] = time.monotonic()-started
        task_record["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0
        task_record["rss_scope"] = "process_lifetime_high_water_at_task_end; not independent task peak"
        store["tasks"][task_id] = task_record
        del original, graph, sources, metadata, encoder
        gc.collect()
    # Recheck all input assets and references, without loading/analysing sources again.
    checked(manifest, input_ref["sha256"])
    checked(input_ref["seal_path"], input_ref["seal_sha256"])
    if load_manifest(manifest, check_files=True) != document:
        raise AssertionError("Input manifest changed during build")
    if _runtime() != runtime:
        raise AssertionError("Runtime source files changed during build")
    store["runtime_start_end_equal"] = True
    store["model_constructions"] = construct_count
    store["graph_keys_produced"] = sum(len(t["graphs"]) for t in store["tasks"].values())
    summary_path = output / "build_summary.csv"
    with summary_path.open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    store["build_summary"] = dict(path=str(summary_path), sha256=sha256(summary_path))
    store_path = output / "store.json"
    write_json(store_path, store)
    write_json(output / "store.seal.json", dict(version=STORE_VERSION,
        status="accepted", store_sha256=sha256(store_path),
        input_manifest_sha256=input_ref["sha256"],
        input_manifest_seal_sha256=input_ref["seal_sha256"],
        model_constructions=construct_count, model_forward_executed=False,
        training_executed=False, optimizer_steps=0))
    verify_store(store_path)
    return store


def verify_store(path):
    """Read-only artifact validation; current source runtime may legitimately differ.

    Rebuild only DGL schema/endpoints through the existing adapter. No HGT model
    construction, forward, source analysis or tokenizer invocation is required.
    """
    path = Path(path).resolve()
    seal = read_json(path.with_name("store.seal.json"))
    if seal.get("version") != STORE_VERSION or seal.get("status") != "accepted":
        raise ValueError("Invalid graph-store seal")
    checked(path, seal.get("store_sha256"))
    store = read_json(path)
    if (store.get("version") != STORE_VERSION or store.get("status") != "accepted"
            or store.get("runtime_start_end_equal") is not True
            or store.get("training_executed") is not False
            or store.get("model_forward_executed") is not False
            or store.get("optimizer_steps") != 0):
        raise ValueError("Invalid graph-store record")
    inputs = store["input_manifest"]
    checked(inputs["path"], inputs["sha256"])
    checked(inputs["seal_path"], inputs["seal_sha256"])
    if (inputs["sha256"] != seal["input_manifest_sha256"]
            or inputs["seal_sha256"] != seal["input_manifest_seal_sha256"]):
        raise ValueError("Graph-store input binding mismatch")
    manifest = load_manifest(inputs["path"], check_files=True)
    selected = _selection(store["requested_tasks"], manifest["tasks"], (), "stored tasks")
    if set(selected) != set(store["tasks"]):
        raise ValueError("Graph-store task set differs")
    requested = _selection(store["requested_graph_keys"], GRAPH_RELATIONS, (), "stored graph keys")
    saved = set(requested) | {"F0"}
    if store["saved_graph_keys"] != [k for k in GRAPH_RELATIONS if k in saved]:
        raise ValueError("Graph-store saved key set differs")
    checked(store["build_summary"]["path"], store["build_summary"]["sha256"])
    constructions = 0
    for task_id, task in store["tasks"].items():
        source = manifest["tasks"][task_id]
        if (task["input_task_digest"] != digest(source) or task["task_id"] != task_id
                or task["category"] != source["category"] or task["task"] != source["task"]
                or set(task["graphs"]) != saved):
            raise ValueError("Graph-store task/input binding differs")
        original_ref = source["original_graph"]
        original_fp = None
        for key in sorted(task["graphs"]):
            entry = task["graphs"][key]
            ref = entry["graph"]
            gp = checked(ref["path"], ref["sha256"])
            if key == "F0" and (gp != Path(original_ref["path"]).resolve()
                               or ref["sha256"] != original_ref["sha256"]):
                raise ValueError("F0 must reference exact original graph file")
            graph = read_graph(gp)
            full, computation = fingerprint(graph), computation_fingerprint(graph)
            if (full != ref["fingerprint"] or computation != ref["computation_fingerprint"]
                    or len(graph) != ref["nodes"] or graph.number_of_edges() != ref["edges"]):
                raise ValueError("Graph-store graph fingerprint/count differs")
            if key == "F0":
                original_fp = full
            audit = read_json(checked(entry["audit"]["path"], entry["audit"]["sha256"]))
            if (audit.get("input_fingerprint") != original_fp
                    or audit.get("output_fingerprint") != full
                    or audit.get("computation_fingerprint") != computation
                    or audit.get("labels_used_for_analysis") is not False
                    or set(audit.get("layers", {})) != set(layers_for_key(key))):
                raise ValueError("Graph-store audit/graph binding differs")
            if entry["forward_relations"] != sorted(GRAPH_RELATIONS[key]):
                raise ValueError("Graph-store forward relation set differs")
            if set(entry["profiles"]) != set(profiles_for_key(key)):
                raise ValueError("Graph-store profile set differs")
            for profile, model in entry["profiles"].items():
                schema, canonical = _schema_only(graph, profile)
                if (model["profile"] != profile or model["graph_key"] != key
                        or key_for_profile(profile) != key
                        or model["schema"] != schema or model["canonical"] != canonical
                        or model["forward_relations"] != sorted(forward_relations(profile))
                        or model["reverse_relations"] != _directions(profile)
                        or model["model_forward_executed"] is not False
                        or model["training_executed"] is not False
                        or model["optimizer_steps"] != 0 or model["device"] != "cpu"
                        or model["parameter_count"] <= 0):
                    raise ValueError("Graph-store schema/profile binding differs")
                constructions += 1
            del graph
    if (constructions != store["model_constructions"] or constructions != seal["model_constructions"]
            or seal["model_forward_executed"] is not False or seal["training_executed"] is not False
            or seal["optimizer_steps"] != 0
            or sum(len(t["graphs"]) for t in store["tasks"].values()) != store["graph_keys_produced"]):
        raise ValueError("Graph-store acceptance counts differ")
    return dict(status="accepted", version=STORE_VERSION, tasks=len(store["tasks"]),
        graphs=store["graph_keys_produced"], recorded_model_constructions=constructions,
        verification_model_constructions=0, model_forward_executed=False,
        training_executed=False, current_runtime_required_to_match=False,
        store_sha256=sha256(path))
