"""Independent, read-only postprocessor for all 60 completed Stage I replays.

This file lives in the output area and does not alter the sealed replay runtime.
Run only after every E3a/E3b task fold has best and last accepted predictions.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROLE = "exploratory_cv_validation_fixed_checkpoint_sensitivity"
THRESHOLD = 1e-8
CONDITIONS = ("Z_D", "Z_S", "Z_C", "Z_SC", "Z_ALL")
TASKS = ("reentrancy_author_contract", "access_control_author_contract",
         "reentrancy_author_node", "access_control_author_node")
HARD = {"reentrancy_author": ("buggy_18.sol", "buggy_36.sol"),
        "access_control_author": ("buggy_18.sol", "buggy_26.sol")}
REPO = next(p for p in Path(__file__).resolve().parents if (p/"sco_models").is_dir())
sys.path.insert(0, str(REPO))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(path, expected, inputs):
    path = Path(path)
    if sha(path) != expected:
        raise ValueError("SHA mismatch: " + str(path))
    inputs[str(path)] = expected
    return path


def csv_rows(path):
    with Path(path).open(encoding="utf8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("x", encoding="utf8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list, tuple))
                             else v for k, v in row.items()})


def node_id(value, csv_input=False):
    if csv_input:
        return json.loads(value) if value else None
    return value


def identity(row, csv_input=False):
    return (row["task_id"], row["cohort"], row["source_sha256"], row["file"],
            json.dumps(node_id(row.get("original_graph_node_id"), csv_input), sort_keys=True))


def static_index(rows):
    result = {}
    for row in rows:
        if row["contrast"] not in ("E3a-E2", "E3b-E2"):
            continue
        variant = row["contrast"].split("-")[0]
        key = (variant, identity(row, True))
        if key in result:
            raise ValueError("Duplicate static prediction identity")
        result[key] = row
    return result


def require_matrix(jobs, receipt_paths, output):
    expected = {(t, f, v) for t in TASKS for f in range(5 if t.endswith("_contract") else 10)
                for v in ("E3a", "E3b")}
    actual = [(j["task_id"], j["fold"], j["variant"]) for j in jobs]
    if len(actual) != 60 or len(set(actual)) != 60 or set(actual) != expected:
        raise ValueError("Expected all 60 task/fold/variant jobs")
    folders = {str(Path(output)/"replays"/t/("fold_"+str(f))/v/"receipt.json")
               for t, f, v in expected}
    if set(map(str, receipt_paths)) != folders:
        raise ValueError("Incomplete/extra replay receipts; refuse formal output")


def validate_prediction(row, job, checkpoint, context):
    for key in ("task_id", "task", "cohort", "fold", "variant"):
        if row.get(key) != job[key]:
            raise ValueError("Replay job identity mismatch: " + key)
    if row["checkpoint"] != checkpoint or row["score_role"] != ROLE:
        raise ValueError("Replay checkpoint/scoring mismatch")
    if identity(row) != identity(context, True):
        raise ValueError("Source/cohort/original node identity mismatch")
    if int(context["target"]) != row["target"] or int(context["fold"]) != row["fold"]:
        raise ValueError("Frozen label/fold mismatch")
    if job["task"] == "node" and row["node_type"] != context["node_type"]:
        raise ValueError("Frozen node type mismatch")
    for condition in ("N",) + CONDITIONS:
        if row[condition+"_pred"] not in (0, 1):
            raise ValueError("Nonbinary prediction")
        probability = row[condition+"_prob"]
        if not isinstance(probability, (float, int)) or not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("Invalid prediction probability")


def intervention(row, context, condition):
    before, after, y = row["N_pred"], row[condition+"_pred"], row["target"]
    delta = row[condition+"_prob"] - row["N_prob"]
    applicable = row.get("task") == "node"
    inside = context.get("potential_influence_within_two") == "True" if applicable else None
    new_context = int(context.get("new_upstream_count_two") or 0) > 0 if applicable else None
    return {"before_error": before != y, "after_error": after != y,
            "corrected": before != y and after == y,
            "regressed": before == y and after != y,
            "class_changed": before != after,
            "probability_changed": abs(delta) > THRESHOLD,
            "probability_delta": delta, "abs_probability_delta": abs(delta),
            "potential_scope": inside, "new_context_scope": new_context, "local_scope_applicable": applicable,
            "class_changed_outside_potential": applicable and before != after and not inside,
            "probability_changed_outside_potential": applicable and abs(delta) > THRESHOLD and not inside}


def summarize_group(items):
    n = len(items)
    result = {"n": n}
    for key in ("before_error", "after_error", "corrected", "regressed", "class_changed",
                "probability_changed", "potential_scope", "new_context_scope", "local_scope_applicable",
                "class_changed_outside_potential", "probability_changed_outside_potential"):
        result[key] = sum(x[key] is True for x in items)
    for scope in ("potential_scope", "new_context_scope"):
        for inside in (True, False):
            selected = [x for x in items if x[scope] == inside]
            prefix = scope + ("_inside_" if inside else "_outside_")
            result[prefix+"nodes"] = len(selected)
            for key in ("before_error", "after_error", "class_changed", "probability_changed"):
                result[prefix+key] = sum(x[key] for x in selected)
    result["mean_abs_probability_delta"] = sum(x["abs_probability_delta"] for x in items)/n if n else 0.0
    result["max_abs_probability_delta"] = max((x["abs_probability_delta"] for x in items), default=0.0)
    return result


def static_descriptions(static_rows, edge_rows, coverage_note, inputs):
    """No graph/source analysis: recompute descriptive counts from archived rows."""
    error_groups = defaultdict(list)
    for row in static_rows:
        if row["contrast"] == "E3b-E2" and row["task_id"].endswith("_node"):
            error_groups[row["task_id"]].append(row)
    errors = []
    for task, rows in error_groups.items():
        if len({identity(r, True) for r in rows}) != len(rows):
            raise ValueError("Duplicate node in error coverage")
        for scope, field in (("potential_influence", "potential_influence_within_two"),
                             ("new_upstream_context", "new_upstream_count_two")):
            for inside in (True, False):
                chosen = [r for r in rows if
                          (r[field] == "True" if field == "potential_influence_within_two"
                           else int(r[field]) > 0) == inside]
                for model in ("before", "after"):
                    count = sum(r[model+"_best"] != r["target"] for r in chosen)
                    total_errors = sum(r[model+"_best"] != r["target"] for r in rows)
                    errors.append({"task_id": task, "contrast": "E3b-E2", "checkpoint": "best",
                        "variant": "E2" if model == "before" else "E3b", "scope": scope, "inside": inside,
                        "n": len(chosen), "errors": count, "total_errors": total_errors,
                        "error_rate_percent": 100*count/len(chosen) if chosen else None,
                        "share_all_errors_percent": 100*count/total_errors if total_errors else None})
    note = read(coverage_note)
    inputs[str(coverage_note)] = sha(coverage_note)
    index_paths = [p for p in note["inputs_sha256"] if Path(p).name == "relation_evidence_index.json"]
    if len(index_paths) != 1:
        raise ValueError("Ambiguous historical constructor evidence")
    checked(index_paths[0], note["inputs_sha256"][index_paths[0]], inputs)
    constructors = []
    for task in note["tasks"]:
        old = task["state_def_use_function_context"]
        old_keys = {(x["file"], x["source_node"], x["target_node"], x["function"]) for x in old}
        new_keys = {(x["file"], json.loads(x["source_node"]), json.loads(x["target_node"]), proof["function"])
                    for x in edge_rows if x["task_id"] == task["task_id"] and x["contrast"] == "E3a-E2"
                    and x["relation"] == "STATE_DEF_USE" for proof in json.loads(x["semantic_evidence"])}
        if old_keys != new_keys:
            raise ValueError("Historical constructor classification edge identity drift")
        constructor_count = sum(x["function_signature"].lstrip().startswith("constructor") for x in old)
        constructors.append({"task_id": task["task_id"], "state_def_use_edges": len(old),
            "constructor_edges": constructor_count, "other_function_edges": len(old)-constructor_count,
            "other_function_signatures": sorted({x["function_signature"] for x in old
                if not x["function_signature"].lstrip().startswith("constructor")}),
            "edge_identities_matched": True})
    return {"error_coverage": errors, "state_def_use_constructor_context": constructors,
        "classification_source": str(coverage_note),
        "scope": "Existing evidence rechecked; no new source parsing, Oracle, label adjudication or statistical significance.",
        "caveats": ["Node tasks are subsets of contract tasks, not independent additional edges.",
                    "Reachability and error overlap are descriptive, not causal utility.",
                    "Historical constructor evidence is inherited audit evidence, not new independent human approval."]}


def process(output, dest=None):
    from scripts.DFG.experiments.stage_i_diagnostics.common import verify_plan
    output = Path(output).resolve()
    dest = Path(dest).resolve() if dest else output/"prediction_context"
    if dest.exists():
        raise FileExistsError("Refuse existing joined output")
    plan = verify_plan(output)
    require_matrix(plan["jobs"], list((output/"replays").rglob("receipt.json")), output)
    inputs = {str(output/"plan.json"): sha(output/"plan.json"),
              str(output/"plan.seal.json"): sha(output/"plan.seal.json")}
    static_paths = {}
    for path, expected in plan["observed_static_sha256"].items():
        checked(path, expected, inputs)
        static_paths[Path(path).name] = Path(path)
    static_rows = csv_rows(static_paths["prediction_evidence.csv"])
    edge_rows = csv_rows(static_paths["edge_evidence.csv"])
    contexts = static_index(static_rows)
    by_target = defaultdict(list)
    for row in edge_rows:
        if row["contrast"] in ("E3a-E2", "E3b-E2"):
            key = (row["task_id"], row["contrast"].split("-")[0], row["cohort"],
                   row["source_sha256"], row["file"], json.dumps(json.loads(row["target_node"])))
            by_target[key].append({"source_node": json.loads(row["source_node"]),
                "target_node": json.loads(row["target_node"]), "relation": row["relation"],
                "canonical": [row["source_type"], row["relation"], row["target_type"]],
                "proof_indices": [x["stage_f_provenance_index"] for x in json.loads(row["semantic_evidence"])]})
    grouped, files, changes, chains = defaultdict(list), defaultdict(list), [], []
    completed, populations, seen = [], defaultdict(set), set()
    task_info_cache = {}
    for job in plan["jobs"]:
        folder = output/"replays"/job["task_id"]/("fold_"+str(job["fold"]))/job["variant"]
        receipt_path = folder/"receipt.json"
        inputs[str(receipt_path)] = sha(receipt_path)
        receipt = read(receipt_path)
        if receipt["status"] != "passed" or receipt["plan_sha256"] != inputs[str(output/"plan.json")]:
            raise ValueError("Wrong diagnostic receipt/plan")
        if receipt["source_receipt_sha256"] != job["receipt_sha256"]:
            raise ValueError("Wrong historical receipt")
        for relative, expected in receipt["artifact_sha256"].items():
            p = (folder/relative).resolve()
            if folder not in p.parents:
                raise ValueError("Receipt path escapes replay folder")
            checked(p, expected, inputs)
        required = {"metadata.json"} | {ck+"/"+name for ck in ("best", "last")
                    for name in ("scores.json", "audit.json", "predictions.json")}
        if not required <= set(receipt["artifact_sha256"]):
            raise ValueError("Missing best/last receipt artifacts")
        meta = read(folder/"metadata.json")
        if meta["job"] != job:
            raise ValueError("Metadata job mismatch")
        info_path = checked(job["task_manifest"], job["task_manifest_sha256"], inputs)
        info = read(info_path)
        if job["task_id"] not in task_info_cache:
            task_info_cache[job["task_id"]] = info
        prep_path = checked(info["source_prepared_manifest"], info["source_prepared_manifest_sha256"], inputs)
        sources = read(prep_path)["sources"]
        for ck in ("best", "last"):
            pred_path = folder/ck/"predictions.json"
            audit_path = folder/ck/"audit.json"
            audit = read(audit_path)
            gates = audit["gates"]
            if not all(gates[k] for k in ("wrapper_exact", "restored_native_exact", "weights_unchanged",
                        "parameter_objects_unchanged", "input_unchanged", "no_gradients")) or gates["optimizer_steps"] != 0:
                raise ValueError("Replay correctness gate failed")
            if not gates["archive_replay"]["predictions_exact"] or not gates["archive_replay"]["metrics_match"]:
                raise ValueError("Archived prediction replay gate failed")
            actual_ids = set()
            rows = read(pred_path)
            expected_ids = {ident for (variant, ident), context in contexts.items()
                            if variant == job["variant"] and ident[0] == job["task_id"]
                            and int(context["fold"]) == job["fold"]}
            for row in rows:
                ident = identity(row)
                context = contexts.get((job["variant"], ident))
                if context is None:
                    raise ValueError("Unknown source/node prediction identity")
                validate_prediction(row, job, ck, context)
                if ident in actual_ids:
                    raise ValueError("Duplicate replay prediction")
                actual_ids.add(ident)
                unique = (job["variant"], ck, ident)
                if unique in seen:
                    raise ValueError("Repeated OOF prediction identity")
                seen.add(unique)
                populations[(job["task_id"], job["variant"], ck)].add(ident)
                if sources[row["file"]]["sha256"] != row["source_sha256"]:
                    raise ValueError("Prepared source identity mismatch")
                for condition in CONDITIONS:
                    value = intervention(row, context, condition)
                    prefix = {"task_id": row["task_id"], "cohort": row["cohort"], "variant": row["variant"],
                              "checkpoint": ck, "condition": condition}
                    grouped[tuple(prefix.items())].append(value)
                    filekey = tuple(dict(prefix, file=row["file"], source_sha256=row["source_sha256"],
                                         fold=row["fold"]).items())
                    files[filekey].append(value)
                    important = value["class_changed"] or value["probability_changed"] or row["file"] in HARD[row["cohort"]]
                    if important:
                        changes.append(dict(prefix, file=row["file"], source_sha256=row["source_sha256"],
                            fold=row["fold"], original_graph_node_id=row.get("original_graph_node_id"),
                            node_type=row.get("node_type"), target=row["target"], N_pred=row["N_pred"],
                            masked_pred=row[condition+"_pred"], N_prob=row["N_prob"],
                            masked_prob=row[condition+"_prob"], **value,
                            context_contrast=job["variant"]+"-E2",
                            scope_interpretation="all_variant_enhancements_two_hop_conservative_upper_bound_not_condition_specific",
                            score_role=ROLE, probability_threshold=THRESHOLD,
                            prediction_artifact=str(pred_path), message_audit_artifact=str(audit_path)))
                if any(intervention(row, context, c)["class_changed"] or
                       intervention(row, context, c)["probability_changed"] for c in CONDITIONS):
                    direct = by_target.get((row["task_id"], row["variant"], row["cohort"],
                                row["source_sha256"], row["file"], json.dumps(row.get("original_graph_node_id"))), [])
                    chains.append({"task_id": row["task_id"], "cohort": row["cohort"], "variant": row["variant"],
                        "fold": row["fold"], "checkpoint": ck, "file": row["file"],
                        "source_sha256": row["source_sha256"], "original_graph_node_id": row.get("original_graph_node_id"),
                        "source": sources[row["file"]],
                        "frozen_task_graph": info["graphs"][job["variant"]],
                        "semantic_fact_and_projection_table": str(static_paths["edge_evidence.csv"]),
                        "direct_incoming_added_edges": direct,
                        "function_fallback_table": str(static_paths["function_support.csv"]),
                        "missing_endpoint_table": str(static_paths["projection_missing_anchors.csv"]),
                        "message": {"artifact": str(audit_path), "layers_recorded": ["0", "1"],
                            "conditions_recorded": ["N", "Z_ALL"],
                            "granularity": "canonical destination aggregate Frobenius L2, not per-node causal attribution",
                            "lookup": "messages.N or messages.Z_ALL -> layers -> canonical -> canonical triple"},
                        "prediction_artifact": str(pred_path), "identity_lookup": ident,
                        "topology_scope": {"contrast": job["variant"]+"-E2",
                            "potential_influence_within_two": context.get("potential_influence_within_two"),
                            "new_upstream_count_two": context.get("new_upstream_count_two"),
                            "direct_added_relation_target": context.get("direct_added_relation_target")},
                        "limits": "Second-hop potential is not per-edge attribution; absent direct incoming proof does not mean no two-hop contribution."})
            if actual_ids != expected_ids:
                raise ValueError("Missing or extra validation population")
        completed.append({"task_id": job["task_id"], "fold": job["fold"], "variant": job["variant"],
                          "receipt_sha256": inputs[str(receipt_path)]})
    if len(completed) != 60:
        raise ValueError("Incomplete final models")
    summaries = [dict(key, **summarize_group(rows)) for key, rows in grouped.items()]
    file_summaries = [dict(key, **summarize_group(rows)) for key, rows in files.items()]
    hard = [x for x in file_summaries if x["file"] in HARD[x["cohort"]]]
    coverage_note = REPO/"scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/coverage_note.json"
    static_summary = static_descriptions(static_rows, edge_rows, coverage_note, inputs)
    for path, expected in inputs.items():
        checked(path, expected, {})
    dest.mkdir(parents=True, exist_ok=False)
    for name, rows in (("intervention_context_summary.csv", summaries),
                       ("file_intervention_context.csv", file_summaries),
                       ("hard_file_interventions.csv", hard),
                       ("changed_or_hard_predictions.csv", changes)):
        write_csv(dest/name, rows)
    report = {"version": "stage-i-postprocess-context-v1", "models": 60, "checkpoint_replays": 120,
        "checkpoint_roles": ["best", "last"], "inference_only": True, "training_executed": False,
        "scope": "E3a uses E3a-E2; E3b uses E3b-E2 all-enhancement two-hop scope.",
        "scope_warning": "Z_D/Z_S/Z_C scopes are conservative whole-variant upper bounds, not exact relation-specific attribution.",
        "probability_threshold": THRESHOLD, "score_role": ROLE, "input_sha256": inputs,
        "completed": completed, "descriptive_static": static_summary,
        "node_context_summary": [x for x in summaries if x["task_id"].endswith("_node")],
        "constructor_classification_uses_existing_evidence": True,
        "message_reference_scope": "Canonical aggregate summaries only; no invented per-node message measurements.",
        "script_sha256": sha(__file__),
        "limits": ["No statistical significance or independent test claim.",
                   "Existing labels and historical graph semantics are not adjudicated.",
                   "Message zeroing with unchanged cross-mean does not reproduce E2/E3a architecture or refitting.",
                   "Exact replay gates do not establish full Solidity semantic correctness."]}
    for name, document in (("summary.json", report), ("evidence_chain_references.json", chains),
                           ("STATIC_ERROR_COVERAGE_AND_CONSTRUCTORS.json", static_summary)):
        with (dest/name).open("x", encoding="utf8") as handle:
            json.dump(document, handle, indent=2)
            handle.write("\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default=str(Path(__file__).resolve().parent))
    p.add_argument("--dest")
    args = p.parse_args()
    result = process(args.output, args.dest)
    print(json.dumps({"models": result["models"], "checkpoint_replays": result["checkpoint_replays"],
                      "training_executed": False}))
