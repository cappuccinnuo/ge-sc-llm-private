"""Read-only final CP3 merge: one result per eligible input, exact replacement map."""
import collections, hashlib, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from compile_repair.evaluation.report import aggregate_failures
from compile_repair.toolchain.project import import_directives
from compile_repair.toolchain.solc import _diagnostic_offset
B = Path(__file__).resolve().parent
OLD = B.with_name("cp3_continue_v1")
LOCAL = Path("/home/zhao/SmartContract/compile-repair-local/cp3_paths_v1")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()

def read_rows(path):
    with path.open() as f:
        return [json.loads(line) for line in f]

def put(name, value):
    with (B / name).open("x") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")


def enrich_single_imports(classification, data, item):
    """Recover import identities from already-observed, located CLI failures."""
    if item["project_root"]:
        return
    for failure in classification["failures"]:
        if failure["category"] not in ("unresolved_package_import", "missing_relative_file"):
            continue
        candidates = [a["solc"] for a in data["attempts"] if a.get("solc")
                      and a.get("version") == failure.get("version")
                      and a["solc"]["returncode"] != 0]
        if not candidates:
            failure["import_statistics_note"] = "no matching saved invocation"
            continue
        compiled = candidates[0]
        source = Path(compiled["source_path"])
        assert sha(source) == compiled["source_sha256"]
        raw = source.read_bytes()
        offset = _diagnostic_offset(failure, raw)
        imports = [d for d in import_directives(raw)
                   if offset is not None and d["start"] <= offset < d["end"]]
        if len(imports) != 1 or not imports[0]["supported_literal"]:
            failure["import_statistics_note"] = "import location not uniquely recoverable"
            continue
        directive = imports[0]
        failure.update(path=directive["path"], start=directive["start"],
                       source_path=data["inputs"][0]["path"],
                       import_statistics_note="derived from saved source and CLI location; no rerun")
        if failure["category"] == "unresolved_package_import":
            parts = directive["path"].split("/")
            failure["package"] = "/".join(parts[:2]) if parts[0].startswith("@") else parts[0]


