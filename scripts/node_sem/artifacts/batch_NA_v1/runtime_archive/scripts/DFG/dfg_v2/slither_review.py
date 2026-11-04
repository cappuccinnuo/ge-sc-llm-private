"""Freeze Prompt 6d 'other' samples and validate explicit analyst decisions.

Separate from review_sheet's human edge annotation. Never assigns verdicts.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

VERSION = "dfg-v2-slither-other-review-v1"
LEGACY_VERDICTS = ("v2_defect", "slither_convention", "comparator_artifact", "unclear")
VERDICTS = ("v2_defect", "v2_scope_limit", "slither_convention",
            "comparator_artifact", "unclear")
FOLLOWUP_VERSION = "dfg-v2-slither-other-review-v2"
DEFAULT_PREDICATES = (
    "modifier_body_unanalyzed", "loop_header_merge_write", "aggregate_base_use",
    "bare_expression_use", "legacy_alias_unconfirmed",
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf8")


def sample_other(differences, seed=0, limit=30):
    """Independent Random(seed) per sorted task/layer/direction stratum."""
    if type(seed) is not int or type(limit) is not int or limit < 1:
        raise ValueError("Invalid sample configuration")
    groups, seen = defaultdict(list), set()
    for row in differences:
        identity = row["difference_id"]
        if identity in seen:
            raise ValueError("Duplicate difference identity")
        seen.add(identity)
        if row["category"] != "other":
            continue
        if row["layer"] not in ("L1", "L2") or row["direction"] not in ("FP", "FN"):
            raise ValueError("Invalid difference stratum")
        groups[(row["task"], row["layer"], row["direction"])].append(row)
    selected, strata = [], []
    for key, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda row: row["difference_id"])
        chosen = (random.Random(seed).sample(rows, limit) if len(rows) > limit else rows)
        chosen = sorted(chosen, key=lambda row: row["difference_id"])
        selected.extend(chosen)
        strata.append(dict(task=key[0], layer=key[1], direction=key[2],
                           population=len(rows), selected=len(chosen)))
    return selected, strata


def prepare(alignment, output):
    alignment, output = Path(alignment).resolve(), Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    report = _read(alignment)
    selected, strata = sample_other(report["differences"])
    selection = dict(version=VERSION, alignment=str(alignment),
                     alignment_sha256=sha256(alignment), seed=0, limit=30,
                     sampling="sorted difference_id; independent Random(0) per stratum",
                     strata=strata, selected=selected,
                     verdicts_assigned=False, human_edge_review=False)
    output.mkdir(parents=True)
    _write(output / "selection.json", selection)
    _write(output / "selection.seal.json", dict(
        version=VERSION, selection_sha256=sha256(output / "selection.json"),
        alignment_sha256=selection["alignment_sha256"]))
    return dict(selected=len(selected), strata=strata, output=str(output))


def _validate_legacy(selection_path, decisions_path):
    selection_path = Path(selection_path).resolve()
    selection = _read(selection_path)
    seal = _read(selection_path.with_name("selection.seal.json"))
    if selection.get("seed") != 0 or selection.get("limit") != 30:
        raise ValueError("Selection configuration differs from frozen protocol")
    if seal.get("version") != VERSION or selection.get("version") != VERSION:
        raise ValueError("Unexpected selection version")
    if sha256(selection_path) != seal["selection_sha256"]:
        raise ValueError("Selection was modified")
    alignment = Path(selection["alignment"])
    if sha256(alignment) != selection["alignment_sha256"] or \
            seal["alignment_sha256"] != selection["alignment_sha256"]:
        raise ValueError("Alignment report was modified")
    expected, strata = sample_other(_read(alignment)["differences"])
    if expected != selection["selected"] or strata != selection["strata"]:
        raise ValueError("Selection is not the fixed seed-0 sample")
    document = _read(decisions_path)
    if document.get("selection_sha256") != seal["selection_sha256"]:
        raise ValueError("Decisions use a different selection")
    by_id = {row["difference_id"]: row for row in selection["selected"]}
    decisions = document["decisions"]
    ids = [row["difference_id"] for row in decisions]
    if len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError("Decisions must cover every selected event exactly once")
    counts, patterns, source_checked = Counter(), defaultdict(list), {}
    comparator_pending = False
    for decision in decisions:
        row, verdict = by_id[decision["difference_id"]], decision.get("verdict")
        if verdict not in LEGACY_VERDICTS:
            raise ValueError("Unknown analyst verdict")
        if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
            raise ValueError("Every decision needs an explicit reason")
        if not isinstance(decision.get("evidence"), dict) or not decision["evidence"]:
            raise ValueError("Every decision needs inspected evidence")
        source = row["source_path"]
        if source not in source_checked:
            source_checked[source] = sha256(source)
        if source_checked[source] != row["source_sha256"]:
            raise ValueError("Reviewed source was modified")
        comparator_pending = comparator_pending or verdict == "comparator_artifact"
        if verdict == "v2_defect":
            pattern = decision.get("pattern")
            if not isinstance(pattern, str) or not pattern.strip():
                raise ValueError("Analyzer defect needs a syntax pattern identity")
            patterns[pattern].append(row["difference_id"])
        counts[(row["task"], row["layer"], row["direction"], verdict)] += 1
    return dict(version=VERSION, selected=len(ids), reviewed=len(decisions),
                selection_sha256=seal["selection_sha256"],
                decisions_sha256=sha256(decisions_path),
                counts=[dict(task=k[0], layer=k[1], direction=k[2], verdict=k[3], count=n)
                        for k, n in sorted(counts.items())],
                defect_patterns=dict(patterns),
                prompt7_gate=("blocked_v2_defect" if patterns else
                              "pending_comparator_recompute" if comparator_pending else
                              "no_sampled_v2_defect"),
                semantic_verdicts_are_analyst_supplied=True)


def digest_json(value):
    """Digest JSON content, independent of indentation and mapping order."""
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf8")).hexdigest()


def evidence_for(event):
    """Full event commitment plus exact source/primary/counterpart snapshots.

    This helper records facts only. It does not assign a semantic verdict.
    """
    fields = ("source_path", "source_sha256", "span", "source_excerpt", "primary",
              "nearby_candidate", "nearby_reference")
    missing = [field for field in fields if field not in event]
    if missing:
        raise ValueError("Incomplete review event: " + ", ".join(missing))
    result = {field: event[field] for field in fields}
    result["event_sha256"] = digest_json(event)
    return result


def sample_followup(differences, predicates=DEFAULT_PREDICATES):
    """All remaining other up to 150; otherwise 30/stratum. Five/predicate."""
    predicates = tuple(predicates)
    if len(set(predicates)) != len(predicates) or any(
            not isinstance(p, str) or not p.strip() or p == "other" for p in predicates):
        raise ValueError("Invalid new predicate list")
    # Validate every identity even when there are no 'other' entries.
    ordinary, ordinary_strata = sample_other(differences)
    all_other = sorted((row for row in differences if row["category"] == "other"),
                       key=lambda row: row["difference_id"])
    if len(all_other) <= 150:
        ordinary = all_other
        for stratum in ordinary_strata:
            stratum["selected"] = stratum["population"]
    predicate_rows, predicate_strata = [], []
    for predicate in predicates:
        hits = sorted((row for row in differences if row["category"] == predicate),
                      key=lambda row: row["difference_id"])
        chosen = random.Random(0).sample(hits, 5) if len(hits) > 5 else hits
        chosen = sorted(chosen, key=lambda row: row["difference_id"])
        predicate_rows.extend(dict(predicate=predicate, event=row) for row in chosen)
        predicate_strata.append(dict(predicate=predicate, population=len(hits),
                                     selected=len(chosen)))
    return dict(remaining_other=ordinary, other_strata=ordinary_strata,
                other_population=len(all_other),
                other_mode="all" if len(all_other) <= 150 else "30_per_stratum",
                other_unreviewed=len(all_other) - len(ordinary),
                predicate_checks=predicate_rows, predicate_strata=predicate_strata)


def _bound(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def _check_bound(binding):
    path = Path(binding["path"])
    if sha256(path) != binding["sha256"]:
        raise ValueError("Bound input was modified: " + str(path))
    return path


def _followup_sets(alignment, old_selection, old_decisions, predicates):
    old_rows = {row["difference_id"]: row for row in old_selection["selected"]}
    old_judgments = {row["difference_id"]: row for row in old_decisions["decisions"]}
    if len(old_rows) != len(old_selection["selected"]) or \
            len(old_judgments) != len(old_decisions["decisions"]) or \
            set(old_rows) != set(old_judgments):
        raise ValueError("Historical review identities do not agree")
    reclassification = [
        dict(review_id="reclassification:" + identity, purpose="reclassification",
             difference_id=identity, event=old_rows[identity],
             previous_decision=old_judgments[identity])
        for identity in sorted(old_rows)
    ]
    sampled = sample_followup(alignment["differences"], predicates)
    remaining = [
        dict(review_id="remaining_other:" + row["difference_id"],
             purpose="remaining_other", difference_id=row["difference_id"], event=row)
        for row in sampled["remaining_other"]
    ]
    checks = [
        dict(review_id="predicate_check:" + item["predicate"] + ":" +
             item["event"]["difference_id"], purpose="predicate_check",
             predicate=item["predicate"], difference_id=item["event"]["difference_id"],
             event=item["event"])
        for item in sampled["predicate_checks"]
    ]
    return dict(reclassification=reclassification, remaining_other=remaining,
                predicate_checks=checks), {
        key: value for key, value in sampled.items()
        if key not in ("remaining_other", "predicate_checks")
    }


def prepare_followup(alignment, old_selection, old_decisions, output,
                     predicates=DEFAULT_PREDICATES, conventions=()):
    """Freeze three independent review sets without reinterpreting old facts."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    _validate_legacy(old_selection, old_decisions)
    old_selection_path = Path(old_selection).resolve()
    inputs = dict(
        alignment=_bound(alignment), old_selection=_bound(old_selection),
        old_selection_seal=_bound(old_selection_path.with_name("selection.seal.json")),
        old_alignment=_bound(_read(old_selection)["alignment"]),
        old_decisions=_bound(old_decisions),
    )
    convention_inputs = [_bound(path) for path in conventions]
    if len({item["path"] for item in convention_inputs}) != len(convention_inputs):
        raise ValueError("Duplicate convention evidence input")
    sets, sampling = _followup_sets(
        _read(alignment), _read(old_selection), _read(old_decisions), tuple(predicates),
    )
    # Require complete facts before publishing an unusable selection.
    for records in sets.values():
        for record in records:
            evidence_for(record["event"])
    selection = dict(
        version=FOLLOWUP_VERSION, inputs=inputs, seed=0, other_limit=30,
        all_other_threshold=150, predicate_limit=5, predicates=list(predicates),
        convention_inputs=convention_inputs, review_sets=sets, sampling=sampling,
        verdicts_assigned=False, human_edge_review=False,
        old_facts_policy="Exact old selection and decision snapshots; no old/new ID inference",
    )
    output.mkdir(parents=True)
    _write(output / "selection.json", selection)
    _write(output / "selection.seal.json", dict(
        version=FOLLOWUP_VERSION,
        selection_sha256=sha256(output / "selection.json"),
    ))
    return dict(version=FOLLOWUP_VERSION, output=str(output),
                selected_by_purpose={key: len(value) for key, value in sets.items()},
                sampling=sampling)


