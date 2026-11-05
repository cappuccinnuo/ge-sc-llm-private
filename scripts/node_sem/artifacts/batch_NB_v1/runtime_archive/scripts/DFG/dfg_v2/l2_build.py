"""Prompt 3: verify frozen L1 inputs and build L2 author-graph bundles.

This is CPU model construction/schema acceptance only: no forward, optimizer,
training, label reconstruction, L1 reanalysis or source compilation.
"""
import argparse
import copy
import csv
import gc
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import checked, read_json, read_sources, sha256, write_json
from scripts.DFG.integration.pipeline import computation_fingerprint
from scripts.labeling_v2.safe_graph import read_graph, write_graph

from . import DATA_DEF_USE, READS_STATE, REVERSE_OF, VERSION, WRITES_STATE
from .l1_build import ARTIFACTS, _function_records, _runtime, _unique_tasks
from .model import make_model, validate_registration

DEFAULT_L1 = ARTIFACTS / "l1_build/final_route_audit"
DEFAULT_OUTPUT = ARTIFACTS / "l2_build"
L2_RELATIONS = {WRITES_STATE, READS_STATE}


def verify_l1(directory):
    """Read-only archive verification; old runtime identity is not rewritten."""
    directory = Path(directory).resolve()
    receipt_path = directory / "receipt.json"
    receipt = read_json(receipt_path)
    if (receipt.get("status") != "accepted" or receipt.get("optimizer_steps") != 0
            or receipt.get("training_executed") is not False):
        raise ValueError("L1 receipt is not an accepted nontraining build")
    summary_path = checked(directory / "summary.json", receipt["summary_sha256"])
    summary = read_json(summary_path)
    if (summary.get("profile") != "G1R" or not summary.get("all_acceptance_passed")
            or summary.get("training_executed") is not False):
        raise ValueError("L1 summary is not the accepted G1R input")
    tasks = _unique_tasks(summary, "L1 summary")
    if set(tasks) != set(receipt["task_manifests"]):
        raise ValueError("L1 receipt/summary task matrix differs")
    run_inputs = read_json(directory / "run_inputs.json")
    if not (summary["runtime"] == receipt["runtime"] == run_inputs["runtime"]):
        raise ValueError("Historical L1 runtime records disagree")
    manifest = checked(run_inputs["manifest"], receipt["manifest_sha256"])
    if run_inputs["manifest_sha256"] != receipt["manifest_sha256"]:
        raise ValueError("L1 input-manifest binding differs")
    checked(manifest, read_json(manifest.with_name("manifest.seal.json"))["sha256"])
    if (run_inputs["prompt0_baseline_sha256"] != receipt["prompt0_baseline_sha256"]):
        raise ValueError("L1 Prompt 0 binding differs")
    checked(run_inputs["prompt0_baseline"], receipt["prompt0_baseline_sha256"])
    input_tasks = _unique_tasks(read_json(manifest), "Frozen source manifest")
    if set(tasks) != set(input_tasks):
        raise ValueError("Frozen input task matrix differs from L1")
    verified = {}
    for tid, record in tasks.items():
        bundle_path = checked(directory / tid / "manifest.json",
                              receipt["task_manifests"][tid])
        bundle = read_json(bundle_path)
        if bundle != record["bundle"]:
            raise ValueError("L1 task manifest differs from summary: " + tid)
        if (bundle.get("layer") != "L1" or bundle.get("profile") != "G1R"
                or bundle.get("training_executed") is not False):
            raise ValueError("Unexpected L1 bundle profile")
        for name in ("audit", "inputs", "acceptance", "model_schema"):
            checked(bundle_path.parent / (name + ".json"), bundle["files"][name])
        checked(bundle["graph"]["path"], bundle["graph"]["sha256"])
        inputs = read_json(bundle_path.parent / "inputs.json")
        ref = input_tasks[tid]
        if (inputs["task_manifest_sha256"] != ref["source_task_sha256"]
                or inputs["source_manifest_sha256"] != ref["source_metadata_sha256"]
                or Path(inputs["task_manifest"]).resolve() !=
                   Path(ref["source_task_manifest"]).resolve()
                or Path(inputs["source_manifest"]).resolve() !=
                   Path(ref["source_metadata_manifest"]).resolve()):
            raise ValueError("L1 task/source binding differs from frozen manifest")
        verified[tid] = dict(summary=record, bundle=bundle, directory=bundle_path.parent,
                             inputs=inputs, input_ref=ref)
    return verified, dict(directory=str(directory), receipt_sha256=sha256(receipt_path),
        summary_sha256=sha256(summary_path), run_inputs_sha256=sha256(directory/"run_inputs.json"),
        task_manifests=receipt["task_manifests"], runtime=receipt["runtime"])


