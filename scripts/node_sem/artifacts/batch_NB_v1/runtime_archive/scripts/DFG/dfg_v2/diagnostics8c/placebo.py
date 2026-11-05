"""Prompt 8C E: prepare, but never execute, the G0P dilution control.

Approved refinement: only original G0 target types match G3R relation counts;
no env_source node/type is added. Denominator-only describes a single layer
at the same input, not a fixed scaling of final logits after stacked layers.
This module is deliberately not connected to production profiles or trainers.
"""
import argparse
import copy
import csv
import json
import statistics
from pathlib import Path

import dgl
import torch
from ..hgt_layer import HGTLayerSharedProjection
from .structure import (canonical_counts, checked_ref, read_json, sha256,
                        task_manifest, write_json)


PLACEBO_VERSION = "prompt8c-g0p-original-target-empty-v1"
EMPTY_PREFIX = "__G0P_EMPTY_"


def placeholder_canonicals(base_canonicals, target_counts, original_types):
    original_types = set(original_types)
    if not original_types or any(c[0] not in original_types or c[2] not in original_types
                                 for c in base_canonicals):
        raise ValueError("G0 canonical has non-original node type")
    if set(target_counts) != original_types:
        raise ValueError("Target counts must cover exactly the original G0 types")
    base_counts = {t: sum(c[2] == t for c in base_canonicals) for t in original_types}
    additions = []
    for typ in sorted(original_types):
        target = target_counts[typ]
        if type(target) is not int or target < base_counts[typ]:
            raise ValueError("Placebo cannot delete registered G0 relations")
        for index in range(target - base_counts[typ]):
            canonical = (typ, EMPTY_PREFIX + str(index).zfill(3), typ)
            if canonical in base_canonicals:
                raise ValueError("Placeholder canonical collides with G0")
            additions.append(canonical)
    return additions


def make_placebo_data(base_data, target_counts, original_types):
    """Use only empty edges; original endpoints are copied without mutation."""
    additions = placeholder_canonicals(list(base_data), target_counts, original_types)
    result = {c: (s.clone(), t.clone()) for c, (s, t) in base_data.items()}
    for c in additions:
        result[c] = (torch.empty(0, dtype=torch.long), torch.empty(0, dtype=torch.long))
    return result


def copy_common_layer_parameters(base, placebo):
    """Semantic relation row copy; unused extras deterministic, no RNG draws."""
    if base.node_dict != placebo.node_dict:
        raise ValueError("Placebo must preserve node type order")
    if not set(base.edge_dict).issubset(placebo.edge_dict):
        raise ValueError("Placebo removed a G0 relation")
    source, target = base.state_dict(), placebo.state_dict()
    with torch.no_grad():
        for key in target:
            if key in ("relation_att", "relation_msg", "relation_pri"):
                target[key].fill_(1 if key == "relation_pri" else 0)
                for canonical, index in base.edge_dict.items():
                    target[key][placebo.edge_dict[canonical]].copy_(source[key][index])
            else:
                if target[key].shape != source[key].shape:
                    raise ValueError("Shared parameter shape mismatch")
                target[key].copy_(source[key])
        placebo.load_state_dict(target, strict=True)
    for key in source:
        if key in ("relation_att", "relation_msg", "relation_pri"):
            assert all(torch.equal(source[key][idx], placebo.state_dict()[key][placebo.edge_dict[c]])
                       for c, idx in base.edge_dict.items())
        else:
            assert torch.equal(source[key], placebo.state_dict()[key])


def _layer(graph, width=4):
    return HGTLayerSharedProjection(
        width, width, {t: i for i, t in enumerate(graph.ntypes)},
        {c: i for i, c in enumerate(graph.canonical_etypes)},
        n_heads=2, dropout=0.0, use_norm=True)


