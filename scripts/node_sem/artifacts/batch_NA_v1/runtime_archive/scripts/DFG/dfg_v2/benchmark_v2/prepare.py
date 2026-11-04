"""Prepare the Prompt 8D grouped benchmark; never run a fit.

This module creates an independent plan, seal, grouped splits, loss/score label
views, resource estimates and an authorization template. The existing experiment
CLI has no G0P/feature-view/grouped-protocol execution support: no fake flags are
advertised, and a future verified executor is an explicit prerequisite.
"""
import argparse
import collections
import copy
import csv
import hashlib
import json
import pickle
import re
import statistics
import subprocess
from pathlib import Path

from .grouping import VERSION, build_groups, grouped_folds, digest
from ..diagnostics8c.common import checked_plan

PLAN_VERSION = "prompt8d-benchmark-preparation-v1"
PROFILES = ("G0", "G1R", "G2R", "G3R", "G3")
ROOT = Path(__file__).resolve().parents[4]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def checked(reference):
    if sha(reference["path"]) != reference["sha256"]:
        raise ValueError("Bound input SHA differs: " + reference["path"])
    return Path(reference["path"])


def write(path, value):
    with Path(path).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_duplicate_evidence(directory, old_plan_path):
    directory = Path(directory)
    audit = read(directory / "audit.json")
    if (audit["status"] != "complete"
            or audit["bindings"]["plan"]["sha256"] != sha(old_plan_path)):
        raise ValueError("Duplicate audit belongs to another plan")
    for reference in audit["artifacts"].values():
        checked(reference)
    sources = read(checked(audit["artifacts"]["sources.json"]))
    clusters = read(checked(audit["artifacts"]["clusters.json"]))
    for source in sources:
        if sha(source["path"]) != source["source_sha256"]:
            raise ValueError("Source SHA differs from duplicate audit")
    return sources, build_groups(sources, clusters), audit


def task_population(task_id, entry, sources, groups, node_views):
    record = entry["record"]
    files = record["graph_files"]
    if len(files) != len(set(files)) or set(files) != set(record["sources"]):
        raise ValueError("Invalid original graph population")
    members = [r for r in sources if task_id in r["task_outer_folds"]]
    if len(members) != len(files) or {r["file"] for r in members} != set(files):
        raise ValueError("Duplicate audit task/source population mismatch")
    by_file = {r["file"]: r for r in members}
    group_of = {sid: group["group_id"] for group in groups for sid in group["members"]}
    labels_raw = read(checked(record["labels"]))
    labels = {r["contract_name"]: int(r["targets"]) for r in labels_raw}
    if len(labels) != len(labels_raw) or not set(files).issubset(labels):
        raise ValueError("Missing or duplicated frozen file labels")
    with checked(record["original_graph"]).open("rb") as stream:
        graph = pickle.load(stream)
    node_counts = collections.defaultdict(lambda: [0, 0])
    graph_ids = set()
    for nid, data in graph.nodes(data=True):
        name = data["source_file"]
        if name not in files:
            raise ValueError("Graph contains file absent from task")
        graph_ids.add((name, nid))
        node_counts[name][int(data.get("node_info_vulnerabilities") is not None)] += 1
    audit_counts = collections.defaultdict(lambda: [0, 0, 0])
    label_rows = []
    if record["task"] == "node":
        rows = node_views[task_id]
        if len(rows) != len(graph_ids) or {(r["file"], r["original_graph_node_id"]) for r in rows} != graph_ids:
            raise ValueError("Audit node identities differ from frozen graph")
        for row in rows:
            name, nid = row["file"], row["original_graph_node_id"]
            src = by_file[name]
            if row["orig"] not in (0, 1) or row["C1"] not in (0, 1) or type(row["C2_include"]) is not bool:
                raise ValueError("Audit targets must be binary and inclusion must be boolean")
            original = int(graph.nodes[nid].get("node_info_vulnerabilities") is not None)
            if (row["source_sha256"] != src["source_sha256"] or original != row["orig"]
                    or row["node_type"] != graph.nodes[nid]["node_type"]):
                raise ValueError("Audit node target/type/source mismatch")
            if row["C2_include"]:
                audit_counts[name][int(row["C1"])] += 1
            else:
                audit_counts[name][2] += 1
            label_rows.append({
                "file": name, "source_id": src["source_id"], "source_sha256": src["source_sha256"],
                "original_graph_node_id": nid, "node_type": row["node_type"],
                "orig": original, "L-orig_target": original, "L-orig_include": True,
                "L-audit_target": int(row["C1"]), "L-audit_include": bool(row["C2_include"]),
                "exclusion_reasons": list(row["exclusion_reasons"]),
                "solidifi": bool(row["solidifi"]),
            })
    else:
        for name in sorted(files):
            src = by_file[name]
            label_rows.append({"file": name, "source_id": src["source_id"],
                               "source_sha256": src["source_sha256"], "orig": labels[name],
                               "L-orig_target": labels[name], "L-audit_target": labels[name],
                               "L-orig_include": True, "L-audit_include": True})
    population = []
    for name in sorted(files):
        src = by_file[name]
        if src["source_sha256"] != record["sources"][name]["sha256"]:
            raise ValueError("Task source differs from duplicate evidence")
        population.append({
            "file": name, "source_id": src["source_id"], "source_sha256": src["source_sha256"],
            "source_cohort": src["cohort"], "category": src["category"],
            "cohort": "SolidiFI" if re.fullmatch(r"buggy_\d+\.sol", name) else "nonSolidiFI",
            "group_id": group_of[src["source_id"]], "file_label": labels[name],
            "node_positive": node_counts[name][1], "node_negative": node_counts[name][0],
            "audit_node_positive": audit_counts[name][1],
            "audit_node_negative": audit_counts[name][0], "audit_masked_nodes": audit_counts[name][2],
        })
    conflicts = []
    for gid in sorted({r["group_id"] for r in population}):
        rows = [r for r in population if r["group_id"] == gid]
        if len({r["file_label"] for r in rows}) > 1:
            conflicts.append({"group_id": gid, "members": rows})
    return population, label_rows, conflicts


