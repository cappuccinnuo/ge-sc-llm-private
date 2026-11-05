"""Read-only Prompt 3 projection parity and state-declaration anchor audit."""
import argparse
import csv
import gc
import hashlib
import sys
import time
from collections import Counter
from pathlib import Path

from scripts.DFG.frontend import SourceView, parse, text, walk
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import checked, read_json, read_sources, sha256, write_json
from scripts.DFG.models import Unsupported
from scripts.DFG.projection import Projector
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from scripts.labeling_v2.safe_graph import read_graph

from . import VERSION
from .projection_view import ProjectionView
from .units import projected_node

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2"
DEFAULT_L1 = ARTIFACTS / "l1_build/final_route_audit"
DEFAULT_OUTPUT = ARTIFACTS / "prompt3_v1/projection_audit"


def _tasks(records):
    result = {}
    if not isinstance(records, list) or not records:
        raise ValueError("Expected a nonempty task list")
    for record in records:
        name = record["task_id"]
        if (not isinstance(name, str) or not name or name in result or name in (".", "..")
                or "/" in name or "\\" in name):
            raise ValueError("Unsafe or duplicate task identity")
        result[name] = record
    return result


def mapping_snapshot(view):
    """Node objects belong to separate trees; compare every node structurally."""
    return dict(mapping=view.mapping, compat_ids=view.compat_ids,
        compat_nodes={key: (node.start_point, node.end_point, node.sexp())
                      for key, node in view.compat_nodes.items()},
        compat_source=view.compat_source)


def assert_mapping_equal(original, projection):
    if mapping_snapshot(original) != mapping_snapshot(projection):
        raise AssertionError("ProjectionView exact AST mapping differs: " + original.file)


def audit_file(graph, file, source, metadata=None):
    rec = dict(file=file, source_sha256=hashlib.sha256(source.encode("utf8")).hexdigest(),
               views={}, declarations=[], source_view_parity=None)
    try:
        raw = parse(source)
    except Unsupported as exc:
        rec["parse_error"] = str(exc)
        return rec
    declarations = [node for node in walk(raw.root_node) if node.type == "state_variable_declaration"]
    views, projectors = {}, {}
    for key, factory in (
            ("source_view", lambda: SourceView(source, file)),
            ("supported_view", lambda: SupportedSourceView(source, file, metadata)),
            ("projection_view", lambda: ProjectionView(source, file))):
        try:
            view = factory()
        except Unsupported as exc:
            rec["views"][key] = dict(status="unsupported", stage="view", reason=str(exc))
            continue
        views[key] = view
        try:
            projector = Projector(graph, view)
        except Unsupported as exc:
            rec["views"][key] = dict(status="unsupported", stage="projector", reason=str(exc))
        else:
            projectors[key] = projector
            rec["views"][key] = dict(projector.stats, status="verified")
    if "source_view" in views:
        if "projection_view" not in views:
            raise AssertionError("ProjectionView lost a SourceView-supported file: " + file)
        assert_mapping_equal(views["source_view"], views["projection_view"])
        rec["source_view_parity"] = True
        if "source_view" in projectors and "projection_view" in projectors:
            if projectors["source_view"].by_ast != projectors["projection_view"].by_ast:
                raise AssertionError("Projector exact identity differs: " + file)
    for node in declarations:
        item = dict(start_byte=node.start_byte, end_byte=node.end_byte,
                    line=node.start_point[0]+1, end_line=node.end_point[0]+1,
                    text=text(source, node))
        name_node = node.child_by_field_name("name")
        item["name"] = text(source, name_node) if name_node is not None else None
        for key in ("source_view", "supported_view", "projection_view"):
            identifier = projected_node(views[key], projectors[key], node) if key in projectors else None
            role = graph.nodes[identifier]["node_type"] if identifier is not None else None
            item[key] = dict(node_id=identifier, node_type=role,
                status="view_unverified" if key not in projectors else
                       "no_exact_hcg_node" if identifier is None else
                       "wrong_anchor_type" if role != "new_variable" else "matched")
        rec["declarations"].append(item)
    return rec


