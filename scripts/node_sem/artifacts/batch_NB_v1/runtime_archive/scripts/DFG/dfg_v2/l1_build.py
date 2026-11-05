"""Prompt 2 real-data L1 acceptance; builds new bundles without training."""
import argparse
import csv
import gc
import time
from collections import Counter, defaultdict
from pathlib import Path

from scripts.DFG.frontend import SourceView, FUNCTION_TYPES, parse, walk
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import checked, read_json, read_sources, sha256, write_json
from scripts.DFG.integration.pipeline import build_graph, computation_fingerprint
from scripts.DFG.integration.rebuild import DEFAULT_MANIFEST
from scripts.DFG.models import Unsupported
from scripts.DFG.projection import Projector
from scripts.DFG.reaching_definitions import solve
from scripts.DFG.semantic_cfg import CFGBuilder
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from scripts.labeling_v2.safe_graph import read_graph, write_graph

from . import DATA_DEF_USE, REVERSE_OF, VERSION
from .l1 import augment_l1
from .l1_rd import solve_v2
from .model import make_model, validate_registration

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2"
DEFAULT_OUTPUT = ARTIFACTS / "l1_build"
DEFAULT_BASELINE = ARTIFACTS / "recon/scalar/summary.json"
EVIDENCE_KEYS = ("symbol", "function", "definition", "use", "source", "target", "self_fact")


def _unique_tasks(document, label):
    records = document.get("tasks")
    if not isinstance(records, list) or not records:
        raise ValueError(label + " must contain nonempty tasks")
    result = {}
    for record in records:
        name = record["task_id"]
        if not isinstance(name, str) or not name or name in result:
            raise ValueError(label + " task IDs must be unique nonempty strings")
        # IDs become subdirectories; never accept paths from manifest data.
        if name in (".", "..") or "/" in name or "\\" in name:
            raise ValueError("Unsafe task ID")
        result[name] = record
    return result


def _evidence(records):
    return Counter(tuple(record[key] for key in EVIDENCE_KEYS) for record in records)


def _pairs(graph):
    return Counter((source, target) for source, target, attrs in graph.edges(data=True)
                   if attrs["edge_type"] == DATA_DEF_USE)


def _function_records(audit):
    result = {}
    for file, record in audit["files"].items():
        for function in record.get("analysis", {}).get("functions", []):
            if function["function"] in result or function["file"] != file:
                raise AssertionError("Duplicate/misaligned function identity")
            result[function["function"]] = function
    return result


