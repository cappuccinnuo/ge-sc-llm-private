"""CP3 observed-failure aggregation; policy stays in the common pipeline."""
from collections import Counter, defaultdict
from pathlib import Path

from compile_repair.toolchain.solc import (
    classify_constraints, classify_diagnostic, classify_slither, parse_diagnostics)


def classify_record(record):
    """Return every observed failure label; per-category unit counts deduplicate.

    An unrepaired unit can have several compiler diagnostics/failed versions.
    A unit accepted by all applicable gates contributes no failure labels.
    Raw source is read only to interpret located messages, never emitted here.
    """
    if record["status"] == "success":
        return []
    originals = [Path(s["path"]).read_bytes() for s in record["inputs"]]
    rows = []
    for attempt in record["attempts"]:
        if attempt["stage"] == "input_format":
            category = "non_solidity_input" if record["reason"] == "non_solidity_input" else "standard_json_input"
            rows.append(dict(attempt, category=category))
            continue
        if attempt["stage"] == "project_assembly":
            rows.extend(dict(issue, stage="project_assembly") for issue in attempt["issues"])
            continue
        if attempt["stage"] == "environment_plan":
            rows.append(dict(classify_constraints(attempt["error_first_line"], originals),
                             stage="environment_plan"))
            continue
        compiled = attempt.get("solc")
        if not compiled:
            continue
        version = attempt["version"]
        if compiled["timed_out"]:
            rows.append({"category": "other", "subtype": "solc_timeout", "stage": "solc", "version": version,
                         "template": "solc invocation timeout"})
        elif compiled["returncode"] != 0:
            for diagnostic in parse_diagnostics(compiled["stderr"]):
                path = diagnostic["filename"]
                source = b""
                if path:
                    target = (Path(compiled["cwd"]) / path).resolve()
                    # Only already-recorded working inputs may supply evidence.
                    if len(record["inputs"]) == 1 and target == Path(compiled["source_path"]).resolve():
                        source = target.read_bytes()
                    elif Path(compiled["cwd"]).resolve() in target.parents:
                        source = target.read_bytes() if target.is_file() else b""
                elif len(record["inputs"]) == 1:
                    source = Path(compiled["source_path"]).read_bytes()
                row = classify_diagnostic(diagnostic, source)
                if row["failure"]:
                    rows.append(dict(row, version=version, stage="solc"))
        elif attempt.get("slither"):
            analysis = attempt["slither"]
            if analysis.get("graph_unusable_reason") == "duplicate_contract_names":
                rows.append({"category": "slither_incomplete", "subtype": "duplicate_contract_names",
                             "stage": "slither", "version": version, "repair_route": "tool_limitation"})
            if not analysis.get("project_binding", {"complete": True})["complete"]:
                rows.append({"category": "slither_incomplete", "stage": "slither",
                             "subtype": "project_binding_rejected", "version": version,
                             "repair_route": "tool_limitation",
                             "binding_evidence": analysis["project_binding"]})
            if not analysis["d3"]:
                rows.append(dict(classify_slither(analysis, originals),
                                 stage="slither", version=version))
    if not rows:
        rows.append({"category": "other", "template": record["reason"] or "no classified diagnostic"})
    return rows


def primary_causes(record, failures=None):
    """Attribute an unrepaired unit to the earliest blocking stage or common diagnostics."""
    if record["status"] == "success":
        return {"categories": [], "by_version": {}}
    failures = classify_record(record) if failures is None else failures
    for stage in ("input_format", "environment_plan", "project_assembly"):
        labels = sorted({row["category"] for row in failures if row.get("stage") == stage})
        if labels:
            return {"categories": labels, "by_version": {}}
    attempts = [attempt for attempt in record["attempts"] if attempt.get("solc")]
    successful = {a["version"] for a in attempts if a["solc"]["returncode"] == 0}
    if successful:
        labels = {r["category"] for r in failures if r.get("stage") == "slither"
                  and r["version"] in successful}
        return {"categories": sorted(labels or {"slither_incomplete"}), "by_version": {}}
    versions = {a["version"]: set() for a in attempts}
    for row in failures:
        if row.get("version") in versions:
            versions[row["version"]].add(row["category"])
    if not versions:
        return {"categories": ["other"], "by_version": {}}
    for labels in versions.values():
        if not labels:
            labels.add("other")
    # A pragma rejection says nothing about the source on a compatible compiler.
    # Keep all observed labels in by_version, including candidates that only reject the version.
    compatible = [labels - {"version_mismatch"} for labels in versions.values()
                  if labels - {"version_mismatch"}]
    common = set.intersection(*compatible) if compatible else set()
    return {"categories": sorted(common or {"version_dependent"}),
            "by_version": {v: sorted(labels) for v, labels in versions.items()}}


