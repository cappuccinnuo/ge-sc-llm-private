"""Statement-unit counting and explicit v3-to-v4 provenance; comparator only."""
import copy
from collections import defaultdict


def normalize_l2_units(lexical, raw):
    # Local import keeps the existing lexical normalizer available for replay.
    from .slither_align import _id, _ordered, _span
    groups = {}
    for event in lexical:
        for evidence in event["evidence"]:
            statement = evidence.get("statement")
            occurrence = _span(evidence["occurrence"], len(raw))
            if statement is None:
                # No invented enclosing statement: keep this occurrence alone.
                unit = ("occurrence_fallback", evidence.get("file"),
                        tuple(occurrence), evidence.get("callable"))
                anchor = occurrence
            else:
                anchor = _span(statement, len(raw))
                unit = ("statement", statement.get("file"), tuple(anchor),
                        statement.get("role"), evidence.get("callable"))
            key = (unit, event["name"], event["kind"])
            if key not in groups:
                item = copy.deepcopy(event)
                item.update(event_id=_id(("v2", "L2", key)), unit_identity=unit,
                            span=list(anchor), evidence=[], tags=[],
                            lexical_event_ids=[], occurrence_spans=[],
                            anchor_rule="statement" if statement else "occurrence_fallback")
                groups[key] = item
            item = groups[key]
            if (item["declaration"] != event["declaration"] or
                    item["function_start"] != event["function_start"]):
                raise ValueError("Ambiguous declaration in one L2 statement/name/kind unit")
            if evidence not in item["evidence"]:
                item["evidence"].append(evidence)
            if event["event_id"] not in item["lexical_event_ids"]:
                item["lexical_event_ids"].append(event["event_id"])
            if occurrence not in item["occurrence_spans"]:
                item["occurrence_spans"].append(occurrence)
            item["tags"] = sorted(set(item["tags"]) | set(event["tags"]))
            if occurrence[0] < item["span"][0] or occurrence[1] > item["span"][1]:
                item["span"] = [min(item["span"][0], occurrence[0]),
                                max(item["span"][1], occurrence[1])]
                item["anchor_rule"] = "statement_occurrence_union_fallback"
    for item in groups.values():
        item["line"] = raw[:item["span"][0]].count(b"\n") + 1
        item["source_text"] = raw[item["span"][0]:item["span"][1]].decode("utf8")
        item["lexical_event_ids"].sort()
        item["occurrence_spans"].sort()
    return _ordered(list(groups.values()))


def unit_comparison(lexical, units, reference, matches, old_extra):
    """Attribute v3 FP removal to collapse versus changed matching anchors.

    Re-run the *unchanged* old lexical matcher to verify the sealed old IDs.
    A unit with a matched old lexical member and an unmatched duplicate
    specifically proves duplicated counting, rather than mere span expansion.
    """
    from .slither_align import match_spans, metrics
    old_matches, lexical_extra, _ = match_spans(lexical, reference)
    expected = {d["event_id"] for d in old_extra}
    if expected != {e["event_id"] for e in lexical_extra}:
        raise ValueError("v3 lexical FP identities do not replay exactly")
    old_matched = {c["event_id"] for c, _ in old_matches}
    matched = {c["event_id"] for c, _ in matches}
    members = defaultdict(list)
    for unit in units:
        for old_id in unit["lexical_event_ids"]:
            members[old_id].append(unit)
    rows = []
    for old in old_extra:
        linked = members[old["event_id"]]
        if len(linked) != 1:
            raise ValueError("Old lexical event lacks unique unit provenance")
        unit = linked[0]
        resolved = unit["event_id"] in matched
        has_old_match = bool(set(unit["lexical_event_ids"]) & old_matched)
        rows.append(dict(old_difference_id=old["difference_id"],
                         old_event_id=old["event_id"], unit_event_id=unit["event_id"],
                         unit_span=unit["span"], lexical_event_ids=unit["lexical_event_ids"],
                         resolved=resolved,
                         reason=("duplicate_in_previously_matched_unit" if resolved and has_old_match
                                 else "statement_anchor_or_matching_change" if resolved
                                 else "unit_still_unmatched")))
    return dict(lexical_metrics=metrics(lexical, reference, old_matches),
                unit_metrics=metrics(units, reference, matches),
                removed_lexical_event_count=len(lexical)-len(units),
                old_fp_count=len(rows), resolved_old_fp_count=sum(r["resolved"] for r in rows),
                duplicate_counting_resolved=sum(r["reason"]=="duplicate_in_previously_matched_unit" for r in rows),
                anchor_or_matching_resolved=sum(r["reason"]=="statement_anchor_or_matching_change" for r in rows),
                old_fp_resolution=rows,
                units=[{k:e[k] for k in ("event_id", "span", "name", "kind",
                    "declaration", "unit_identity", "lexical_event_ids",
                    "occurrence_spans", "anchor_rule")} for e in units])