def check_legacy(base, old_graph, old_audit, graph, audit, sources, metadata,
                 max_iterations=100000):
    """Compare explicit old identities, including successes producing no facts."""
    scalar = old_audit["stages"]["scalar"]
    new_records = _function_records(audit)
    old_supported, zero_facts = set(), []
    solver_count, projector_equal = 0, 0
    projector_fallbacks, function_checks = [], []
    old_fact_counts = Counter(e["function"] for e in scalar["evidence"])
    grouped_old, grouped_new = defaultdict(list), defaultdict(list)
    for ev in scalar["evidence"]:
        grouped_old[ev["function"]].append(ev)
    for ev in audit["evidence"]:
        if ev["analysis_path"] == "legacy":
            grouped_new[ev["function"]].append(ev)
    for file, source in sorted(sources.items()):
        record = scalar["files"][file]
        diagnostics = record["diagnostics"]
        if any(d["kind"] == "file_fallback" for d in diagnostics):
            continue
        view = SourceView(source, file)
        failures = {d["function"] for d in diagnostics if d["kind"] == "function_fallback"}
        functions = {file + ":" + str(fn.start_byte): fn for fn in view.functions}
        supported = set(functions) - failures
        if len(supported) != record["analysis"]["functions_supported"]:
            raise AssertionError("Independent legacy success identity mismatch")
        for identity in sorted(supported):
            rec = new_records[identity]
            if (rec["old_status"] != "supported" or rec["status"] != "supported"
                    or rec["routes"] != ["legacy"] or not rec["legacy_reused"]):
                raise AssertionError("Legacy success was recalculated or lost: " + identity)
            if _evidence(grouped_old[identity]) != _evidence(grouped_new[identity]):
                raise AssertionError("Legacy projected facts differ: " + identity)
            # Same IR goes through both solvers; compare every result field,
            # including definitions, reachable set, iterations and use counters.
            ir = CFGBuilder(view, functions[identity]).build()
            original, extended = solve(ir, max_iterations), solve_v2(ir, max_iterations)
            if original != extended:
                raise AssertionError("Scalar solver equality failed: " + identity)
            solver_count += 1
            old_supported.add(identity)
            if not old_fact_counts[identity]:
                zero_facts.append(identity)
            function_checks.append(dict(function=identity, solver_equal=True,
                projected_facts_equal=True, projected_facts=old_fact_counts[identity],
                analysis_facts=rec["facts"]))
        try:
            supported_view = SupportedSourceView(source, file, metadata.get(file))
        except Unsupported as exc:
            projector_fallbacks.append(dict(file=file, stage="supported_view", reason=str(exc)))
        else:
            try:
                a, b = Projector(base, view), Projector(base, supported_view)
            except Unsupported as exc:
                projector_fallbacks.append(dict(file=file, stage="projector", reason=str(exc)))
            else:
                if a.by_ast != b.by_ast:
                    raise AssertionError("Raw/compat Projector.by_ast mismatch: " + file)
                projector_equal += 1
    from_records = {key for key, rec in new_records.items() if rec["old_status"] == "supported"}
    if from_records != old_supported:
        raise AssertionError("L1 old-success identities differ from independent legacy run")
    if _evidence(scalar["evidence"]) != _evidence(
            [e for e in audit["evidence"] if e["analysis_path"] == "legacy"]):
        raise AssertionError("Whole legacy projected evidence changed")
    old_pairs, new_pairs = _pairs(old_graph), _pairs(graph)
    legacy_pairs = Counter({(e["source"], e["target"]): 1
                            for e in audit["evidence"]
                            if e["analysis_path"] == "legacy" and not e["self_fact"]})
    if old_pairs != legacy_pairs or any(count != 1 for count in old_pairs.values()):
        raise AssertionError("Legacy projected edge identity/multiplicity differs")
    if old_pairs - new_pairs:
        raise AssertionError("New L1 is not an edge superset of original scalar")
    return dict(legacy_supported=len(old_supported),
        legacy_zero_projected_fact_functions=zero_facts,
        solver_equal_functions=solver_count, old_edges=len(old_pairs),
        old_edges_exact=True, old_facts_exact=True, edge_superset=True,
        projectors_by_ast_equal_files=projector_equal,
        projector_comparison_fallbacks=projector_fallbacks, functions=function_checks)


def _summary(audit):
    functions = list(_function_records(audit).values())
    old_reasons = Counter(rec["old_reason"] for rec in functions if rec["old_status"] != "supported")
    new_reasons = Counter(rec["reason"] for rec in functions if rec["status"] != "supported")
    routes = Counter(route for rec in functions for route in rec["routes"])
    cross = Counter((rec["old_reason"] or "legacy_supported",
        "+".join(rec["routes"]) if rec["status"] == "supported" else "fallback:" + rec["reason"])
        for rec in functions)
    recovery = []
    for reason, count in old_reasons.most_common():
        selected = [rec for rec in functions if rec["old_reason"] == reason]
        recovered = [rec for rec in selected if rec["recovered"]]
        recovery.append(dict(old_reason=reason, before=count, recovered=len(recovered),
            still_fallback=count-len(recovered),
            recovery_routes=dict(Counter(route for rec in recovered for route in rec["routes"]))))
    return dict(functions_total=len(functions),
        legacy_supported=sum(rec["old_status"] == "supported" for rec in functions),
        functions_supported=sum(rec["status"] == "supported" for rec in functions),
        recovered=sum(rec["recovered"] for rec in functions),
        routes=dict(routes), old_fallback_top10=old_reasons.most_common(10),
        new_fallback_top10=new_reasons.most_common(10),
        new_fallback_reasons=dict(new_reasons), recovery_by_old_reason=recovery,
        recovery_cross_table=[dict(old_reason=a, new_result=b, functions=count)
                              for (a,b),count in sorted(cross.items())],
        modifier_facts_dropped=sum(record.get("analysis", {}).get("modifier_facts_dropped", 0)
                                  for record in audit["files"].values()))