def numerical_denominator_proof():
    """CPU only, same h/weights, hooks observe exact production a_linear input."""
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(8)
        data = {
            ("statement", "next", "statement"): (torch.tensor([0, 1]), torch.tensor([1, 2])),
            ("declaration", "read", "statement"): (torch.tensor([0]), torch.tensor([1])),
            ("statement", "write", "declaration"): (torch.tensor([1]), torch.tensor([0])),
            ("statement", "already_empty", "declaration"):
                (torch.empty(0, dtype=torch.long), torch.empty(0, dtype=torch.long)),
        }
        numbers = {"statement": 4, "declaration": 2}
        targets = {"statement": 5, "declaration": 4}
        expanded = make_placebo_data(data, targets, numbers)
        base_graph = dgl.heterograph(data, num_nodes_dict=numbers)
        expanded_graph = dgl.heterograph(expanded, num_nodes_dict=numbers)
        base, placebo = _layer(base_graph).eval(), _layer(expanded_graph).eval()
        copy_common_layer_parameters(base, placebo)
        features = {t: torch.randn(count, 4) for t, count in numbers.items()}
        capture = {"G0": {}, "G0P": {}}
        hooks = []
        for label, layer in (("G0", base), ("G0P", placebo)):
            for typ, index in layer.node_dict.items():
                def hook(module, inputs, label=label, typ=typ):
                    capture[label][typ] = inputs[0].detach().clone()
                hooks.append(layer.a_linears[index].register_forward_pre_hook(hook))
        with torch.no_grad():
            baseline = base(base_graph, features)
            actual = placebo(expanded_graph, features)
        for handle in hooks:
            handle.remove()
        records = []
        for typ in sorted(numbers):
            divisor_before = sum(c[2] == typ for c in data)
            divisor_after = targets[typ]
            ratio = float(divisor_before) / divisor_after
            expected_message = capture["G0"][typ] * ratio
            error = (capture["G0P"][typ] - expected_message).abs().max().item()
            idx = base.node_dict[typ]
            alpha = torch.sigmoid(base.skip[idx])
            expected_out = base.norms[idx](
                base.a_linears[idx](expected_message) * alpha + features[typ] * (1 - alpha))
            out_error = (actual[typ] - expected_out).abs().max().item()
            if error > 1e-6 or out_error > 1e-6:
                raise AssertionError("Denominator-only numerical proof failed")
            records.append({"node_type": typ, "before_denominator": divisor_before,
                            "after_denominator": divisor_after, "message_ratio": ratio,
                            "max_abs_message_formula_error": error,
                            "max_abs_layer_output_formula_error": out_error,
                            "max_abs_actual_output_change":
                                (actual[typ] - baseline[typ]).abs().max().item()})
        if sum(x["max_abs_actual_output_change"] for x in records) <= 0:
            raise AssertionError("Probe does not exercise dilution")
    return {"status": "passed", "device": "cpu", "fits_executed": 0,
            "parameter_copy": "Every G0 parameter identical; added empty relation rows zero/priority1",
            "records": records,
            "limitation": "At a fixed layer input, only message mean denominator changes. "
                          "With stacked layers, nonlinear hidden states and attention can then change; "
                          "final logits are not a constant scalar multiple."}


def _estimate_timing(plan_path, node_tasks):
    resource_path = Path(plan_path).parent / "reports/final/fit_resources.csv"
    rows = list(csv.DictReader(resource_path.open(encoding="utf8")))
    result = {}
    for task in node_tasks:
        selected = {profile: [float(r["training_seconds"]) for r in rows
                              if r["task_id"] == task and r["profile"] == profile]
                    for profile in ("G0", "G3R")}
        if any(len(values) != 10 for values in selected.values()):
            raise ValueError("Expected 10 historical node fits per task/profile for timing")
        result[task] = {
            "G0_median_fit_seconds": statistics.median(selected["G0"]),
            "G3R_median_fit_seconds": statistics.median(selected["G3R"]),
            "ten_G0_median_reference_seconds": 10 * statistics.median(selected["G0"]),
            "ten_G3R_median_reference_seconds": 10 * statistics.median(selected["G3R"]),
        }
    return {"source": {"path": str(resource_path), "sha256": sha256(resource_path)},
            "tasks": result,
            "twenty_G0_median_reference_seconds":
                sum(v["ten_G0_median_reference_seconds"] for v in result.values()),
            "twenty_G3R_median_reference_seconds":
                sum(v["ten_G3R_median_reference_seconds"] for v in result.values()),
            "interpretation": "Historical fit durations include validation/save/reload. These are "
                              "reference estimates, not a guarantee or measured G0P throughput; "
                              "controller/full audit overhead is additional."}