def summarize(files):
    declarations = [item for rec in files for item in rec["declarations"]]
    result = dict(files=len(files), declarations=len(declarations),
        source_view_parity_files=sum(rec["source_view_parity"] is True for rec in files),
        parse_failures=[dict(file=rec["file"], reason=rec["parse_error"])
                        for rec in files if "parse_error" in rec])
    for view in ("source_view", "supported_view", "projection_view"):
        hits = sum(item[view]["status"] == "matched" for item in declarations)
        failures = [dict(file=rec["file"], **rec["views"][view])
                    for rec in files if rec["views"].get(view, {}).get("status") == "unsupported"]
        result[view] = dict(anchors=hits, declarations=len(declarations),
            fraction=hits/len(declarations) if declarations else None,
            verified_files=sum(rec["views"].get(view, {}).get("status") == "verified" for rec in files),
            ordinary_nodes_checked=sum(rec["views"].get(view, {}).get("ordinary_nodes_checked", 0)
                                       for rec in files),
            failures=failures, failure_reasons=dict(Counter(item["reason"] for item in failures)))
    result["recovered_from_supported_view"] = [
        dict(file=rec["file"], source_sha256=rec["source_sha256"],
             old_failure=rec["views"]["supported_view"],
             declarations=len(rec["declarations"]),
             anchors=sum(item["projection_view"]["status"] == "matched"
                         for item in rec["declarations"]))
        for rec in files
        if rec["views"].get("supported_view", {}).get("status") == "unsupported"
        and rec["views"].get("projection_view", {}).get("status") == "verified"]
    result["projection_missing_anchors"] = [
        dict(file=rec["file"], **item) for rec in files for item in rec["declarations"]
        if item["projection_view"]["status"] != "matched"]
    result["anchor_gate_passed"] = (not result["parse_failures"]
        and result["projection_view"]["fraction"] is not None
        and result["projection_view"]["fraction"] >= .9)
    return result


def _runtime():
    # Only modules used by this audit, not unrelated concurrently edited L2 code.
    paths = [
        "scripts/DFG/dfg_v2/l2_projection_audit.py",
        "scripts/DFG/dfg_v2/projection_view.py", "scripts/DFG/dfg_v2/units.py",
        "scripts/DFG/frontend.py", "scripts/DFG/projection.py", "scripts/DFG/models.py",
        "scripts/DFG/graph_audit.py", "scripts/DFG/integration/io.py",
        "scripts/labeling_v2/safe_graph.py",
        "process_graphs/tree_sitter_codeviews/utils/preprocessor.py",
    ]
    paths += [str(p.relative_to(ROOT)) for p in (ROOT/"scripts/DFG/state").rglob("*.py")]
    return {path: sha256(ROOT/path) for path in sorted(set(paths))}


def _bind_l1(l1):
    receipt_path, run_path = l1/"receipt.json", l1/"run_inputs.json"
    receipt, run = read_json(receipt_path), read_json(run_path)
    if receipt.get("status") != "accepted" or receipt.get("training_executed") is not False:
        raise ValueError("L1 receipt is not an accepted nontraining build")
    summary = read_json(checked(l1/"summary.json", receipt["summary_sha256"]))
    tasks = _tasks(summary["tasks"])
    if set(tasks) != set(receipt["task_manifests"]):
        raise ValueError("L1 receipt task set differs from summary")
    if (run["manifest_sha256"] != receipt["manifest_sha256"]
            or run.get("runtime") != receipt.get("runtime")
            or summary.get("runtime") != receipt.get("runtime")):
        raise ValueError("L1 receipt/run-input identity mismatch")
    manifest = checked(run["manifest"], receipt["manifest_sha256"])
    refs = _tasks(read_json(manifest)["tasks"])
    if set(refs) != set(tasks):
        raise ValueError("L1 manifest task set differs")
    return receipt, run, tasks, refs, manifest


