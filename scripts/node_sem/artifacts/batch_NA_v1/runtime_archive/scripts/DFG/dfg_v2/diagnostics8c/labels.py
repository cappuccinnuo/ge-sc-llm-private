"""Independent, read-only Prompt 8C label sensitivity audit.

The author rule is an empirically checked hypothesis, not verified ground truth.
No reviewer functions are imported. Comment lexing preserves quoted strings.
C1/C2 are diagnostic scoring views; frozen labels and graphs are never written.
"""
import csv
import hashlib
import io
import json
import re
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

PIN = "4b0573e1b3f7031396de6f48f7f3e7380222ad3a"
CONTAINERS = frozenset(("contract_declaration", "library_declaration"))
FUNCTIONS = frozenset(("function_definition", "constructor_definition",
                       "modifier_definition"))
TASK_OPTIONS = {
    "reentrancy_node": ("reentrancy", "Re-entrancy", "re_ent"),
    "access_control_node": ("access_control", "tx.origin", "txorigin"),
}


def _lex_comments(text):
    chars = list(text)
    comments = []
    i = 0
    while i < len(text):
        if text[i] in ("'", '"'):
            quote = text[i]
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            continue
        if text.startswith("//", i) or text.startswith("/*", i):
            start = i
            if text.startswith("//", i):
                end = text.find("\n", i)
                end = len(text) if end < 0 else end
            else:
                end = text.find("*/", i + 2)
                end = len(text) if end < 0 else end + 2
            comments.append({"start": start, "end": end,
                             "line": text.count("\n", 0, start) + 1,
                             "text": text[start:end]})
            for k in range(start, end):
                if chars[k] not in "\r\n":
                    chars[k] = " "
            i = end
        else:
            i += 1
    return "".join(chars), comments


def strip_comments(text):
    """Preserve strings and line positions; do not interpret Solidity syntax."""
    return _lex_comments(text)[0]


def normalized_lines(text):
    return ["".join(line.split()) for line in strip_comments(text).splitlines()]


def map_lines(original, cleaned):
    """Greedy, forward-only normalized-text match; never guess unmatched lines."""
    old, new = normalized_lines(original), normalized_lines(cleaned)
    mapping, unmatched_clean, cursor = {}, [], 0
    for clean_line, content in enumerate(new, 1):
        if not content:
            continue
        match = next((j for j in range(cursor, len(old))
                      if old[j] == content), None)
        if match is None:
            unmatched_clean.append({"line": clean_line, "normalized_text": content})
        else:
            mapping[match + 1] = clean_line
            cursor = match + 1
    unmapped_original = [
        {"line": i, "normalized_text": content}
        for i, content in enumerate(old, 1) if content and i not in mapping
    ]
    return {
        "raw_to_clean": mapping,
        "unmapped_cleaned": unmatched_clean,
        "unmapped_original": unmapped_original,
        "unmapped_cleaned_lines": len(unmatched_clean),
        "unmapped_original_lines": len(unmapped_original),
        "original_physical_lines": len(old),
        "cleaned_physical_lines": len(new),
        "method": "forward_exact_after_quote_aware_comment_and_all_whitespace_removal",
    }


def parse_buglog(text):
    rows = []
    for i, row in enumerate(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))), 1):
        loc, length = int(row["loc"]), int(row["length"])
        if loc < 1 or length < 1:
            raise ValueError("invalid BugLog interval at record %d" % i)
        rows.append({"entry": i, "loc": loc, "length": length,
                     "end": loc + length - 1, "original_record": row})
    return rows


def node_lines(row):
    lines = set()
    for span in row["graph_stored_source_lines"]:
        if not span or any(not isinstance(x, int) for x in span):
            raise ValueError("invalid stored node span")
        if span[-1] < span[0]:
            raise ValueError("reversed stored node span")
        lines.update(range(span[0], span[-1] + 1))
    return lines