def main():
    start = time.monotonic()
    inventory = read_rows(OLD / "unit_inventory.jsonl")
    eligible = {r["unit_id"]: r for r in inventory if r["language_evidence"]["is_solidity"]}
    excluded = [r for r in inventory if not r["language_evidence"]["is_solidity"]]
    previous_path = B.with_name("cp3_binding_v1") / "result_provenance.json"
    previous_provenance = json.loads(previous_path.read_text())
    approved = set(json.loads((B / "authorization.json").read_text())["revalidation_unit_ids"])
    assert len(approved) == 103
    recovery = json.loads((B / "driver_comparison_recovery.json").read_text())
    assert recovery["accepted"] and recovery["repeated_compiler_or_slither_calls"] == 0
    first = LOCAL / "revalidate_103"
    continuation = LOCAL / "continue_remaining_102"
    completion = json.loads((continuation / "summary.json").read_text())
    assert completion["status"] == "complete_segment" and completion["completed_units"] == 102
    run_inventory = []
    for run in [first, continuation]:
        seal = json.loads((run / "seal.json").read_text())
        for rel, digest in seal["files"].items():
            assert sha(run / rel) == digest, str(run / rel)
        for rel, digest in seal["implementation_sha256"].items():
            assert sha(ROOT / rel) == digest, "Implementation changed: " + rel
        run_inventory.append({"path": str(run), "seal_sha256": sha(run / "seal.json"),
                              "verified_members": len(seal["files"]),
                              "implementation_sha256": seal["implementation_sha256"]})
    selected, provenance, class_cache, class_verifications = {}, {}, {}, []
    for uid, ref in previous_provenance["rows"].items():
        path = Path(ref["result_path"])
        assert sha(path) == ref["result_sha256"], uid
        run = path.parents[2]
        if str(run) not in class_cache:
            seal = json.loads((run / "seal.json").read_text())
            class_path = run / "classifications.jsonl"
            assert sha(class_path) == seal["files"]["classifications.jsonl"]
            class_cache[str(run)] = {r["unit_id"]: r for r in read_rows(class_path)}
            class_verifications.append({"path": str(class_path), "sha256": sha(class_path),
                                        "run_seal_sha256": sha(run / "seal.json")})
        selected[uid] = class_cache[str(run)][uid]
        provenance[uid] = dict(ref)
    replacement_rows = [json.loads((B / "recovered_first_classification.json").read_text())]
    replacement_rows += read_rows(continuation / "classifications.jsonl")
    assert len(replacement_rows) == 103 and {r["unit_id"] for r in replacement_rows} == approved
    replacements = []
    old_calls = collections.Counter()
    for row in replacement_rows:
        uid = row["unit_id"]
        old_ref = provenance[uid]
        old_data = json.loads(Path(old_ref["result_path"]).read_text())
        new_run = first if uid == recovery["unit_id"] else continuation
        new_path = new_run / "units" / uid / "result.json"
        new_data = json.loads(new_path.read_text())
        assert new_data["inputs"] == old_data["inputs"] and new_data["plan"] == old_data["plan"]
        if old_data["status"] == "success":
            assert new_data["status"] == "success", uid
        old_calls["solc"] += selected[uid]["compiler_calls"]
        old_calls["slither"] += selected[uid]["slither_calls"]
        replacements.append({"unit_id": uid, "old": old_ref,
            "new": {"result_path": str(new_path), "result_sha256": sha(new_path)},
            "old_status": old_data["status"], "new_status": new_data["status"],
            "old_selected_version": old_data["selected_version"],
            "new_selected_version": new_data["selected_version"],
            "inputs_equal": True, "serialized_plans_equal": True})
        selected[uid] = row
        provenance[uid] = {"kind": "approved_path_revalidation", "result_path": str(new_path),
                          "result_sha256": sha(new_path), "replaces": old_ref}
    assert set(selected) == set(eligible)
    assert len(selected) == 31071 and len(excluded) == 236
    assert sum(ref["kind"] == "approved_path_revalidation" for ref in provenance.values()) == 103
    replacement_totals = {"units": len(replacements),
        "old_status": dict(collections.Counter(r["old_status"] for r in replacements)),
        "new_status": dict(collections.Counter(r["new_status"] for r in replacements)),
        "status_transitions": dict(collections.Counter(r["old_status"] + "->" + r["new_status"] for r in replacements)),
        "prior_success_selected_version_changed": sum(r["old_status"] == "success" and r["old_selected_version"] != r["new_selected_version"] for r in replacements),
        "old_calls_replaced": dict(old_calls),
        "new_calls": {"solc": sum(r["compiler_calls"] for r in replacement_rows),
                      "slither": sum(r["slither_calls"] for r in replacement_rows)},
        "repeat_executions_of_first_unit": 0,
        "rows": replacements}
    put("replacement_summary.json", replacement_totals)
    rows = [selected[uid] for uid in sorted(selected)]
    taxonomy = json.loads((OLD / "taxonomy_verified.json").read_text())

    facts = collections.Counter()
    by_corpus = collections.defaultdict(collections.Counter)
    slither_subtypes = collections.Counter()
    binding_reasons = collections.Counter()
    other_units = collections.defaultdict(set)
    other_examples = collections.defaultdict(set)
    timings = []
    plan_flags = collections.Counter()
    lower_bound_examples = []
    for uid, classification in selected.items():
        item = eligible[uid]
        assert classification["entry_sha256"] == item["entry_sha256"]
        assert sha(Path(item["path"])) == item["entry_sha256"]
        data = json.loads(Path(provenance[uid]["result_path"]).read_text())
        assert data["unit_id"] == uid
        enrich_single_imports(classification, data, item)
        for source in data["inputs"]:
            assert sha(Path(source["path"])) == source["sha256"]
        plan_data = data.get("plan") or {}
        plan_flags.update(plan_data.get("flags", []))
        interval = plan_data.get("interval")
        if interval and len(interval) == 2:
            lo, hi = [tuple(v) for v in interval]
            if lo <= (0, 4, 11) < hi and not lo <= (0, 4, 12) < hi:
                lower_bound_examples.append({"unit_id": uid, "entry_sha256": item["entry_sha256"],
                    "corpus": item["corpus"], "interval": interval, "status": data["status"],
                    "selected_version": data["selected_version"], "override": plan_data.get("override")})
        any_d3 = False
        for attempt in data["attempts"]:
            assert "File outside of allowed directories" not in (attempt.get("solc") or {}).get("stderr", ""), uid
            analysis = attempt.get("slither")
            if not analysis:
                continue
            facts["slither_calls"] += 1
            timings.append(analysis["elapsed_seconds"])
            any_d3 = any_d3 or analysis["d3"]
            if "project_binding" in analysis:
                facts["project_slither_calls"] += 1
                check = analysis["project_binding"]
                facts["direct_contract_bindings_examined"] += check.get("checked", 0)
                facts["project_calls_without_direct_contract_variables"] += check.get("complete", False) and check.get("checked") == 0
                if not check["complete"]:
                    facts["project_binding_rejected_calls"] += 1
                    if analysis["d3"]:
                        facts["d3_true_but_binding_rejected_calls"] += 1
                    binding_reasons[check.get("reason", "per_variable_diagnostics")] += 1
                    for binding in check.get("bindings", []):
                        if not binding["complete"]:
                            binding_reasons[binding["reason"]] += 1
        facts["units_with_any_d3"] += any_d3
        facts["old_parse_failed_new_read_succeeded"] += classification["old_parse_failed_new_read_succeeded"]
        facts["compiler_calls"] += classification["compiler_calls"]
        facts["slither_side_failure_units"] += classification["reason"] == "slither_side_failure"
        labels = {f["category"] for f in classification["failures"]}
        facts["unsupported_disjunction_units"] += "unsupported_disjunction" in labels
        for key in ["old_parse_failed_new_read_succeeded", "old_parse_failed", "new_interval_read"]:
            by_corpus[classification["corpus"]][key] += bool(classification[key])
        if data["status"] == "success" and item["project_root"]:
            assert any((a.get("slither") or {}).get("graph_usable") for a in data["attempts"])
        seen_subtypes = set()
        for failure in classification["failures"]:
            if failure["category"] == "slither_incomplete":
                seen_subtypes.add(failure["subtype"])
            if failure["category"] == "other":
                template = failure.get("template") or failure.get("error_template") or failure.get("reason") or "<absent>"
                other_units[template].add(uid)
                other_examples[template].add(classification["entry_sha256"])
        slither_subtypes.update(seen_subtypes)
    physical_imports = {}
    for row in rows:
        item = eligible[row["unit_id"]]
        for failure in row["failures"]:
            if failure.get("path") and failure.get("source_path") and failure.get("start") is not None:
                key = (item.get("project_root"), failure["source_path"], failure["start"], failure["path"])
                physical_imports.setdefault(key, failure)
    physical_packages = collections.Counter()
    physical_paths = collections.Counter()
    physical_candidates = collections.Counter()
    for failure in physical_imports.values():
        if failure.get("package"):
            physical_packages[failure["package"]] += 1
            physical_paths[failure["path"]] += 1
        if failure.get("candidate_kind"):
            physical_candidates[failure["candidate_kind"]] += 1
    summary = aggregate_failures(rows, [r["category"] for r in taxonomy["categories"]])
    for category in summary["category_unit_counts"]:
        matching = [row for row in rows if any(
            failure["category"] == category["category"] for failure in row["failures"])]
        matching.sort(key=lambda row: (row["entry_sha256"], row["unit_id"]))
        category["unit_examples"] = [
            {"unit_id": row["unit_id"], "corpus": row["corpus"],
             "entry_sha256": row["entry_sha256"],
             "result_sha256": provenance[row["unit_id"]]["result_sha256"],
             "result_path": provenance[row["unit_id"]]["result_path"]}
            for row in matching[:3]]
    facts["eligible_units"] = len(rows)
    facts["excluded_non_solidity"] = len(excluded)
    summary.update(status="complete",
                   binding_rejection_count_basis="All calls lacking binding certification, including Slither-not-constructed. d3_true_but_binding_rejected_calls measures the added gate's effect; checked counts only inspected AST variable bindings.",
                   distinct_source_import_statistics={
                       "basis":"unique project-root/source-position/import-path across overlapping entry closures; single-file paths recovered from saved located diagnostics",
                       "unresolved_packages":dict(physical_packages),
                       "unresolved_import_paths":dict(physical_paths),
                       "relative_basename_candidates":dict(physical_candidates)}, environment_plan_flags=dict(plan_flags),
                   d19_intervals_allowing_0411_but_not_0412=lower_bound_examples, population_sampling="none", measurement_facts=dict(facts),
                   old_new_parser_by_corpus={k:dict(v) for k,v in by_corpus.items()},
                   slither_subtype_unit_counts=dict(slither_subtypes), binding_rejection_reasons=dict(binding_reasons),
                   slither_timeout_protection=False,
                   slither_timeout_observation="All selected calls completed; no enforced Slither timeout. This does not prove absence of future hangs.",
                   maximum_completed_slither_seconds=max(timings, default=0),
                   other_template_unit_counts=[dict(template=k, units=len(v), example_sha256=sorted(other_examples[k])[:3])
                                              for k,v in sorted(other_units.items())],
                   import_statistics_enrichment="Single-file import path/package inferred only from the existing located CLI failure and hash-verified saved working source. Project imports use original assembly evidence; raw records unchanged.",
                   missing_import_identity_records=sum(bool(f.get("import_statistics_note")) and not f.get("path") for r in rows for f in r["failures"]),
                   inputs_sha256=sha(OLD / "unit_inventory.jsonl"),
                   provenance_policy="Each eligible input counted once. Exactly 103 approved path-affected observations replaced; 30968 previous observations preserved with their original implementation provenance.",
                   extra_revalidation_calls_excluded_from_effective_counts={"solc":335 + old_calls["solc"], "slither":230 + old_calls["slither"]},
                   path_revalidation_replaced_calls=dict(old_calls),
                   interrupted_prior_solc_calls_excluded=9, cost_usd=0)
    put("failure_summary.json", summary)
    draft_path = B.with_name("cp3_binding_v1") / "d6_cp4_conclusions.json"
    conclusions = json.loads(draft_path.read_text())
    conclusions["status"] = "complete_cp3_routes_and_cp4_operator_inventory"
    conclusions["draft_sha256"] = sha(draft_path)
    conclusions["frequency_summary_sha256"] = sha(B / "failure_summary.json")
    frequencies = {row["category"]: row for row in summary["category_unit_counts"]}
    assert set(frequencies) == {row["category"] for row in conclusions["categories"]}
    for category in conclusions["categories"]:
        category["observed_units"] = frequencies[category["category"]]["units"]
        category["fraction_remaining_failures"] = frequencies[category["category"]]["fraction_remaining_failures"]
    conclusions["implementation_priority_by_frequency_only"] = [
        row["category"] for row in sorted(summary["category_unit_counts"],
                                          key=lambda row: (-row["units"], row["category"]))]
    conclusions["zero_frequency_categories_retained"] = [
        row["category"] for row in summary["category_unit_counts"] if not row["units"]]
    put("d6_cp4_final.json", conclusions)

    put("result_provenance.json", {"unit_count":len(provenance), "rows":provenance,
                                 "previous_provenance_path":str(previous_path), "previous_provenance_sha256":sha(previous_path),
                                 "replaced_units":103, "preserved_units":30968,
                                 "reused_classification_file_verifications":class_verifications,
                                 "run_inventory":run_inventory, "elapsed_seconds":time.monotonic()-start})
    print(json.dumps({k:summary[k] for k in ["status","total","success","remaining_failures","measurement_facts"]}))


if __name__ == "__main__":
    main()