def load_sources(record, graph):
    inputs = record["inputs"]
    task_path = checked(inputs["task_manifest"], inputs["task_manifest_sha256"])
    source_path = checked(inputs["source_manifest"], inputs["source_manifest_sha256"])
    original = inputs["original_graph"]
    checked(original["path"], original["sha256"])
    if read_json(task_path)["graphs"]["HCG"] != original:
        raise ValueError("Original HCG identity differs from frozen task")
    sources, metadata, used, missing = read_sources(source_path, graph)
    if missing or inputs["missing_sources"]:
        raise ValueError("Acceptance requires every frozen source")
    if used != inputs["sources"]:
        raise ValueError("L1 source identities/metadata differ from current manifest")
    return sources, metadata, used


def assert_l2_only(base, enhanced):
    """Fingerprint comparison includes all L1 edge attributes and edge keys."""
    if any(attrs.get("edge_type") in L2_RELATIONS
           for _, _, attrs in base.edges(data=True)):
        raise ValueError("L1 input already contains L2 relations")
    restored = copy.deepcopy(enhanced)
    seen = set()
    for source, target, key, attrs in list(restored.edges(keys=True, data=True)):
        if attrs.get("edge_type") in L2_RELATIONS:
            identity = (source, target, attrs["edge_type"])
            if source == target or identity in seen:
                raise AssertionError("L2 duplicate/self edge")
            seen.add(identity)
            restored.remove_edge(source, target, key)
    if fingerprint(restored) != fingerprint(base):
        raise AssertionError("Original graph or L1 nodes/edges/attributes changed")
    return dict(base_nodes_exact=True, base_edges_exact=True,
        L1_DATA_DEF_USE_attributes_exact=True, base_nodes=len(base),
        base_edges=base.number_of_edges(), output_edges=enhanced.number_of_edges(),
        added_by_relation=dict(Counter(edge[2] for edge in seen)))