def node_start(row):
    spans = row["graph_stored_source_lines"]
    return min((s[0] for s in spans if s), default=None)


def anchor_first_line(row):
    anchor = row.get("graph_label_anchor") or ""
    return anchor.strip('"').split("\\n", 1)[0].split("\n", 1)[0]


def inferred_label(row, bug_lines):
    """Contract starts only; all other node types use inclusive stored ranges."""
    if row["node_type"] == "contract_declaration":
        return int(node_start(row) in bug_lines)
    return int(bool(node_lines(row).intersection(bug_lines)))


def first_overlap(records):
    """First interval (ordered by raw start, stable record id) meeting any prior."""
    previous = []
    for current in sorted(records, key=lambda r: (r["loc"], r["entry"])):
        hits = [r for r in previous if r["end"] >= current["loc"]]
        if hits:
            return {"current": current, "previous": hits,
                    "overlap_start": current["loc"],
                    "ordering": "raw_start_then_original_csv_record"}
        previous.append(current)
    return None


def truncation_evidence(rows, rule, mapping, buglog, attached_bug_lines=None):
    missing = [r["original_graph_node_id"] for r in rows
               if rule[r["original_graph_node_id"]] == 1 and r["target"] == 0]
    excess = [r["original_graph_node_id"] for r in rows
              if rule[r["original_graph_node_id"]] == 0 and r["target"] == 1]
    positive = [r for r in rows if r["target"] == 1]
    last_start = max((node_start(r) for r in positive if node_start(r) is not None),
                     default=None)
    last_covered = max((n for r in positive for n in node_lines(r)), default=None)
    reverse = {v: k for k, v in mapping.items()}
    overlap = first_overlap(buglog)
    attached = sorted(set(attached_bug_lines or []))
    in_bounds_attached = [n for n in attached if n in reverse]
    inferred_raw = reverse.get(last_start)
    return {
        "truncated": len(missing) > 20,
        "criterion": "more_than_20_rule_positive_frozen_negative_nodes",
        "missing_positive_nodes": missing, "excess_positive_nodes": excess,
        "first_overlap": overlap,
        "last_positive_node_start_clean": last_start,
        "last_positive_node_start_raw": inferred_raw,
        "last_positive_node_covered_clean": last_covered,
        "start_equals_first_overlap_start": (
            inferred_raw == overlap["overlap_start"] if overlap is not None else None),
        "cutoff_interpretation": (
            "positive_node_start_boundary_is_observed_not_the_author_annotation_stop_algorithm"),
        "attached_author_bug_lines_clean": attached,
        "last_attached_bug_line_clean": max(attached) if attached else None,
        "last_mappable_attached_bug_line_raw": (
            reverse[max(in_bounds_attached)] if in_bounds_attached else None),
    }


def _function_name(row):
    match = re.search(r"\b(?:function|modifier)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
                      anchor_first_line(row))
    return match.group(1) if match else ""


def _function_ranges(rows, marker):
    return [
        {"node_id": r["original_graph_node_id"], "start": min(node_lines(r)),
         "end": max(node_lines(r)), "anchor": anchor_first_line(r),
         "has_injection_marker": marker in _function_name(r)}
        for r in rows if r["node_type"] in FUNCTIONS and node_lines(r)
    ]


def _contains(fr, lines):
    return bool(lines) and fr["start"] <= min(lines) and max(lines) <= fr["end"]