def make_jobs(tasks, seeds):
    if not seeds or len(seeds) != len(set(seeds)) or any(type(s) is not int or s < 1 for s in seeds):
        raise ValueError("Distinct positive integer seeds required")
    jobs = []
    for tid, task in tasks.items():
        allowed = PROFILES + (("G0P",) if task["granularity"] == "node" else ())
        for fold in range(task["k_folds"]):
            for seed in seeds:
                constructor = 10000 + fold + (1000 if task["granularity"] == "contract" else 0) + 100000*(seed-1)
                for profile in allowed:
                    jobs.append({"task_id": tid, "fold": fold, "seed": seed, "profile": profile,
                                 "constructor_seed": constructor, "fit_seed": constructor + 1000000,
                                 "execution_authorized": False})
    expected = sum(t["k_folds"] * (6 if t["granularity"] == "node" else 5) for t in tasks.values()) * len(seeds)
    if len(jobs) != expected or len({(j["task_id"], j["fold"], j["seed"], j["profile"]) for j in jobs}) != len(jobs):
        raise AssertionError("Incorrect benchmark execution matrix")
    return jobs


def timing_estimate(old_plan_path, jobs):
    path = Path(old_plan_path).parent / "reports/final/fit_resources.csv"
    with path.open(encoding="utf8") as stream:
        rows = list(csv.DictReader(stream))
    by_key = collections.defaultdict(list)
    for row in rows:
        by_key[(row["task_id"], row["profile"])].append(float(row["training_seconds"]))
    estimates = []
    for job in jobs:
        profile = "G0" if job["profile"] == "G0P" else job["profile"]
        values = by_key[(job["task_id"], profile)]
        if not values or any(v <= 0 for v in values):
            raise ValueError("Missing historical fit timing")
        estimates.append({"task_id": job["task_id"], "fold": job["fold"], "profile": job["profile"],
                          "seed": job["seed"], "reference_median_seconds": statistics.median(values),
                          "reference_profile": profile})
    total = sum(r["reference_median_seconds"] for r in estimates)
    return {
        "source": ref(path), "jobs": estimates, "local_reference_total_seconds": total,
        "local_reference_total_hours": total / 3600.0,
        "interpretation": "Historical local median per task/profile, summed; new grouped splits and name-neutral features can change early stopping. Controller overhead is additional.",
        "server_measured": False, "server_gpu": None,
        "server_estimate": "Unknown until server specification and one authorized fit measurement; sufficient VRAM does not specify throughput.",
        "server_conditional_scenarios": [
            {"assumed_speedup_vs_local": factor, "conditional_hours": total / 3600.0 / factor}
            for factor in (1, 2, 4)],
        "local_and_server_results_may_be_mixed": False,
    }