def run(output=DEFAULT_OUTPUT, l1_directory=DEFAULT_L1):
    output, l1 = Path(output).resolve(), Path(l1_directory).resolve()
    if output.exists():
        raise FileExistsError("Refusing to overwrite " + str(output))
    receipt, old_run, tasks, refs, manifest = _bind_l1(l1)
    runtime = _runtime()
    bound = {str(l1/name): sha256(l1/name)
             for name in ("receipt.json", "run_inputs.json", "summary.json")}
    bound[str(manifest)] = receipt["manifest_sha256"]
    output.mkdir(parents=True)
    records = []
    write_json(output/"run_inputs.json", dict(version=VERSION, l1_directory=str(l1),
        l1_receipt_sha256=bound[str(l1/"receipt.json")],
        l1_run_inputs_sha256=bound[str(l1/"run_inputs.json")],
        runtime=runtime, python=sys.version, no_graph_mutation=True,
        model_construction=False, training_executed=False))
    for task_id, task in tasks.items():
        start = time.monotonic()
        print(task_id + ": projection parity and declaration anchors", flush=True)
        bundle_path = checked(l1/task_id/"manifest.json", receipt["task_manifests"][task_id])
        bundle = read_json(bundle_path)
        if bundle != task["bundle"] or bundle.get("layer") != "L1":
            raise ValueError("L1 task summary/bundle identity mismatch")
        bound[str(bundle_path)] = receipt["task_manifests"][task_id]
        inputs_path = checked(l1/task_id/"inputs.json", bundle["files"]["inputs"])
        inputs = read_json(inputs_path)
        bound[str(inputs_path)] = bundle["files"]["inputs"]
        ref = refs[task_id]
        if (inputs["source_manifest_sha256"] != ref["source_metadata_sha256"]
                or inputs["task_manifest_sha256"] != ref["source_task_sha256"]):
            raise ValueError("L1 source/task reference mismatch")
        source_path = checked(inputs["source_manifest"], inputs["source_manifest_sha256"])
        task_path = checked(inputs["task_manifest"], inputs["task_manifest_sha256"])
        if read_json(task_path)["graphs"]["HCG"] != inputs["original_graph"]:
            raise ValueError("Original task graph identity changed")
        graph_path = checked(bundle["graph"]["path"], bundle["graph"]["sha256"])
        graph = read_graph(graph_path)
        if fingerprint(graph) != bundle["graph"]["fingerprint"]:
            raise AssertionError("L1 graph fingerprint differs")
        sources, metadata, used, missing = read_sources(source_path, graph)
        if missing or used != inputs["sources"]:
            raise ValueError("L1 source identities differ or are missing")
        bound[str(source_path)] = inputs["source_manifest_sha256"]
        bound[str(task_path)] = inputs["task_manifest_sha256"]
        bound[str(graph_path)] = bundle["graph"]["sha256"]
        for source in used.values():
            bound[str(Path(source["path"]).resolve())] = source["sha256"]
            for path_key, hash_key in (("csv_path", "csv_sha256"), ("source_path", "source_sha256")):
                meta = source.get("metadata") or {}
                if path_key in meta:
                    metadata_path = checked(meta[path_key], meta[hash_key])
                    bound[str(metadata_path)] = meta[hash_key]
        files = [audit_file(graph, name, source, metadata.get(name))
                 for name, source in sorted(sources.items())]
        result = summarize(files)
        result.update(task_id=task_id, task=task["task"], seconds=time.monotonic()-start,
                      input_graph=dict(bundle["graph"]))
        write_json(output/(task_id+".json"), dict(summary=result, files=files))
        records.append(result)
        print(task_id + ": parity=%d; supported anchors=%d/%d; projection anchors=%d/%d" % (
            result["source_view_parity_files"], result["supported_view"]["anchors"],
            result["declarations"], result["projection_view"]["anchors"],
            result["declarations"]), flush=True)
        del graph
        gc.collect()
    for path, digest in bound.items():
        checked(path, digest)
    if runtime != _runtime():
        raise AssertionError("Projection audit runtime changed while executing")
    result = dict(version=VERSION, tasks=records, no_graph_mutation=True,
        training_executed=False, model_construction=False,
        all_source_view_comparisons_equal=True,
        all_anchor_gates_passed=all(task["anchor_gate_passed"] for task in records))
    write_json(output/"summary.json", result)
    columns = ("task_id", "declarations", "source_view_parity_files",
               "supported_anchors", "projection_anchors", "projection_fraction",
               "projection_failures", "seconds")
    with (output/"summary.csv").open("w", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for rec in records:
            writer.writerow(dict(task_id=rec["task_id"], declarations=rec["declarations"],
                source_view_parity_files=rec["source_view_parity_files"],
                supported_anchors=rec["supported_view"]["anchors"],
                projection_anchors=rec["projection_view"]["anchors"],
                projection_fraction=rec["projection_view"]["fraction"],
                projection_failures=len(rec["projection_view"]["failures"]), seconds=rec["seconds"]))
    write_json(output/"receipt.json", dict(version=VERSION, status="accepted",
        inputs=bound, runtime=runtime, summary_sha256=sha256(output/"summary.json"),
        task_reports={rec["task_id"]:sha256(output/(rec["task_id"]+".json")) for rec in records},
        no_graph_mutation=True, model_construction=False, training_executed=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--l1-directory", default=str(DEFAULT_L1))
    args = parser.parse_args()
    run(args.output, args.l1_directory)


if __name__ == "__main__":
    main()