def annotation_evidence(source, rows, mapping):
    """Report comment annotations and exact mappings, without target correction."""
    code, comments = _lex_comments(source)
    headers, reports = [], []
    for comment in comments:
        for match in re.finditer(r"@vulnerable_at_lines\s*:\s*([^\r\n]*)",
                                 comment["text"], flags=re.I):
            headers.extend(int(n) for n in re.findall(r"\d+", match.group(1)))
        for offset, line in enumerate(comment["text"].splitlines()):
            if re.search(r"<yes>\s*<report>", line, re.I):
                reports.append(comment["line"] + offset)
    result = []
    raw_lines, code_lines = source.splitlines(), code.splitlines()
    for kind, raw_refs in (("vulnerable_at_lines", headers),
                           ("yes_report_comment", reports)):
        for raw_line in sorted(set(raw_refs)):
            clean_line = mapping.get(raw_line)
            hits = []
            if clean_line is not None:
                for row in rows:
                    if clean_line in node_lines(row):
                        hits.append({
                            "node_id": row["original_graph_node_id"],
                            "node_type": row["node_type"], "target": row["target"],
                            "anchor": anchor_first_line(row),
                        })
            next_code = next((i for i in range(raw_line + 1, len(code_lines) + 1)
                              if code_lines[i - 1].strip()), None)
            result.append({
                "annotation_kind": kind, "raw_line": raw_line,
                "cleaned_line": clean_line,
                "original_text": raw_lines[raw_line - 1]
                if 1 <= raw_line <= len(raw_lines) else None,
                "same_line_has_code": bool(code_lines[raw_line - 1].strip())
                if 1 <= raw_line <= len(code_lines) else False,
                "following_code_line_context_only": next_code,
                "nodes_covering_mapped_line": hits,
                "mapping_status": "mapped" if clean_line is not None else "unmapped",
            })
    return result


