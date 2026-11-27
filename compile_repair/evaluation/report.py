"""CP3 observed-failure aggregation and the CP7 retrieval benchmark; policy stays in the pipeline."""
import re
from collections import Counter, defaultdict
from pathlib import Path

from compile_repair.rag.retrieve import Query, retrieve
from compile_repair.toolchain.solc import (
    classify_constraints, classify_diagnostic, classify_slither, parse_diagnostics, version_tuple)


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
        if operator == "standard_json_input":
            item["recovered_nodes"] = sum(s["affected_by_damage"] - s["lost"] for s in scores)
            item["lost"] = sum(s["lost"] for s in scores)
            item["added"] = sum(s["added"] for s in scores)
            output.setdefault(split, {})[operator] = item
            continue
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


# ---- CP7: retrieval benchmark (PROMPTS 3.4, 4.7) -----------------------------------------

# Correct K1 knowledge per CP4 operator, fixed from the documentation before any retrieval
# was run: (file path pattern, heading pattern); a section is correct when its file matches
# and one heading of its title chain matches. Operators whose repair needs project or
# library context (K2/K3), or that no documentation section explains (codegen_only,
# parser_error_other), have no K1 truth and are not scored for K1.
_PRAGMA = ((r"layout-of-source-files\.rst$", r"^Version Pragma$"),)
_IMPORTS = ((r"layout-of-source-files\.rst$", r"^(Importing other Source Files|Paths|Import Paths)$"),
            (r"path-resolution\.rst$", r"."))
K1_TRUTH = {
    "closure_version_conflict": _PRAGMA, "unsupported_disjunction": _PRAGMA, "unsupported_expression": _PRAGMA,
    "unterminated_pragma": _PRAGMA, "pragma_missing_semicolon_candidate": _PRAGMA,
    "multiple_license_or_pragma": ((r"layout-of-source-files\.rst$", r"^(ABI Coder Pragma|ABIEncoderV2)$"),),
    "docstring_error": ((r"natspec-format\.rst$", r"^Tags$"),),
    "syntax_error": ((r"050-breaking-changes\.rst$", r"^Explicitness Requirements$"),
                     (r"(contracts|visibility-and-getters)\.rst$", r"^Visibility and Getters$")),
    "encoding": ((r"(types|value-types)\.rst$", r"^(String Literals( and Types)?|Unicode Literals)$"),),
    "type_error_other": ((r"control-structures\.rst$", r"^Control Structures$"),),
    "declaration_error": ((r"050-breaking-changes\.rst$", r"^Constructors$"),
                          (r"(contracts|inheritance|constructor)\.rst$", r"^Constructors?$")),
    "duplicate_definition": ((r"control-structures\.rst$", r"^Scoping and Declarations$"),),
    "unimplemented_feature": ((r"(types|reference-types)\.rst$", r"^Data [Ll]ocation( and [Aa]ssignment [Bb]ehaviou?r)?$"),),
    "io_error": _IMPORTS, "missing_relative_file": _IMPORTS,
    "standard_json_input": ((r"using-the-compiler\.rst$", r"^(Compiler Input and Output JSON Description|Input Description)$"),),
}


def k1_correct(entry, operator):
    """Whether a K1 entry is a correct section for the operator (K1_TRUTH)."""
    return any(re.search(path, entry.payload["path"]) and any(re.search(head, t) for t in entry.payload["titles"])
               for path, head in K1_TRUTH.get(operator, ()))


def receipt_queries(receipts, docs_versions):
    """One retrieval query per included CP4 sample, from its recorded first error line.

    The version is the sample's selected or environment version, otherwise the newest
    documented version of its series; the group is the CP4 project group.
    """
    newest = {}
    for v in docs_versions:
        series = ".".join(v.split(".")[:2])
        if series not in newest or version_tuple(v) > version_tuple(newest[series]):
            newest[series] = v
    samples = []
    for r in receipts:
        if r.get("outcome") != "included":
            continue
        line = r.get("selected_first_line") or r.get("environment_first_line") or ""
        version = r.get("environment_version") or newest.get(r.get("series"))
        categories = tuple(r.get("selected_categories") or r.get("environment_categories") or ())
        samples.append(dict(sample=r["mutation_sha256"], unit_id=r["unit_id"], operator=r["operator"],
                            split=r["split"], group=r["group"],
                            query=Query(errors=(line,), version=version, categories=categories, group=r["group"])))
    return samples


def retrieval_hits(kb, samples, correct, source, k_max):
    """Per sample, the 1-based rank of the first correct hit within k_max (None if absent)."""
    entries = {e.entry_id: e for e in kb.by_source[source]}
    ranks = []
    for sample in samples:
        hits = retrieve(kb, sample["query"], k_max, (source,))[source]
        rank = next((i + 1 for i, h in enumerate(hits) if correct(entries[h.entry_id], sample)), None)
        ranks.append(dict(sample=sample["sample"], operator=sample["operator"], split=sample["split"],
                          group=sample["group"], rank=rank, returned=len(hits)))
    return ranks


def hit_rates(ranks, ks):
    """Share of samples with a correct hit within each k, overall and per operator and split."""
    table = defaultdict(lambda: defaultdict(lambda: [0] * (len(ks) + 1)))
    for row in ranks:
        for key in (("all", row["split"]), (row["operator"], row["split"])):
            cell = table[key[0]][key[1]]
            cell[0] += 1
            for i, k in enumerate(ks):
                cell[i + 1] += int(row["rank"] is not None and row["rank"] <= k)
    return {name: {split: dict(samples=c[0], **{"hit@%d" % k: round(c[i + 1] / c[0], 4) for i, k in enumerate(ks)})
                   for split, c in splits.items()} for name, splits in table.items()}


def choose_k(rates, ks, split="dev", tolerance=0.95):
    """Smallest k whose dev hit rate reaches `tolerance` of the rate at the largest k (PROMPTS 4.7)."""
    cell = rates["all"][split]
    best = cell["hit@%d" % ks[-1]]
    return next(k for k in ks if cell["hit@%d" % k] >= tolerance * best)