def prepare_placebo(plan_path, structure_dir, output_dir):
    output = Path(output_dir)
    output.mkdir(parents=False, exist_ok=False)
    plan, structure = read_json(plan_path), read_json(Path(structure_dir) / "structure.json")
    if structure["plan"]["sha256"] != sha256(plan_path):
        raise ValueError("Structure and training plans differ")
    jobs, schemas = [], {}
    for task_id, entry in plan["tasks"].items():
        if entry["record"]["task"] != "node":
            continue
        details = structure["tasks"][task_id]["profiles"]
        original_types = details["G0"]["node_types"]
        base = [tuple(c) for row in details["G0"]["schema_counts"] for c in row["canonical_relations"]]
        all_target = {row["node_type"]: row["canonical_count"]
                      for row in details["G3R"]["schema_counts"]}
        targets = {t: all_target[t] for t in original_types}
        added = placeholder_canonicals(base, targets, original_types)
        schemas[task_id] = {
            "original_node_types": original_types,
            "base_canonicals": [list(c) for c in sorted(base)],
            "added_empty_canonicals": [list(c) for c in added],
            "target_counts": targets, "additional_relation_count": len(added),
            "omitted_auxiliary_target_types": sorted(set(all_target) - set(original_types)),
            "all_added_edge_counts": 0,
        }
        for fold in entry["folds"]:
            manifest = task_manifest(plan, task_id, fold)
            initial = manifest["profiles"]["G0"]["initial"]
            checked_ref(initial)
            initial_evidence = read_json(checked_ref(manifest["initialization"]))
            proof = initial_evidence["profiles"]["G0"]
            if proof["optimizer_steps"] != 0 or proof["state_sha256"] != initial["state_sha256"]:
                raise ValueError("G0 initial state is not the bound zero-step initialization")
            graph_ref = manifest["profiles"]["G0"]["graph"]
            checked_ref(graph_ref)
            jobs.append({
                "task_id": task_id, "task": "node", "fold": fold, "seed": manifest["seed"],
                "profile": "G0P", "source_profile": "G0",
                "source_prepared": entry["prepared"][str(fold) + "/1"],
                "source_graph": graph_ref, "source_initial": initial,
                "source_initialization_evidence": manifest["initialization"],
                "source_shared_semantic_sha256": proof["shared_semantic_sha256"],
                "optimizer_steps_at_start": 0, "seeds": manifest["seeds"],
                "split": manifest["split"], "effective_config": copy.deepcopy(entry["config"]),
                "execution_authorized": False,
            })
    if len(jobs) != 20 or len({(j["task_id"], j["fold"]) for j in jobs}) != 20:
        raise ValueError("Expected precisely 20 distinct node task/fold jobs")
    proof = numerical_denominator_proof()
    result = {
        "version": PLACEBO_VERSION, "status": "prepared_not_executed",
        "execution_authorized": False, "fits_executed": 0,
        "source_plan": {"path": str(Path(plan_path).resolve()), "sha256": sha256(plan_path)},
        "source_structure": {"path": str((Path(structure_dir) / "structure.json").resolve()),
                             "sha256": sha256(Path(structure_dir) / "structure.json")},
        "approved_refinement": {
            "original_nodes_features_types_unchanged": True,
            "match_G3R_counts_only_on_original_target_types": True,
            "no_env_source_nodes": True,
            "proof_scope": "single-layer identical inputs; no fixed final-logit scaling claim"},
        "initialization_policy": {
            "G0_common_parameters": "Copy exact archived UNTRAINED G0 state by semantic node/canonical identity",
            "inactive_extra_relation_parameters": "Zero attention/message rows and priority1; no RNG draw",
            "fit_rng": "Restore source prepared seeds.fit immediately before training",
            "no_trained_checkpoint_or_smoke_state": True,
            "prospective_executor_required": "No production profile/constructor/trainer is modified by this preparation"},
        "schemas": schemas, "jobs": jobs, "numerical_proof": proof,
        "timing_estimate": _estimate_timing(plan_path, schemas),
        "stop_condition": "A separate explicit user authorization AND executor integration verification "
                          "are required before any of the 20 fits."}
    write_json(output / "plan.json", result)
    digest = sha256(output / "plan.json")
    write_json(output / "plan.seal.json", {"version": PLACEBO_VERSION, "plan_sha256": digest})
    write_json(output / "authorization_template.json", {
        "version": PLACEBO_VERSION, "plan_sha256": digest, "execution_authorized": False,
        "authorized_by": None, "authorization_message": None, "authorized_utc": None,
        "tasks": 20, "scope": "G0P only; 2 frozen node tasks x10 folds; no other training"})
    write_json(output / "denominator_proof.json", proof)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--structure", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = prepare_placebo(args.plan, args.structure, args.output)
    print(json.dumps({"jobs": len(result["jobs"]), "fits_executed": 0,
                      "execution_authorized": False, "timing": result["timing_estimate"]}, indent=2))