def coverage_summary(graph, audit, l1_audit):
    """Metrics are identity-based, never dependent on labels or predictions."""
    l1_functions = _function_records(l1_audit)
    fallback = {identity for identity, rec in l1_functions.items()
                if rec["status"] != "supported"}
    projected = [ev for ev in audit["evidence"] if ev["status"] == "projected"]
    evidence_edges = {(e["source"], e["target"], e["relation"]) for e in projected}
    graph_edges = {(s, t, d["edge_type"]) for s, t, d in graph.edges(data=True)
                   if d["edge_type"] in L2_RELATIONS}
    if evidence_edges != graph_edges:
        raise AssertionError("L2 projected evidence and graph edge identities differ")
    fallback_edges = {(e["source"], e["target"], e["relation"]) for e in projected
                      if e.get("callable") in fallback}
    fallback_with_edges = {e["callable"] for e in projected if e.get("callable") in fallback}
    declarations = [d for f in audit["files"].values() for d in f["declarations"]]
    matched = [d for d in declarations if d["status"] == "matched"]
    locations = {}
    for d in matched:
        identity = d["node_id"]
        location = {k: d.get(k) for k in ("file", "name", "start", "end", "line", "node_id")}
        if identity in locations and locations[identity] != location:
            raise AssertionError("State declaration HCG identity is ambiguous")
        locations[identity] = location
    readers, writers = defaultdict(set), defaultdict(set)
    for ev in projected:
        if not ev.get("callable") or ev.get("callable_kind") == "state_variable_declaration":
            continue
        if ev["relation"] == WRITES_STATE:
            writers[ev["target"]].add((ev["source"], ev["callable"]))
        elif ev["relation"] == READS_STATE:
            readers[ev["source"]].add((ev["target"], ev["callable"]))
    cross_pairs = {}
    for declaration in set(writers) | set(readers):
        pairs = {(w, r) for w, wc in writers[declaration]
                 for r, rc in readers[declaration] if wc != rc}
        if pairs:
            cross_pairs[declaration] = len(pairs)
    reads = Counter(s for s, _, relation in graph_edges if relation == READS_STATE)
    writes = Counter(t for _, t, relation in graph_edges if relation == WRITES_STATE)
    def top(counter):
        return [dict(locations.get(node, {"node_id": node}), degree=count)
                for node, count in sorted(counter.items(), key=lambda pair: (-pair[1], str(pair[0])))[:10]]
    alias_edges = {(e["source"], e["target"], e["relation"]) for e in projected
                   if e.get("via_alias")}
    aliases_by_relation = Counter(edge[2] for edge in alias_edges)
    relation_counts = Counter(edge[2] for edge in graph_edges)
    unresolved, alias_unresolved, access_unresolved, excluded = (Counter() for _ in range(4))
    for file_record in audit["files"].values():
        unresolved.update(file_record["unresolved_reasons"])
        alias_unresolved.update(file_record.get("alias_unresolved_reasons", {}))
        access_unresolved.update(file_record.get("access_unresolved_reasons", {}))
        excluded.update(d["reason"] for d in file_record.get("diagnostics", [])
                        if d.get("kind") == "state_binding_excluded")
    return dict(
        state_declarations=len(declarations), anchored_state_declarations=len(matched),
        anchor_fraction=len(matched)/len(declarations) if declarations else None,
        declaration_statuses=dict(Counter(d["status"] for d in declarations)),
        L1_functions_total=len(l1_functions), L1_fallback_functions=len(fallback),
        L1_fallback_functions_with_L2=len(fallback_with_edges),
        L1_fallback_with_L2=sorted(fallback_with_edges), L1_fallback_L2_edges=len(fallback_edges),
        L1_fallback_L2_edges_by_relation=dict(Counter(edge[2] for edge in fallback_edges)),
        L2_callables=sum(f.get("callable_count", len(f["callables"])) for f in audit["files"].values()),
        L2_state_initializers=sum(rec.get("kind") == "state_variable_declaration"
            for f in audit["files"].values() for rec in f["callables"].values()),
        L2_units=sum(f["units"] for f in audit["files"].values()),
        L2_occurrences=dict(sum((Counter(f["occurrences"]) for f in audit["files"].values()), Counter())),
        L2_edges=dict(relation_counts), alias_edges=len(alias_edges),
        alias_edge_fraction=len(alias_edges)/len(graph_edges) if graph_edges else 0.0,
        alias_edges_by_relation=dict(aliases_by_relation),
        cross_callable_pairs=sum(cross_pairs.values()),
        cross_callable_pairs_by_declaration=[dict(locations.get(node, {"node_id":node}), pairs=count)
            for node,count in sorted(cross_pairs.items(), key=lambda pair: str(pair[0]))],
        top10_READS_STATE_outdegree=top(reads), top10_WRITES_STATE_indegree=top(writes),
        unresolved_reasons=dict(unresolved), binding_unresolved_occurrences=sum(unresolved.values()),
        alias_unresolved_reasons=dict(alias_unresolved),
        alias_unresolved_occurrences=sum(alias_unresolved.values()),
        access_unresolved_reasons=dict(access_unresolved),
        access_unresolved_occurrences=sum(access_unresolved.values()),
        binding_excluded_reasons=dict(excluded), binding_excluded_occurrences=sum(excluded.values()),
        alias_bindings=sum(f.get("alias_bindings", 0) for f in audit["files"].values()),
        unmapped=sum(f["unmapped"] for f in audit["files"].values()),
        anchor_missing=sum(f["anchor_missing"] for f in audit["files"].values()),
        evidence_statuses=dict(Counter(e["status"] for e in audit["evidence"])))