def _json_pointer(document, pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise ValueError("Evidence locator must be a JSON pointer")
    value = document
    if not pointer:
        return value
    for component in pointer[1:].split("/"):
        component = component.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(value, list):
                if not component.isdigit() or (len(component) > 1 and component[0] == "0"):
                    raise ValueError("Noncanonical JSON array index")
                value = value[int(component)]
            else:
                value = value[component]
        except (KeyError, IndexError, ValueError, TypeError):
            raise ValueError("Evidence pointer does not resolve")
    return value


def _check_json_evidence(reference, allowed_paths=None, cache=None):
    if not isinstance(reference, dict):
        raise ValueError("Evidence reference must be an object")
    path = Path(reference["path"]).resolve()
    key = str(path)
    if cache is None:
        cache = {}
    if key not in cache:
        _check_bound(reference)
        cache[key] = (reference["sha256"], _read(path))
    digest, document = cache[key]
    if reference["sha256"] != digest:
        raise ValueError("Evidence reference SHA differs from the bound input")
    if allowed_paths is not None and str(path) not in allowed_paths:
        raise ValueError("Convention evidence is not a frozen probe input")
    if not isinstance(reference.get("interpretation"), str) or \
            not reference["interpretation"].strip():
        raise ValueError("Evidence reference needs an explicit interpretation")
    if "value" not in reference or "pointer" not in reference or \
            _json_pointer(document, reference["pointer"]) != reference["value"]:
        raise ValueError("Evidence reference does not match the bound JSON fact")


def _check_scope_basis(basis):
    if not isinstance(basis, dict):
        raise ValueError("Scope limit needs an exact documented scope basis")
    path = _check_bound(basis)
    quote = basis.get("quote")
    if not isinstance(quote, str) or not quote.strip() or \
            quote not in path.read_text(encoding="utf8"):
        raise ValueError("Scope basis quote does not occur in the bound document")


def _validate_followup(selection_path, decisions_path):
    selection_path = Path(selection_path).resolve()
    selection, seal = _read(selection_path), _read(
        selection_path.with_name("selection.seal.json"))
    if selection.get("version") != FOLLOWUP_VERSION or \
            seal.get("version") != FOLLOWUP_VERSION:
        raise ValueError("Unexpected followup selection version")
    if sha256(selection_path) != seal["selection_sha256"]:
        raise ValueError("Selection was modified")
    if (selection.get("seed"), selection.get("other_limit"),
            selection.get("all_other_threshold"), selection.get("predicate_limit")) != \
            (0, 30, 150, 5):
        raise ValueError("Followup sampling configuration differs from the protocol")
    paths = {key: _check_bound(value) for key, value in selection["inputs"].items()}
    for binding in selection["convention_inputs"]:
        _check_bound(binding)
    # Preserve old v1 interpretation and validate its input chain, not just its SHA.
    _validate_legacy(paths["old_selection"], paths["old_decisions"])
    expected, sampling = _followup_sets(
        _read(paths["alignment"]), _read(paths["old_selection"]),
        _read(paths["old_decisions"]), selection["predicates"])
    if expected != selection["review_sets"] or sampling != selection["sampling"]:
        raise ValueError("Followup review sets are not the frozen exact selections")
    document = _read(decisions_path)
    if document.get("version") != FOLLOWUP_VERSION or \
            document.get("selection_sha256") != seal["selection_sha256"]:
        raise ValueError("Decisions use a different followup selection")
    by_id = {record["review_id"]: record
             for records in expected.values() for record in records}
    decisions = document["decisions"]
    ids = [decision["review_id"] for decision in decisions]
    if len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError("Decisions must cover every review identity exactly once")
    convention_paths = {item["path"] for item in selection["convention_inputs"]}
    counts, patterns, checked_sources = Counter(), defaultdict(list), {}
    evidence_cache = {}
    comparator_pending, unclear_count = False, 0
    for decision in decisions:
        record = by_id[decision["review_id"]]
        event, verdict = record["event"], decision.get("verdict")
        if decision.get("difference_id") != record["difference_id"]:
            raise ValueError("Decision difference identity differs from the frozen record")
        if verdict not in VERDICTS:
            raise ValueError("Unknown analyst verdict")
        if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
            raise ValueError("Every decision needs an explicit reason")
        if decision.get("evidence") != evidence_for(event):
            raise ValueError("Decision evidence does not equal the complete frozen event")
        if record["purpose"] == "reclassification":
            if decision.get("previous_decision") != record["previous_decision"]:
                raise ValueError("Historical decision facts were modified")
        elif "previous_decision" in decision:
            raise ValueError("New event cannot claim historical decision reuse")
        source = event["source_path"]
        if source not in checked_sources:
            checked_sources[source] = sha256(source)
        if checked_sources[source] != event["source_sha256"]:
            raise ValueError("Reviewed source was modified")
        if verdict == "v2_scope_limit":
            _check_scope_basis(decision.get("scope_basis"))
        if verdict == "slither_convention":
            references = decision.get("convention_evidence")
            if not isinstance(references, list) or not references:
                raise ValueError("Slither convention needs bound direct probe evidence")
            for reference in references:
                _check_json_evidence(reference, convention_paths, evidence_cache)
        if verdict == "comparator_artifact":
            # Historical unit mismatches may already be fixed in this new report.
            # The reviewer must link exact current report evidence, not silently
            # relabel them as a tool convention.
            if record["purpose"] == "reclassification" and \
                    decision.get("artifact_resolution") is not None:
                resolution = decision["artifact_resolution"]
                _check_json_evidence(resolution, {str(paths["alignment"].resolve())}, evidence_cache)
            else:
                comparator_pending = True
        if verdict == "v2_defect":
            pattern = decision.get("pattern")
            if not isinstance(pattern, str) or not pattern.strip():
                raise ValueError("Analyzer defect needs a syntax pattern identity")
            patterns[pattern].append(decision["review_id"])
        unclear_count += verdict == "unclear"
        counts[(record["purpose"], event["task"], event["layer"],
                event["direction"], verdict)] += 1
    return dict(
        version=FOLLOWUP_VERSION, selection_sha256=seal["selection_sha256"],
        decisions_sha256=sha256(decisions_path),
        selected_by_purpose={key: len(value) for key, value in expected.items()},
        reviewed=len(decisions), sampling=sampling,
        counts=[dict(purpose=key[0], task=key[1], layer=key[2], direction=key[3],
                     verdict=key[4], count=count) for key, count in sorted(counts.items())],
        defect_patterns=dict(patterns), unclear_count=unclear_count,
        prompt7_gate=("blocked_v2_defect" if patterns else
                      "pending_comparator_recompute" if comparator_pending else
                      "unresolved_analyst_findings" if unclear_count else
                      "no_reviewed_v2_defect"),
        semantic_verdicts_are_analyst_supplied=True,
        evidence_binding_does_not_prove_semantic_correctness=True,
    )


def validate(selection_path, decisions_path):
    """Old review bundles remain readable; stronger v2 rules apply only to v2."""
    version = _read(selection_path).get("version")
    if version == VERSION:
        return _validate_legacy(selection_path, decisions_path)
    if version == FOLLOWUP_VERSION:
        return _validate_followup(selection_path, decisions_path)
    raise ValueError("Unexpected selection version")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    select = commands.add_parser("prepare")
    select.add_argument("--alignment", required=True)
    select.add_argument("--output", required=True)
    followup = commands.add_parser("prepare-followup")
    followup.add_argument("--alignment", required=True)
    followup.add_argument("--old-selection", required=True)
    followup.add_argument("--old-decisions", required=True)
    followup.add_argument("--output", required=True)
    followup.add_argument("--predicates", default=",".join(DEFAULT_PREDICATES))
    followup.add_argument("--conventions", action="append", default=[])
    check = commands.add_parser("validate")
    check.add_argument("--selection", required=True)
    check.add_argument("--decisions", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.alignment, args.output)
    elif args.command == "prepare-followup":
        result = prepare_followup(
            args.alignment, args.old_selection, args.old_decisions, args.output,
            predicates=tuple(args.predicates.split(",")), conventions=args.conventions)
    else:
        result = validate(args.selection, args.decisions)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