def _schema(graph, task):
    # Construction only: no model forward, loss, optimizer or training.
    model = make_model(task, graph, "G1R", device="cpu")
    schema = validate_registration(model)
    relation_names = {DATA_DEF_USE, REVERSE_OF[DATA_DEF_USE]}
    canonical = [dict(canonical=list(key), edges=model.symmetrical_global_graph.num_edges(key))
                 for key in sorted(model.etypes_dict) if key[1] in relation_names]
    record = dict(profile="G1R", adapter="scripts.DFG.dfg_v2.model.make_model",
        device="cpu", node_feature=model.node_feature, input_width=model.in_size,
        schema=schema, enhancement_canonical=canonical,
        parameter_count=sum(p.numel() for p in model.parameters()),
        model_forward_executed=False, optimizer_steps=0, training_executed=False)
    del model
    gc.collect()
    return record


def _bundle(output, graph, audit, inputs, acceptance, model):
    output = Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    output.mkdir()
    graph_path = output / "hcg.gpickle"
    write_graph(graph, graph_path)
    if fingerprint(read_graph(graph_path)) != fingerprint(graph):
        raise AssertionError("Output graph serialization roundtrip differs")
    for name, data in (("audit", audit), ("inputs", inputs),
                       ("acceptance", acceptance), ("model_schema", model)):
        write_json(output / (name + ".json"), data)
    record = dict(version=VERSION, layer="L1", profile="G1R",
        adapter="scripts.DFG.dfg_v2.model.make_model",
        graph=dict(path=str(graph_path), sha256=sha256(graph_path),
                   fingerprint=fingerprint(graph),
                   computation_fingerprint=computation_fingerprint(graph)),
        files={name: sha256(output / (name + ".json"))
               for name in ("audit", "inputs", "acceptance", "model_schema")},
        nodes=len(graph), edges=graph.number_of_edges(), training_executed=False)
    write_json(output / "manifest.json", record)
    return record


def _runtime():
    paths = set((ROOT / "scripts/DFG").rglob("*.py"))
    paths.update([ROOT / "sco_models/graph_utils.py", ROOT / "sco_models/model_hgt.py",
                  ROOT / "scripts/labeling_v2/safe_graph.py"])
    return {str(path.relative_to(ROOT)): sha256(path) for path in sorted(paths)}