def audit_file(source, cleaned, rows, buglog, marker, attached_bug_lines=None):
    if not rows:
        raise ValueError("file audit requires prediction identities")
    files = {r["file"] for r in rows}
    if len(files) != 1:
        raise ValueError("mixed source files")
    if len({r["original_graph_node_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate original node identity")
    mapping_result = map_lines(source, cleaned)
    mapping = mapping_result["raw_to_clean"]
    filename = rows[0]["file"]
    solidifi = bool(re.fullmatch(r"buggy_\d+\.sol", filename))
    if solidifi and buglog is None:
        raise ValueError("SolidiFI file missing pinned BugLog")
    records = buglog or []
    raw_bug_lines = {n for record in records
                     for n in range(record["loc"], record["end"] + 1)}
    bug_lines = {mapping[n] for n in raw_bug_lines if n in mapping}
    rule = {r["original_graph_node_id"]: inferred_label(r, bug_lines)
            for r in rows} if solidifi else {}
    truncation = truncation_evidence(
        rows, rule, mapping, records, attached_bug_lines) if solidifi else None
    functions = _function_ranges(rows, marker)
    raw_lines = source.splitlines()
    source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
    nodes, spills = [], []
    special = (filename == "parity_wallet_bug_2.sol" or
               filename.startswith("0x627fa62"))
    for row in rows:
        nid = row["original_graph_node_id"]
        lines = node_lines(row)
        enclosing = [fr for fr in functions if _contains(fr, lines)]
        marked = [fr for fr in enclosing if fr["has_injection_marker"]]
        own_marker = marker in anchor_first_line(row)
        lexical = int(row["node_type"] not in CONTAINERS and
                      (own_marker or bool(marked)))
        spill = bool(solidifi and rule[nid] and not own_marker and not marked)
        reasons = []
        if spill:
            reasons.append("rule_positive_outside_identifier_marked_injection_candidate")
        if row["node_type"] in CONTAINERS:
            reasons.append("container_node")
        if special:
            reasons.append("explicit_special_file")
        if spill:
            relevant_clean = {node_start(row)} if row["node_type"] == "contract_declaration" else lines
            raw_hits = sorted(n for n, c in mapping.items()
                              if c in relevant_clean and n in raw_bug_lines)
            evidence = [
                {"buglog_entry": rec,
                 "raw_lines": [{"line": n,
                                "text": raw_lines[n - 1] if n <= len(raw_lines) else None}
                               for n in raw_hits if rec["loc"] <= n <= rec["end"]]}
                for rec in records
                if any(rec["loc"] <= n <= rec["end"] for n in raw_hits)
            ]
            spills.append({
                "file": filename, "source_sha256": source_sha, "node_id": nid,
                "node_type": row["node_type"], "target": row["target"],
                "node_first_line": anchor_first_line(row),
                "graph_stored_source_lines": row["graph_stored_source_lines"],
                "enclosing_functions": enclosing, "buglog_evidence": evidence,
                "interpretation": "lexical_injection_scope_candidate_not_verified_vulnerability_truth",
            })
        c1 = rule[nid] if solidifi and truncation["truncated"] else row["target"]
        nodes.append({
            "file": filename, "source_sha256": source_sha, "node_id": nid,
            "original_graph_node_id": nid,
            "node_type": row["node_type"], "orig": int(row["target"]),
            "C1": int(c1), "C2": int(c1), "C2_include": not reasons,
            "exclusion_reasons": reasons, "rule_target": rule.get(nid),
            "lexical_prediction": lexical, "solidifi": solidifi,
            "in_injection_marker_function": bool(marked),
            "node_has_injection_marker": own_marker,
        })
    agreements = sum(rule[r["original_graph_node_id"]] == r["target"]
                     for r in rows) if solidifi else None
    annotations = annotation_evidence(source, rows, mapping) if not solidifi else []
    return {
        "file": filename, "source_sha256": source_sha, "nodes": nodes,
        "node_count": len(rows), "positive_nodes": sum(r["target"] for r in rows),
        "solidifi": solidifi, "mapping": mapping_result,
        "buglog": records, "raw_bug_line_count": len(raw_bug_lines),
        "unmapped_raw_bug_lines": sorted(raw_bug_lines.difference(mapping)),
        "mapped_bug_lines_cleaned": sorted(bug_lines),
        "rule_agree": agreements,
        "rule_agreement": agreements / len(rows) if solidifi else None,
        "truncation": truncation, "spill_candidates": spills,
        "annotation_evidence": annotations,
        "special_file_evidence": {
            "selected_for_explicit_review": special,
            "cleaned_physical_lines": len(cleaned.splitlines()),
            "positive_nodes": sum(r["target"] for r in rows),
            "changeOwner_nodes": [
                {"node_id": r["original_graph_node_id"], "target": r["target"],
                 "lines": r["graph_stored_source_lines"],
                 "first_line": anchor_first_line(r)}
                for r in rows if "changeOwner" in anchor_first_line(r)],
            "annotation_matches": annotations,
        } if special else None,
    }


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_source(ref):
    path = Path(ref["path"])
    if sha(path) != ref["sha256"]:
        raise ValueError("source SHA mismatch: %s" % path)
    return path.read_bytes().decode("utf-8")


def _counts(rows, targets):
    tp = fp = fn = 0
    for row in rows:
        t, p = int(targets(row)), int(row["best"])
        tp += t == 1 and p == 1
        fp += t == 0 and p == 1
        fn += t == 1 and p == 0
    return {"tp": tp, "fp": fp, "fn": fn}


def _bf1(counts):
    denominator = 2 * counts["tp"] + counts["fp"] + counts["fn"]
    return 200.0 * counts["tp"] / denominator if denominator else 0.0


def comparison_projection(task_audit, profile_folds):
    """Build independently computed reviewer-compatible summaries for comparison."""
    nodes = {(r["file"], r["node_id"]): r for r in task_audit["nodes"]}
    files = task_audit["files"]
    not_truncated = [f for f in files if f["solidifi"] and not f["truncation"]["truncated"]]
    result = {
        "truncated_files": sorted(f["file"] for f in files if f["solidifi"] and f["truncation"]["truncated"]),
        "rule_agreement_non_truncated": [
            sum(f["rule_agree"] for f in not_truncated),
            sum(f["node_count"] for f in not_truncated)],
        "scores": {},
        "per_file": {f["file"]: {
            "nodes": f["node_count"], "rule_agree": f["rule_agree"],
            "unmapped_cleaned_lines": f["mapping"]["unmapped_cleaned_lines"]}
                    for f in files if f["solidifi"]},
    }
    for profile, fold_rows in profile_folds.items():
        result["scores"][profile] = {}
        for view in ("orig", "C1", "nonSolidiFI_only"):
            counts, fold_scores = {"tp": 0, "fp": 0, "fn": 0}, []
            for fold in sorted(fold_rows):
                rows = fold_rows[fold]
                if view == "nonSolidiFI_only":
                    rows = [r for r in rows if not nodes[(r["file"], r["original_graph_node_id"])]["solidifi"]]
                c = _counts(rows, lambda r: nodes[(r["file"], r["original_graph_node_id"])][
                    "C1" if view == "C1" else "orig"])
                fold_scores.append(_bf1(c))
                for key in counts:
                    counts[key] += c[key]
            result["scores"][profile][view] = dict(
                counts, folds=fold_scores, pooled_bf1=_bf1(counts),
                fold_mean_bf1=statistics.mean(fold_scores),
                fold_mean_role="reviewer_comparison_only_not_nonSolidiFI_inference")
    return result


def compare_review(ours, reviewer):
    """List every requested common-field discrepancy, without changing either."""
    differences, checks = [], 0
    for task, actual in ours.items():
        expected = reviewer[task]
        fields = [("truncated_files",), ("rule_agreement_non_truncated",)]
        for filename in actual["per_file"]:
            fields.extend(("per_file", filename, field)
                          for field in ("nodes", "rule_agree", "unmapped_cleaned_lines"))
        for profile in actual["scores"]:
            for view in actual["scores"][profile]:
                fields.extend(("scores", profile, view, field)
                              for field in ("tp", "fp", "fn", "fold_mean_bf1", "pooled_bf1", "folds"))
        for path in fields:
            left, right = actual, expected
            for key in path:
                left, right = left[key], right[key]
            checks += 1
            equal = abs(left - right) <= 1e-10 if isinstance(left, float) else left == right
            if not equal:
                differences.append({"task": task, "field": list(path),
                                    "ours": left, "reviewer": right})
    return {"checks": checks, "differences": differences,
            "status": "equal" if not differences else "differences_retained"}


def _json_value(value):
    import ast
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
    return value


def attached_records(graph):
    """Decode graph's serialized metadata with literal_eval, never eval."""
    records = defaultdict(dict)
    for _, data in graph.nodes(data=True):
        filename = _json_value(data.get("source_file"))
        value = _json_value(data.get("node_info_vulnerabilities", []))
        if value is None:
            continue
        if not isinstance(value, (list, tuple)):
            raise ValueError("unrecognized attached annotation representation")
        if not value:
            continue
        for record in value:
            if not isinstance(record, dict) or "lines" not in record:
                raise ValueError("invalid attached annotation record")
            key = json.dumps(record, sort_keys=True)
            records[filename][key] = record
    return {filename: list(items.values()) for filename, items in records.items()}


def verify_frozen_labels(graph, prediction_rows):
    """Cross-check node identity and binary labels directly against frozen HCG."""
    checked = 0
    for row in prediction_rows:
        nid = row["original_graph_node_id"]
        data = graph.nodes[nid]
        target = int(data.get("node_info_vulnerabilities") is not None)
        if target != row["target"]:
            raise ValueError("prediction target differs from frozen graph")
        if _json_value(data.get("source_file")) != row["file"]:
            raise ValueError("prediction source differs from frozen graph")
        if data["node_type"] != row["node_type"]:
            raise ValueError("prediction node type differs from frozen graph")
        if data["node_source_code_lines"] != row["graph_stored_source_lines"]:
            raise ValueError("prediction coordinate differs from frozen graph")
        checked += 1
    return checked


def _write_json_new(path, content):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(content, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def run_audit(repo, plan_path, out_dir, solidifi_repo):
    """Read two node task matrices, verify pinned inputs, write only fresh A."""
    from scripts.labeling_v2.safe_graph import read_graph
    repo, plan_path = Path(repo), Path(plan_path)
    out_dir, solidifi_repo = Path(out_dir), Path(solidifi_repo)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    actual_pin = subprocess.check_output(
        ["git", "-C", str(solidifi_repo), "rev-parse", "HEAD"]).decode().strip()
    if actual_pin != PIN:
        raise ValueError("SolidiFI checkout HEAD differs from pinned commit")
    if out_dir.exists():
        raise FileExistsError("audit output must be new: %s" % out_dir)
    out_dir.mkdir(parents=False)
    provenance = {"plan": {"path": str(plan_path), "sha256": sha(plan_path)},
                  "solidifi_git_commit": PIN, "csv": [], "sources": [],
                  "predictions": [], "graphs": []}
    task_audits, projections = {}, {}
    for task, (category, csv_dir, marker) in TASK_OPTIONS.items():
        task_plan = plan["tasks"][task]
        profiles = {}
        expected_folds = set(task_plan["folds"])
        # The plan enumerates jobs; paths follow the frozen runner's convention.
        jobs = [j for j in plan["jobs"] if j["task_id"] == task]
        for job in jobs:
            fold, profile, seed = job["fold"], job["profile"], job["seed"]
            if seed != 1:
                raise ValueError("audit expects frozen seed 1 only")
            attempt_root = plan_path.parent / "runs" / task / (
                "fold_%d" % fold) / ("seed_%d" % seed) / profile
            attempts = sorted(a for a in attempt_root.glob("attempt_*") if a.is_dir())
            if len(attempts) != 1 or attempts[0].name != "attempt_001":
                raise ValueError("unexpected fit attempt inventory")
            pred = attempts[0] / "outer_test_predictions.json"
            profiles.setdefault(profile, {})[fold] = json.loads(pred.read_text())
            provenance["predictions"].append({"task": task, "fold": fold,
                "profile": profile, "path": str(pred), "sha256": sha(pred)})
        if set(profiles) != set(plan["profiles"]):
            raise ValueError("profile inventory differs from plan")
        g0 = profiles["G0"]
        if set(g0) != expected_folds:
            raise ValueError("fold inventory differs from plan")
        identities = {}
        byfile, file_fold = defaultdict(list), {}
        for fold, rows in g0.items():
            for row in rows:
                key = (row["file"], row["original_graph_node_id"])
                if key in identities:
                    raise ValueError("duplicate OOF node")
                identities[key] = row
                byfile[row["file"]].append(row)
                if file_fold.setdefault(row["file"], fold) != fold:
                    raise ValueError("file crosses outer folds")
        for profile, folds in profiles.items():
            if set(folds) != expected_folds:
                raise ValueError("profile fold inventory differs")
            seen = set()
            for fold, rows in folds.items():
                for row in rows:
                    key = (row["file"], row["original_graph_node_id"])
                    if key in seen or key not in identities:
                        raise ValueError("profile node inventory differs")
                    seen.add(key)
                    reference = identities[key]
                    for field in ("target", "node_type", "graph_stored_source_lines",
                                  "graph_label_anchor"):
                        if row[field] != reference[field]:
                            raise ValueError("frozen profile identity mismatch: %s" % field)
                    if file_fold[row["file"]] != fold:
                        raise ValueError("profile fold mismatch")
            if seen != set(identities):
                raise ValueError("profile nodes missing")
        prepared = task_plan["prepared"]["0/1"]
        if sha(prepared["path"]) != prepared["sha256"]:
            raise ValueError("prepared manifest changed")
        doc = json.loads(Path(prepared["path"]).read_text())
        ref = doc["profiles"]["G0"]["graph"]
        if sha(ref["path"]) != ref["sha256"]:
            raise ValueError("frozen G0 graph changed")
        graph = read_graph(Path(ref["path"]))
        verified_labels = verify_frozen_labels(graph, list(identities.values()))
        attached = attached_records(graph)
        provenance["graphs"].append({"task": task, "path": ref["path"],
                                     "sha256": ref["sha256"], "verified_node_labels": verified_labels})
        del graph
        files, all_nodes = [], []
        for filename, rows in sorted(byfile.items()):
            source_ref = task_plan["record"]["sources"][filename]
            source = checked_source(source_ref)
            cleaned_path = repo / "experiments/ge-sc-data/source_code" / category / (
                "cleaned_buggy_curated") / filename
            cleaned = cleaned_path.read_bytes().decode("utf-8")
            provenance["sources"].append({
                "task": task, "file": filename, "source": source_ref,
                "cleaned": {"path": str(cleaned_path), "sha256": sha(cleaned_path)},
            })
            buglog = None
            if re.fullmatch(r"buggy_\d+\.sol", filename):
                number = filename[6:-4]
                relative = "buggy_contracts/%s/BugLog_%s.csv" % (csv_dir, number)
                pinned = subprocess.check_output(
                    ["git", "-C", str(solidifi_repo), "show", PIN + ":" + relative])
                local = (solidifi_repo / relative).read_bytes()
                if pinned != local:
                    raise ValueError("local CSV differs from pinned git object: %s" % relative)
                destination = out_dir / "pinned_csv" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as handle:
                    handle.write(pinned)
                provenance["csv"].append({
                    "task": task, "file": filename, "git_path": relative,
                    "git_commit": PIN, "sha256": hashlib.sha256(pinned).hexdigest(),
                    "snapshot_path": str(destination), "local_equals_git_object": True,
                })
                buglog = parse_buglog(pinned.decode("utf-8"))
            author_records = attached.get(filename, [])
            author_lines = {n for record in author_records for n in record["lines"]}
            result = audit_file(source, cleaned, rows, buglog, marker, author_lines)
            result["attached_author_records"] = author_records
            result["attached_lines_outside_cleaned_file"] = sorted(
                n for n in author_lines if n < 1 or n > len(cleaned.splitlines()))
            result["outer_fold"] = file_fold[filename]
            for node in result["nodes"]:
                node["fold"] = file_fold[filename]
            all_nodes.extend(result["nodes"])
            files.append(result)
        task_audits[task] = {
            "task": task, "category": category, "files": files,
            "nodes": all_nodes, "files_count": len(files),
            "nodes_count": len(all_nodes), "criterion_notes": [
                "C1/C2 are sensitivity views, not independently validated ground truth",
                "missing-positive threshold >20; differs from reviewer total-disagreement criterion",
                "spill candidates use injection identifiers and stored function scopes",
                "positive-node-start boundary does not prove annotation generation mechanism",
                "report-only comment lines are not guessed onto following code"],
        }
        projections[task] = comparison_projection(task_audits[task], profiles)
    views = {task: audit["nodes"] for task, audit in task_audits.items()}
    _write_json_new(out_dir / "node_views.json", views)
    for audit in task_audits.values():
        audit.pop("nodes")
        for f in audit["files"]:
            f.pop("nodes")
    _write_json_new(out_dir / "audit.json", {
        "version": "prompt8c-independent-label-audit-v1",
        "tasks": task_audits, "provenance": provenance,
        "node_views": {"path": str(out_dir / "node_views.json"),
                       "sha256": sha(out_dir / "node_views.json")}})
    _write_json_new(out_dir / "review_comparison_projection.json", projections)
    return out_dir / "audit.json"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--solidifi", required=True)
    args = parser.parse_args()
    print(run_audit(args.repo, args.plan, args.out, args.solidifi))