def verify_prepared(plan_path):
    plan_path = Path(plan_path)
    seal = read(plan_path.with_name("plan.seal.json"))
    if seal["plan_sha256"] != sha(plan_path):
        raise ValueError("Preparation plan seal mismatch")
    plan = read(plan_path)
    if plan["execution_authorized"] is not False or plan["training_executed"] != 0:
        raise ValueError("Preparation cannot authorize execution")
    def verify_refs(value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                checked(value)
            for nested in value.values():
                verify_refs(nested)
        elif isinstance(value, list):
            for nested in value:
                verify_refs(nested)
    verify_refs(plan)
    if len(plan["jobs"]) != plan["fit_count"]:
        raise ValueError("Job count mismatch")
    expected = make_jobs(plan["tasks"], plan.get("proposed_training_seeds", [1]))
    if plan["jobs"] != expected:
        raise ValueError("Job identity/profile/order matrix differs")
    if any(j["execution_authorized"] is not False for j in plan["jobs"]):
        raise ValueError("A preparation job cannot be authorized")
    for tid, task in plan["tasks"].items():
        checked(task["folds"])
        checked(task["population"])
        from .grouping import validate_splits
        validate_splits(read(task["folds"]["path"]), read(task["population"]["path"]))
    return {"passed": True, "fit_count": plan["fit_count"], "training_executed": 0,
            "execution_authorized": False}


def prepare_benchmark(old_plan_path, duplicate_dir, node_views_path, feature_manifest_path,
                      feature_equivalence_path, output_dir, split_seed=1, keyword_baselines_path=None):
    output = Path(output_dir)
    if not output.is_dir():
        output.mkdir(parents=False, exist_ok=False)
    # F/features can already exist; every output written here is exclusive.
    for name in ("plan.json", "plan.seal.json", "authorization_template.json", "folds",
                 "populations", "groups.json", "label_views.json", "timing.json", "verification.json"):
        if (output / name).exists():
            raise FileExistsError("Refusing to overwrite preparation artifact: " + name)
    old = checked_plan(old_plan_path)
    sources, groups, duplicate_audit = load_duplicate_evidence(duplicate_dir, old_plan_path)
    audit_path = Path(node_views_path).parent / "audit.json"
    label_audit = read(audit_path)
    if (checked(label_audit["node_views"]).resolve() != Path(node_views_path).resolve()
            or label_audit["provenance"]["plan"]["sha256"] != sha(old_plan_path)):
        raise ValueError("Node views differ from frozen 8C label audit")
    views = read(node_views_path)
    features = read(feature_manifest_path)
    equality = read(feature_equivalence_path)
    if (not features.get("orig_inputs_unchanged")
            or set(features["task_views"]) != set(old["tasks"])
            or not equality.get("passed")
            or any(equality.get(k) is not True for k in
                   ("forward_bitwise", "epoch_loss_bitwise", "state_digest_equal",
                    "optimizer_state_equal", "scheduler_state_equal"))):
        raise ValueError("Feature view/equality preparation gate failed")
    for task_feature in features["task_views"].values():
        checked(task_feature["manifest"])
        checked(task_feature["data"])
    stats_ref = old["batch_registration"]["report_spec"]
    stats = read(checked(stats_ref))["statistics"]
    placebo_path = Path(duplicate_dir).parent / "E/plan.json"
    placebo = checked_plan(placebo_path)
    if placebo["execution_authorized"] is not False or placebo["fits_executed"] != 0:
        raise ValueError("Expected frozen unexecuted placebo preparation")
    (output / "folds").mkdir()
    (output / "populations").mkdir()
    task_records, label_records = {}, {}
    for tid, entry in old["tasks"].items():
        rows, labels, conflicts = task_population(tid, entry, sources, groups, views)
        granularity = entry["record"]["task"]
        k = 5 if granularity == "contract" else 10
        splits = grouped_folds(tid, rows, k, seed=split_seed, inner_fraction=.2)
        write(output / "folds" / (tid + ".json"), splits)
        write(output / "populations" / (tid + ".json"), rows)
        config = copy.deepcopy(entry["config"])
        config.update(protocol="dfg-v2-grouped-nested", protocol_version=VERSION,
                      partition_policy="group_disjoint_nested_file_supervision",
                      score_role="outer_test", selection_role="inner_val")
        profile_manifest = read(checked(entry["prepared"]["0/1"]))
        task_records[tid] = {
            "granularity": granularity, "category": entry["record"]["category"], "k_folds": k,
            "files": len(rows), "groups": len({r["group_id"] for r in rows}),
            "population": ref(output / "populations" / (tid + ".json")),
            "folds": ref(output / "folds" / (tid + ".json")),
            "original_record": entry["record"], "effective_config": config,
            "feature_view": features["task_views"][tid],
            "profiles": {profile: {"graph": detail["graph"], "schema": detail["support"]["schema"],
                                    "parameter_count": detail["parameter_count"]}
                         for profile, detail in profile_manifest["profiles"].items()},
            "mixed_file_label_groups": conflicts,
            "new_partition_support_audit_required_before_execution": True,
        }
        label_records[tid] = labels
    jobs = make_jobs(task_records, [1])
    if len(jobs) != 170:
        raise ValueError("Expected 170 preparation tasks for current four-task seed1 matrix")
    write(output / "groups.json", {"groups": groups, "source_identities": sources,
                                  "config": duplicate_audit["config"]})
    write(output / "label_views.json", label_records)
    timing = timing_estimate(old_plan_path, jobs)
    write(output / "timing.json", timing)
    bound = {
        "historical_plan": ref(old_plan_path), "historical_seal": ref(Path(old_plan_path).with_name("plan.seal.json")),
        "duplicate_audit": ref(Path(duplicate_dir)/"audit.json"),
        "duplicate_sources": ref(Path(duplicate_dir)/"sources.json"),
        "duplicate_clusters": ref(Path(duplicate_dir)/"clusters.json"),
        "node_diagnostic_views": ref(node_views_path), "node_label_audit": ref(audit_path),
        "feature_views": ref(feature_manifest_path),
        "feature_equivalence": ref(feature_equivalence_path), "groups": ref(output/"groups.json"),
        "label_views": ref(output/"label_views.json"), "timing": ref(output/"timing.json"),
        "historical_report_spec": stats_ref, "historical_placebo_preparation": ref(placebo_path),
    }
    if keyword_baselines_path is not None:
        bound["keyword_baselines"] = ref(keyword_baselines_path)
    result = {
        "version": PLAN_VERSION, "protocol": "dfg-v2-grouped-nested",
        "protocol_version": VERSION, "status": "prepared_requires_label_seed_location_choice_and_executor_gate",
        "execution_authorized": False, "training_executed": 0, "fit_count": len(jobs),
        "split_seed": split_seed, "proposed_training_seeds": [1], "selected_training_seeds": None,
        "label_policy_default": "L-audit", "selected_label_policy": None, "selected_execution_location": None,
        "bound_artifacts": bound, "tasks": task_records, "jobs": jobs,
        "git_head_at_preparation": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT)).decode().strip(),
        "initialization": {
            "version": old["initialization_version"], "seed_rule": old["seed_rule"],
            "fresh_untrained_states_required": True, "trained_state_reuse_forbidden": True,
            "paired_shared_G0_parameters": "exact semantic node/canonical alignment",
            "new_common_relation_rows": "semantic random seed, own-profile Xavier bank scale as approved in Prompt7",
            "G0P": "Copy fresh same-fold G0 common parameters; empty relation attention/message zero, priority one.",
            "state_materialization": "after authorization; bind zero optimizer steps and tensor/file SHA before fit",
        },
        "label_policies": {
            "L-orig": "Original author node/file labels; every original supervised unit included.",
            "L-audit": "Node target=C1; C2_include is loss/metric mask, never delete a graph node or flip an excluded label. Contract/file labels unchanged.",
            "always_report": "Original-label score over ALL original outer-test supervised units, even L-audit-masked nodes.",
            "interpretation": "C1 plus C2 mask is a diagnostic annotation policy, not established vulnerability ground truth.",
        },
        "scoring": {"selection_role": "inner_val", "score_role": "outer_test",
                    "best": "strict minimum inner validation loss", "last": "auxiliary, separate",
                    "node_unit": "original HCG node", "grouped_not_independent_external_test": True,
                    "forward_scope": "full_fixed_task_graph", "forward_is_transductive": True,
                    "source_layers": ["SolidiFI", "nonSolidiFI"],
                    "keyword_baseline_comparison_required": True,
                    "keyword_baseline_task_scope": "node tasks; E defines node/function keyword predictions",
                    "contract_keyword_baseline": "not defined by E; no invented file aggregation"},
        "statistics": stats,
        "statistical_label_scope": {
            "primary": "User-selected label policy; unchanged four-profile Holm family",
            "auxiliary_orig": "Separate original-label reference; never combine its p-values with primary diagnostic labels",
            "statistics_computed_in_this_preparation": False},
        "selection_rule": copy.deepcopy(old["selection_rule"]),
        "automatic_additional_seed_training": False,
        "preparation_code": [ref(Path(__file__)), ref(Path(__file__).with_name("grouping.py"))],
        "G0P": {"schemas": placebo["schemas"], "numerical_proof": placebo["numerical_proof"],
                "comparison": "G0P-G0 separately for node tasks; excluded from old four-comparison Holm family",
                "uses_new_grouped_folds": True, "reuse_old_G0P_jobs": False},
        "execution_gate": {
            "user_choices_required": ["label_policy", "training_seeds", "execution_location"],
            "seed_or_location_changes_require_new_execution_plan": True,
            "runtime_and_environment_binding_required": True, "new_initials_required": True,
            "keyword_baseline_binding_pending": keyword_baselines_path is None,
            "new_split_support_and_checkpoint_bindings_required": True,
            "existing_cli_supports_this_plan": False,
            "executor_integration_required": "Reuse existing fit loop via explicit feature/label/split bindings; test G0P empty schema and loss mask before running.",
            "serial_single_model": True, "automatic_retries": False, "on_oom": "retain failed attempt and stop",
            "local_server_mixing_forbidden": True,
        },
        "limitations": [
            "Frozen textual clone detector may miss semantic/renamed clones; grouping reduces known cross-fold duplication, not all leakage.",
            "Inner and outer groups are disjoint, but full-graph inputs remain transductive.",
            "No result selection based on new outer-test scores or seed search.",
            "Final experiments are intended for a sufficient-VRAM server; current RTX3050 restriction is local.",
        ],
    }
    write(output/"plan.json", result)
    write(output/"plan.seal.json", {"version": PLAN_VERSION, "plan_sha256": sha(output/"plan.json")})
    write(output/"authorization_template.json", {
        "version": PLAN_VERSION, "plan": ref(output/"plan.json"), "execution_authorized": False,
        "label_policy": None, "label_policy_default": "L-audit", "training_seeds": None,
        "training_seeds_default": [1], "execution_location": None,
        "allowed_locations": ["local", "server"], "authorized_by": None,
        "authorization_message": None, "estimated_default_fit_count": 170,
        "do_not_edit_historical_plan": True,
        "instruction": "User choices are required; materialize a separate sealed executable plan after executor validation. This template is not permission to fit.",
    })
    verification = verify_prepared(output/"plan.json")
    write(output/"verification.json", verification)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old-plan", "duplicates", "node-views", "feature-manifest", "feature-equivalence", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--keyword-baselines", type=Path)
    args = parser.parse_args()
    result = prepare_benchmark(args.old_plan, args.duplicates, args.node_views,
                               args.feature_manifest, args.feature_equivalence, args.output,
                               keyword_baselines_path=args.keyword_baselines)
    print(json.dumps({"fit_count": result["fit_count"], "execution_authorized": False,
                      "training_executed": 0}, indent=2))


if __name__ == "__main__":
    main()