def sample_edges(graph, audit, count=20, seed=0):
    edges = sorted(((s, t, d) for s, t, d in graph.edges(data=True)
                    if d["edge_type"] in L2_RELATIONS),
                   key=lambda item: (item[2]["edge_type"], str(item[0]), str(item[1])))
    selected = random.Random(seed).sample(edges, min(count, len(edges)))
    records = []
    for source, target, attrs in selected:
        src, dst = graph.nodes[source], graph.nodes[target]
        records.append(dict(source=source, target=target, relation=attrs["edge_type"],
            source_file=src["source_file"], target_file=dst["source_file"],
            source_code=src.get("code"), target_code=dst.get("code"),
            source_lines=src.get("node_source_code_lines"),
            target_lines=dst.get("node_source_code_lines"),
            state_vars=attrs["state_vars"], via_alias=attrs["via_alias"],
            evidence_indices=attrs["evidence_indices"]))
    return dict(seed=seed, unit="unique projected L2 edge per task", requested=count, edges=records)


def model_schema(graph, task):
    model = make_model(task, graph, "G2R", device="cpu")
    schema = validate_registration(model)
    names = L2_RELATIONS | {REVERSE_OF[name] for name in L2_RELATIONS}
    canonical = [dict(canonical=list(key), edges=model.symmetrical_global_graph.num_edges(key))
                 for key in sorted(model.etypes_dict) if key[1] in names]
    record = dict(profile="G2R", adapter="scripts.DFG.dfg_v2.model.make_model",
        device="cpu", input_width=model.in_size, node_feature=model.node_feature,
        schema=schema, L2_canonical=canonical,
        relation_edges=dict(Counter({name:sum(row["edges"] for row in canonical
                                             if row["canonical"][1] == name) for name in sorted(names)})),
        parameter_count=sum(p.numel() for p in model.parameters()),
        model_forward_executed=False, optimizer_steps=0, training_executed=False)
    for name in L2_RELATIONS:
        if record["relation_edges"][name] != record["relation_edges"][REVERSE_OF[name]]:
            raise AssertionError("L2 explicit reverse count differs")
    del model
    gc.collect()
    return record


def write_bundle(output, graph, audit, inputs, acceptance, model, sample):
    output = Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    output.mkdir()
    graph_path = output / "hcg.gpickle"
    write_graph(graph, graph_path)
    if fingerprint(read_graph(graph_path)) != fingerprint(graph):
        raise AssertionError("L2 graph serialization roundtrip differs")
    documents = dict(audit=audit, inputs=inputs, acceptance=acceptance,
                     model_schema=model, edge_sample=sample)
    for name, document in documents.items():
        write_json(output/(name+".json"), document)
    result = dict(version=VERSION, layer="L2", profile="G2R",
        adapter="scripts.DFG.dfg_v2.model.make_model",
        graph=dict(path=str(graph_path), sha256=sha256(graph_path),
            fingerprint=fingerprint(graph), computation_fingerprint=computation_fingerprint(graph)),
        files={name:sha256(output/(name+".json")) for name in documents},
        nodes=len(graph), edges=graph.number_of_edges(), training_executed=False)
    write_json(output/"manifest.json", result)
    return result