def run(output=DEFAULT_OUTPUT, manifest=DEFAULT_MANIFEST, baseline=DEFAULT_BASELINE,
        max_iterations=100000):
    output, manifest, baseline = (Path(p).resolve() for p in (output, manifest, baseline))
    if output.exists():
        raise FileExistsError("Refusing to overwrite " + str(output))
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    manifest_sha = read_json(manifest.with_name("manifest.seal.json"))["sha256"]
    checked(manifest, manifest_sha)
    document = read_json(manifest)
    references = _unique_tasks(document, "Input manifest")
    baseline_sha = sha256(baseline)
    baseline_tasks = _unique_tasks(read_json(baseline), "Prompt 0 baseline")
    if set(references) != set(baseline_tasks):
        raise ValueError("Task matrix differs from Prompt 0 acceptance")
    runtime = _runtime()
    output.mkdir(parents=True)
    records = []
    write_json(output / "run_inputs.json", dict(version=VERSION, manifest=str(manifest),
        manifest_sha256=manifest_sha, prompt0_baseline=str(baseline),
        prompt0_baseline_sha256=baseline_sha, runtime=runtime, max_iterations=max_iterations,
        training_executed=False, model_forward_executed=False))
    for tid, ref in references.items():
        start = time.monotonic()
        print(tid + ": original scalar vs L1 acceptance", flush=True)
        task_path = checked(ref["source_task_manifest"], ref["source_task_sha256"])
        source_path = checked(ref["source_metadata_manifest"], ref["source_metadata_sha256"])
        task = read_json(task_path)
        if ref["task"] not in ("node", "contract"):
            raise ValueError("Unknown task granularity")
        original = task["graphs"]["HCG"]
        path = checked(original["path"], original["sha256"])
        base = read_graph(path)
        sources, metadata, used, missing = read_sources(source_path, base)
        if missing:
            raise ValueError("Acceptance requires all frozen sources: " + repr(missing))
        p0 = baseline_tasks[tid]
        # Bind the old denominator to the exact same graph and source files.
        p0_bundle = p0["bundle"]
        p0_dir = Path(p0_bundle["graph"]["path"]).parent
        p0_inputs_path = checked(p0_dir / "inputs.json", p0_bundle["inputs_sha256"])
        p0_inputs = read_json(p0_inputs_path)
        if (p0_inputs["original_graph"]["sha256"] != original["sha256"]
                or p0_inputs["source_manifest_sha256"] != ref["source_metadata_sha256"]
                or {k:v["sha256"] for k,v in p0_inputs["sources"].items()} !=
                   {k:v["sha256"] for k,v in used.items()}):
            raise ValueError("Prompt 0 denominator/input identities differ")
        raw_total = sum(sum(n.type in FUNCTION_TYPES and n.child_by_field_name("body") is not None
                            for n in walk(parse(source).root_node)) for source in sources.values())
        if raw_total != p0["raw_functions_with_body"]:
            raise AssertionError("Function denominator differs from frozen Prompt 0")
        old_graph, old_audit = build_graph(base, sources, profile="scalar", metadata=metadata,
                                           max_iterations=max_iterations)
        enhanced, audit = augment_l1(base, sources, metadata, max_iterations)
        acceptance = check_legacy(base, old_graph, old_audit, enhanced, audit,
                                  sources, metadata, max_iterations)
        summary = _summary(audit)
        if (summary["functions_total"] != raw_total or summary["legacy_supported"] != p0["functions_supported"]
                or acceptance["old_edges"] != p0["DATA_DEF_USE"]):
            raise AssertionError("Prompt 0 scalar support/edge baseline changed")
        model = _schema(enhanced, ref["task"])
        new_edges = sum(d["edge_type"] == DATA_DEF_USE for _,_,d in enhanced.edges(data=True))
        summary.update(task_id=tid, task=ref["task"], files=len(used),
            original_nodes=len(base), original_edges=base.number_of_edges(),
            old_DATA_DEF_USE=acceptance["old_edges"], DATA_DEF_USE=new_edges,
            incremental_DATA_DEF_USE=new_edges-acceptance["old_edges"],
            before_support_fraction=summary["legacy_supported"]/raw_total if raw_total else None,
            after_support_fraction=summary["functions_supported"]/raw_total if raw_total else None,
            invariants=audit["invariants"], acceptance=acceptance,
            enhancement_canonical=model["enhancement_canonical"])
        inputs = dict(original_graph=original, task_manifest=str(task_path),
            task_manifest_sha256=ref["source_task_sha256"],
            source_manifest=str(source_path), source_manifest_sha256=ref["source_metadata_sha256"],
            sources=used, missing_sources=missing, prompt0_baseline=str(baseline),
            prompt0_baseline_sha256=baseline_sha, prompt0_inputs_sha256=sha256(p0_inputs_path))
        summary["bundle"] = _bundle(output/tid, enhanced, audit, inputs, acceptance, model)
        summary["seconds"] = time.monotonic()-start
        write_json(output/tid/"summary.json", summary)
        records.append(summary)
        for source in used.values():
            checked(source["path"], source["sha256"])
        checked(task_path, ref["source_task_sha256"])
        checked(source_path, ref["source_metadata_sha256"])
        checked(path, original["sha256"])
        print(tid + ": support %d -> %d / %d; DDG %d -> %d; legacy exact" % (
            summary["legacy_supported"], summary["functions_supported"], raw_total,
            summary["old_DATA_DEF_USE"], new_edges), flush=True)
        del base, old_graph, enhanced
        gc.collect()
    checked(manifest, manifest_sha)
    checked(baseline, baseline_sha)
    if _runtime() != runtime:
        raise AssertionError("Runtime source files changed during acceptance")
    result = dict(version=VERSION, profile="G1R", tasks=records, all_acceptance_passed=True,
                  training_executed=False, model_forward_executed=False, runtime=runtime)
    write_json(output/"summary.json", result)
    columns = ["task_id", "functions_total", "legacy_supported", "functions_supported",
               "recovered", "before_support_fraction", "after_support_fraction",
               "old_DATA_DEF_USE", "DATA_DEF_USE", "incremental_DATA_DEF_USE", "seconds"]
    with (output/"summary.csv").open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key:row[key] for key in columns} for row in records)
    write_json(output/"receipt.json", dict(version=VERSION, status="accepted",
        manifest_sha256=manifest_sha, prompt0_baseline_sha256=baseline_sha,
        runtime=runtime, summary_sha256=sha256(output/"summary.json"),
        task_manifests={row["task_id"]:sha256(output/row["task_id"]/"manifest.json")
                        for row in records}, training_executed=False, optimizer_steps=0))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--baseline-summary", default=str(DEFAULT_BASELINE))
    parser.add_argument("--max-iterations", type=int, default=100000)
    args = parser.parse_args()
    run(args.output, args.manifest, args.baseline_summary, args.max_iterations)


if __name__ == "__main__":
    main()
