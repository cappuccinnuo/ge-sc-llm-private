"""Prompt 6d.2: immutable category sampling, shape counts and review gates.

This validator does not run Slither, any analyzer, graph construction or training.
Random samples test predicates; accepted semantic reasons remain explicit analyst
decisions with bound documentary or empirical evidence.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re

from .slither_align import SourceFacts
from .slither_review import (
    sha256, _read, _write, _bound, _check_bound, _check_json_evidence,
    _check_scope_basis, evidence_for, VERDICTS)

VERSION = "dfg-v2-category-validation-v1"


def stratum(event):
    return tuple(event[k] for k in ("task", "layer", "direction", "category"))


def key_for(group):
    return "|".join(group)


def sample_categories(events):
    groups, seen = defaultdict(list), set()
    for event in events:
        identity = event["difference_id"]
        if identity in seen:
            raise ValueError("Duplicate difference identity")
        seen.add(identity)
        if event["layer"] not in ("L1", "L2") or event["direction"] not in ("FP", "FN"):
            raise ValueError("Invalid category stratum")
        groups[stratum(event)].append(event)
    selected, records = [], []
    for group, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda row: row["difference_id"])
        chosen = random.Random(0).sample(rows, 10) if len(rows) > 10 else rows
        chosen = sorted(chosen, key=lambda row: row["difference_id"])
        selected.extend(chosen)
        records.append(dict(key=key_for(group), task=group[0], layer=group[1],
                            direction=group[2], category=group[3], population=len(rows),
                            selected_ids=[row["difference_id"] for row in chosen]))
    return selected, records


def normalized_shape(event, ast):
    """Replace known variable identifiers, preserving selectors and type names.

    Histogram-only rendering; it never drives event matching or classification.
    Variable spelling is normalized by first appearance, preserving repeated
    identity. Whitespace normalization is descriptive, not Solidity execution.
    """
    a, b = event["span"]
    variable_names = set()
    for node in ast.nodes:
        if node.type in ("state_variable_declaration", "variable_declaration", "parameter"):
            name = node.child_by_field_name("name")
            if name is not None:
                variable_names.add(ast.text(name))
    replacements, seen_spans, variables = [], set(), {}
    for node in sorted(ast.nodes, key=lambda n: (n.start_byte, n.end_byte)):
        if node.type != "identifier" or not (a <= node.start_byte and node.end_byte <= b):
            continue
        value, span = ast.text(node), (node.start_byte, node.end_byte)
        if value not in variable_names or span in seen_spans:
            continue
        parent = node.parent
        # A field named like a local is still a member selector, not that local.
        if parent is not None:
            prop = parent.child_by_field_name("property")
            if prop is not None and prop == node:
                continue
            if parent.type in ("user_defined_type", "type_name"):
                continue
        seen_spans.add(span)
        if value not in variables:
            variables[value] = "VAR_" + str(len(variables) + 1)
        replacements.append((span[0], span[1], variables[value]))
    data, cursor = [], a
    for start, end, value in replacements:
        data.append(ast.raw[cursor:start].decode("utf8"))
        data.append(value)
        cursor = end
    data.append(ast.raw[cursor:b].decode("utf8"))
    return re.sub(r"\s+", " ", "".join(data)).strip()


def histogram(events):
    by_file, counts, examples, bindings = defaultdict(list), defaultdict(Counter), {}, {}
    for event in events:
        by_file[(event["source_path"], event["source_sha256"])].append(event)
    for (path, digest), rows in sorted(by_file.items()):
        if sha256(path) != digest:
            raise ValueError("Source identity changed")
        raw = Path(path).read_bytes()
        ast = SourceFacts(raw.decode("utf8"))
        bindings[path] = digest
        for row in rows:
            a, b = row["span"]
            if raw[a:b].decode("utf8") != row["source_excerpt"]:
                raise ValueError("Event source excerpt does not match its span")
            shape, key = normalized_shape(row, ast), key_for(stratum(row))
            counts[key][shape] += 1
            examples.setdefault((key, shape), row["difference_id"])
    result = {}
    for key, count in sorted(counts.items()):
        ordered = sorted(count.items(), key=lambda item: (-item[1], item[0]))
        result[key] = dict(population=sum(count.values()), distinct_shapes=len(count),
                          top10=[dict(template=shape, count=n, example_id=examples[(key, shape)])
                                 for shape, n in ordered[:10]],
                          other_shape_events=sum(n for _, n in ordered[10:]))
    return result, bindings


def prepare(alignment_path, output):
    output, alignment_path = Path(output).resolve(), Path(alignment_path).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    seal_path = alignment_path.with_name("report.seal.json")
    if _read(seal_path)["report_sha256"] != sha256(alignment_path):
        raise ValueError("Alignment seal mismatch")
    alignment = _read(alignment_path)
    selected, groups = sample_categories(alignment["differences"])
    shapes, sources = histogram(alignment["differences"])
    selection = dict(version=VERSION, alignment=_bound(alignment_path),
                     alignment_seal=_bound(seal_path), seed=0, limit=10,
                     sampling="Independent Random(0); sorted IDs; task/layer/direction/category",
                     strata=groups, selected=selected, histograms=shapes,
                     source_bindings=sources, semantic_verdicts_assigned=False)
    output.mkdir(parents=True)
    _write(output / "selection.json", selection)
    _write(output / "selection.seal.json",
           dict(version=VERSION, selection_sha256=sha256(output / "selection.json")))
    return dict(strata=len(groups), selected=len(selected), total=len(alignment["differences"]))


def gate_status(category_states, residuals, defects):
    if defects:
        return "blocked_v2_defect"
    if any(row["status"] not in ("accepted", "accepted_with_residual") for row in category_states):
        return "blocked_unaccepted_category"
    ids = [row["difference_id"] for row in residuals]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate residual identity")
    if not residuals:
        if any(row["status"] != "accepted" for row in category_states):
            return "blocked_residual_status_without_events"
        return "passed_all_categories"
    if len(residuals) > 20 or any(row["direction"] != "FN" for row in residuals):
        return "blocked_residual_count_or_direction"
    # User-approved tightening: a missing event is not itself proof of safety.
    for row in residuals:
        impact = row.get("impact")
        if (not isinstance(impact, dict) or impact.get("checked") is not True or
                impact.get("changes_definition_kill") is not False or
                impact.get("changes_existing_dependency_facts") is not False or
                not impact.get("reason") or not impact.get("evidence")):
            return "blocked_residual_impact_unverified"
    return "passed_with_bounded_FN_residuals"


def validate(selection_path, decisions_path, categories_path):
    selection_path = Path(selection_path).resolve()
    selected = _read(selection_path)
    seal = _read(selection_path.with_name("selection.seal.json"))
    if (selected.get("version") != VERSION or seal.get("version") != VERSION or
            seal["selection_sha256"] != sha256(selection_path) or
            selected.get("seed") != 0 or selected.get("limit") != 10):
        raise ValueError("Selection seal or sampling configuration mismatch")
    alignment_path = _check_bound(selected["alignment"])
    _check_bound(selected["alignment_seal"])
    if _read(selected["alignment_seal"]["path"])["report_sha256"] != sha256(alignment_path):
        raise ValueError("Alignment seal mismatch")
    alignment = _read(alignment_path)
    expected, strata = sample_categories(alignment["differences"])
    if expected != selected["selected"] or strata != selected["strata"]:
        raise ValueError("Not the frozen category sample")
    expected_shapes, expected_sources = histogram(alignment["differences"])
    if (selected.get("source_bindings") != expected_sources or
            selected.get("histograms") != expected_shapes):
        raise ValueError("Source bindings or shape histograms differ from alignment")
    decisions, categories = _read(decisions_path), _read(categories_path)
    for document in (decisions, categories):
        if document.get("version") != VERSION or document.get("selection_sha256") != sha256(selection_path):
            raise ValueError("Decision document belongs to another selection")
    evidence_inputs = categories["evidence_inputs"]
    for item in evidence_inputs:
        _check_bound(item)
    allowed = {str(Path(item["path"]).resolve()) for item in evidence_inputs}
    cache = {}
    by_id = {row["difference_id"]: row for row in expected}
    rows = decisions["decisions"]
    if len(rows) != len(by_id) or {row["difference_id"] for row in rows} != set(by_id):
        raise ValueError("Decisions must cover every selected event exactly once")
    rows_by_id = {}
    for row in rows:
        event = by_id[row["difference_id"]]
        if row.get("evidence") != evidence_for(event) or not row.get("reason"):
            raise ValueError("Decision needs exact event evidence and reason")
        if row.get("verdict") not in VERDICTS or type(row.get("predicate_holds")) is not bool:
            raise ValueError("Invalid sample decision")
        if row["verdict"] == "v2_scope_limit":
            _check_scope_basis(row.get("scope_basis"))
        elif row["verdict"] == "slither_convention":
            if not row.get("convention_evidence"):
                raise ValueError("Convention requires direct empirical evidence")
            for ref in row["convention_evidence"]:
                _check_json_evidence(ref, allowed, cache)
        rows_by_id[row["difference_id"]] = row
    groups = {s["key"]: s for s in strata}
    states = categories["categories"]
    if len(states) != len(groups) or {row["key"] for row in states} != set(groups):
        raise ValueError("Category decisions missing, duplicated or unexpected")
    all_events = {row["difference_id"]: row for row in alignment["differences"]}
    residuals = categories.get("residuals", [])
    residual_ids = [row["difference_id"] for row in residuals]
    if len(residual_ids) != len(set(residual_ids)) or not set(residual_ids).issubset(all_events):
        raise ValueError("Residual identities missing from alignment or duplicated")
    additional_defects = categories.get("additional_defect_ids", [])
    if (len(additional_defects) != len(set(additional_defects)) or
            not set(additional_defects).issubset(all_events)):
        raise ValueError("Additional defect identities missing from alignment or duplicated")
    residual_by_group = defaultdict(set)
    for row in residuals:
        event = all_events[row["difference_id"]]
        if (row["direction"] != event["direction"] or row.get("evidence") != evidence_for(event)
                or not row.get("reason") or not row.get("empirical_checks")):
            raise ValueError("Residual needs its exact identity and attempted evidence")
        for ref in row["empirical_checks"]:
            _check_json_evidence(ref, allowed, cache)
        if row.get("impact", {}).get("evidence"):
            for ref in row["impact"]["evidence"]:
                _check_json_evidence(ref, allowed, cache)
        residual_by_group[key_for(stratum(event))].add(row["difference_id"])
    for state in states:
        group = groups[state["key"]]
        if (state.get("sample_ids") != group["selected_ids"] or
                state.get("population") != group["population"] or
                not state.get("mechanical_predicate") or not state.get("reason")):
            raise ValueError("Category needs exact sample and mechanical/reason records")
        if state["status"] in ("accepted", "accepted_with_residual"):
            samples = [rows_by_id[identity] for identity in group["selected_ids"]]
            if any(row["predicate_holds"] is not True or row["verdict"] in
                   ("v2_defect", "comparator_artifact") for row in samples):
                raise ValueError("Cannot accept a category with a failed predicate or defect")
            if any(row["verdict"] == "unclear" and row["difference_id"] not in
                   residual_by_group[state["key"]] for row in samples):
                raise ValueError("Unclear samples must be listed as residual events")
            if state["status"] == "accepted" and residual_by_group[state["key"]]:
                raise ValueError("Accepted category cannot hide residuals")
            if state["status"] == "accepted_with_residual" and not residual_by_group[state["key"]]:
                raise ValueError("Residual category needs explicit residuals")
            if not state.get("rationale"):
                raise ValueError("Accepted category needs bound rationale")
            for reason in state["rationale"]:
                if reason["kind"] == "scope":
                    _check_scope_basis(reason["reference"])
                elif reason["kind"] == "empirical":
                    _check_json_evidence(reason["reference"], allowed, cache)
                else:
                    raise ValueError("Unknown category rationale")
    defects = [row["difference_id"] for row in rows if row["verdict"] == "v2_defect"]
    defects.extend(additional_defects)
    return dict(version=VERSION, selection_sha256=sha256(selection_path),
                decisions_sha256=sha256(decisions_path), categories_sha256=sha256(categories_path),
                samples=len(rows), strata=len(states), residual_count=len(residuals),
                defect_ids=sorted(set(defects)), gate=gate_status(states,residuals,defects),
                category_status_counts=dict(Counter(row["status"] for row in states)),
                verdict_counts=dict(Counter(row["verdict"] for row in rows)),
                semantic_reasons_are_analyst_decisions=True,
                no_analyzer_graph_or_training_execution=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--alignment", required=True)
    p.add_argument("--output", required=True)
    p = commands.add_parser("validate")
    p.add_argument("--selection", required=True)
    p.add_argument("--decisions", required=True)
    p.add_argument("--categories", required=True)
    args = parser.parse_args(argv)
    result = (prepare(args.alignment, args.output) if args.command == "prepare" else
              validate(args.selection, args.decisions, args.categories))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    main()