def run(output=DEFAULT_OUTPUT, l1_directory=DEFAULT_L1, include_constants=False):
    output, l1_directory = Path(output).resolve(), Path(l1_directory).resolve()
    if output.exists():
        raise FileExistsError("Refusing to overwrite " + str(output))
    if type(include_constants) is not bool:
        raise ValueError("include_constants must be boolean")
    tasks, binding = verify_l1(l1_directory)
    runtime = _runtime()
    output.mkdir(parents=True)
    write_json(output/"run_inputs.json", dict(version=VERSION, profile="G2R",
        L1=binding, include_constants=include_constants, runtime=runtime,
        training_executed=False, model_forward_executed=False))
    from .l2 import augment_l2
    records = []
    for tid, record in tasks.items():
        started = time.monotonic()
        print(tid + ": frozen L1 + L2 acceptance", flush=True)
        graph_ref = record["bundle"]["graph"]
        graph = read_graph(checked(graph_ref["path"], graph_ref["sha256"]))
        before = fingerprint(graph)
        if (before != graph_ref["fingerprint"]
                or computation_fingerprint(graph) != graph_ref["computation_fingerprint"]):
            raise ValueError("L1 graph fingerprint differs")
        sources, metadata, used = load_sources(record, graph)
        l1_audit = read_json(record["directory"]/"audit.json")
        enhanced, audit = augment_l2(graph, sources, metadata, include_constants)
        if fingerprint(graph) != before:
            raise AssertionError("L2 mutated the input graph object")
        invariant = assert_l2_only(graph, enhanced)
        summary = coverage_summary(enhanced, audit, l1_audit)
        if summary["L1_fallback_functions"] != (
                record["summary"]["functions_total"] - record["summary"]["functions_supported"]):
            raise AssertionError("L1 fallback denominator differs from frozen summary")
        model = model_schema(enhanced, record["summary"]["task"])
        sample = sample_edges(enhanced, audit)
        summary.update(task_id=tid, task=record["summary"]["task"], files=len(sources),
            original_nodes=len(graph), L1_edges=graph.number_of_edges(),
            DATA_DEF_USE=sum(d["edge_type"] == DATA_DEF_USE for _,_,d in graph.edges(data=True)),
            nodes=len(enhanced), edges=enhanced.number_of_edges(),
            WRITES_STATE=summary["L2_edges"].get(WRITES_STATE,0),
            READS_STATE=summary["L2_edges"].get(READS_STATE,0), invariants=invariant,
            L2_canonical=model["L2_canonical"], parameters=model["parameter_count"],
            CPU_model_only=True, training_executed=False)
        acceptance = dict(invariants=invariant, coverage=summary,
                          L1_receipt_sha256=binding["receipt_sha256"])
        inputs = dict(L1_graph=graph_ref, L1_bundle=str(record["directory"]/"manifest.json"),
            L1_bundle_sha256=binding["task_manifests"][tid], sources=used,
            source_manifest=record["inputs"]["source_manifest"],
            source_manifest_sha256=record["inputs"]["source_manifest_sha256"],
            original_inputs=record["inputs"], include_constants=include_constants)
        summary["bundle"] = write_bundle(output/tid, enhanced, audit, inputs, acceptance, model, sample)
        summary["seconds"] = time.monotonic()-started
        write_json(output/tid/"summary.json", summary)
        records.append(summary)
        load_sources(record, graph)
        checked(graph_ref["path"], graph_ref["sha256"])
        print(tid + ": state anchors %d/%d; WRITES %d; READS %d; L1-fallback edges %d" % (
            summary["anchored_state_declarations"], summary["state_declarations"],
            summary["WRITES_STATE"], summary["READS_STATE"],
            summary["L1_fallback_L2_edges"]), flush=True)
        del graph, enhanced
        gc.collect()
    _, final_binding = verify_l1(l1_directory)
    if final_binding != binding:
        raise AssertionError("Frozen L1 inputs changed during L2 build")
    if _runtime() != runtime:
        raise AssertionError("Runtime source changed during L2 acceptance")
    result = dict(version=VERSION, profile="G2R", tasks=records, L1=binding,
        all_acceptance_passed=True, training_executed=False, model_forward_executed=False,
        runtime=runtime)
    write_json(output/"summary.json", result)
    columns = ["task_id","files","nodes","edges","state_declarations","anchored_state_declarations",
               "anchor_fraction","DATA_DEF_USE","WRITES_STATE","READS_STATE",
               "L1_fallback_functions","L1_fallback_functions_with_L2","L1_fallback_L2_edges",
               "cross_callable_pairs","alias_edges","alias_edge_fraction","parameters","seconds"]
    with (output/"summary.csv").open("w",newline="",encoding="utf8") as stream:
        writer=csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader()
        writer.writerows({key:row[key] for key in columns} for row in records)
    write_json(output/"receipt.json",dict(version=VERSION,status="accepted",
        L1_receipt_sha256=binding["receipt_sha256"],runtime=runtime,
        summary_sha256=sha256(output/"summary.json"),
        task_manifests={row["task_id"]:sha256(output/row["task_id"]/"manifest.json") for row in records},
        training_executed=False,optimizer_steps=0))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default=str(DEFAULT_OUTPUT))
    parser.add_argument("--l1-directory",default=str(DEFAULT_L1))
    parser.add_argument("--include-constants",action="store_true")
    args=parser.parse_args()
    run(args.output,args.l1_directory,args.include_constants)


if __name__ == "__main__":
    main()