def aggregate_failures(classifications, categories):
    """Count units, not diagnostics; preserve zero-frequency taxonomy categories.

    classifications rows carry corpus, unit_id, entry_sha256, status, failures.
    Category percentages may sum above 100 because labels are non-exclusive.
    """
    counts, by_corpus, examples, templates = Counter(), defaultdict(Counter), defaultdict(set), Counter()
    total, failed, successes = Counter(), Counter(), Counter()
    packages, import_paths, candidates = Counter(), Counter(), Counter()
    for row in classifications:
        corpus = row["corpus"]
        total[corpus] += 1
        if row["status"] == "success":
            successes[corpus] += 1
            continue
        failed[corpus] += 1
        labels = {failure["category"] for failure in row["failures"]}
        for category in labels:
            counts[category] += 1
            by_corpus[category][corpus] += 1
            examples[category].add(row["entry_sha256"])
        for failure in row["failures"]:
            template = failure.get("template") or failure.get("error_template") or failure.get("reason")
            if failure["category"] == "other":
                templates[template or "<absent>"] += 1
        # Count unresolved import occurrences once per compiled unit/source
        # location, not once per compiler candidate.
        seen = set()
        for failure in row["failures"]:
            key = (failure.get("source_path"), failure.get("start"), failure.get("path"))
            if key in seen:
                continue
            seen.add(key)
            if failure.get("package"):
                packages[failure["package"]] += 1
                import_paths[failure["path"]] += 1
            if failure.get("candidate_kind"):
                candidates[failure["candidate_kind"]] += 1
    denominator = sum(failed.values())
    table = []
    for name in sorted(set(categories) | set(counts)):
        table.append({"category": name, "units": counts[name],
            "fraction_remaining_failures": counts[name] / denominator if denominator else 0,
            "by_corpus": dict(by_corpus[name]), "example_sha256": sorted(examples[name])[:3]})
    return {"total": dict(total), "success": dict(successes), "remaining_failures": dict(failed),
            "category_unit_counts": table, "categories_are_nonexclusive": True,
            "other_templates": dict(templates), "unresolved_packages": dict(packages),
            "unresolved_import_paths": dict(import_paths), "relative_basename_candidates": dict(candidates),
            "import_count_basis": "unique importer/byte-position/path per compilation unit; closures overlap"}


def parseable_version_blockers(by_version):
    """Return shared labels on candidates without the two parser-blocking diagnostics.

    An empty result means no common blocker was observed (including no parseable
    candidate). This supplementary evidence never changes the primary cause.
    """
    parser_failures = {"parser_error_other", "unbalanced_structure"}
    remaining = [set(labels) - {"version_mismatch"} for labels in by_version.values()
                 if parser_failures.isdisjoint(labels) and set(labels) - {"version_mismatch"}]
    return sorted(set.intersection(*remaining)) if remaining else []


def aggregate_attributions(classifications, categories):
    """Report both candidate conventions from the same population and denominator."""
    primary_rows, all_rows, combinations = [], [], Counter()
    blockers, exclusions, unmeasured = [], Counter(), Counter()
    for item in classifications:
        primary = item["primary"]
        if "non_solidity_input" in primary["categories"]:
            exclusions[item["corpus"]] += 1
            continue
        if item["status"] == "unmeasured":
            unmeasured[item["corpus"]] += 1
            continue
        row = {key: item[key] for key in ("unit_id", "status", "corpus", "entry_sha256")}
        any_rows = [{"category": category} for category in item["any_categories"]]
        all_rows.append(dict(row, failures=any_rows))
        primary_rows.append(dict(row, failures=[{"category": c} for c in primary["categories"]]))
        if "version_dependent" in primary["categories"]:
            labels = parseable_version_blockers(primary["by_version"]) or ["none"]
            blockers.append(dict(row, failures=[{"category": label} for label in labels]))
            for version, labels in primary["by_version"].items():
                combinations[(version, tuple(labels))] += 1
    def table(rows, names):
        counts = aggregate_failures(rows, names)
        return {key: counts[key] for key in (
            "total", "success", "remaining_failures", "category_unit_counts",
            "categories_are_nonexclusive")}

    return {
        "primary": table(primary_rows, list(categories) + ["version_dependent"]),
        "any_candidate": table(all_rows, categories),
        "non_solidity_by_corpus": dict(exclusions),
        "unmeasured_by_corpus": dict(unmeasured),
        "version_dependent_blockers": {
            "units": len(blockers),
            "category_unit_counts": aggregate_failures(blockers, ["none"])["category_unit_counts"]},
        "version_dependent_combinations": [
            {"version": version, "categories": list(labels), "units": count}
            for (version, labels), count in sorted(combinations.items(), key=lambda pair: (-pair[1], pair[0]))]}


def dependency_benchmark_summary(rows):
    """Aggregate the two denominators and all graph metrics without dropping failed repairs."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row["split"], row["operator"])].append(row)
    output = {}
    for (split, operator), samples in sorted(groups.items()):
        scores = [r["score"] for r in samples]
        item = dict(units=len(samples), compiled=sum(s["compiled"] for s in scores),
                    exact=sum(s["exact"] for s in scores), exact_ratio=sum(s["exact"] for s in scores)/len(scores),
                    removed_by_repair=sum(s["removed_by_repair"] for s in scores),
                    names=dict(Counter(s["counter_correspondence"]["status"] for s in scores)),
                    change_levels=dict(Counter(r["change_level"] for r in samples)))
        for view in ("main", "surviving"):
            stats = [s if view == "main" else s["surviving"] for s in scores]
            item[view] = {}
            for metric in ("kept", "cfg_edges", "calls"):
                facts = [s[metric] for s in stats]
                if metric == "kept":
                    numerator = sum(f["equal"] for f in facts)
                    denominator = sum(f["units"] for f in facts)
                else:
                    numerator = sum(f["matched"] for f in facts)
                    denominator = sum(f["truth"] + f["repaired"] - f["matched"] for f in facts)
                item[view][metric] = dict(numerator=numerator, denominator=denominator,
                    pooled_ratio=numerator/denominator if denominator else 1.0,
                    mean_unit_ratio=sum(f["ratio"] for f in facts)/len(facts))
        if operator == "unresolved_package_import":
            comparisons = [equal for row in samples for equal in row["original_package_bytes_equal"].values()]
            item["original_package_files"] = dict(total=len(comparisons), equal=sum(comparisons),
                                                  ratio=sum(comparisons)/len(comparisons) if comparisons else None)
            item["units_with_all_original_package_bytes"] = sum(bool(r["original_package_bytes_equal"])
                    and all(r["original_package_bytes_equal"].values()) for r in samples)
        output.setdefault(split, {})[operator] = item
    return output
