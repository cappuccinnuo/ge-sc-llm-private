"""Synthetic, independent Prompt 8C label-view regression tests."""
import copy

import pytest

from scripts.DFG.dfg_v2.diagnostics8c.labels import (
    annotation_evidence, audit_file, compare_review, first_overlap,
    inferred_label, map_lines, node_lines, parse_buglog, strip_comments,
    truncation_evidence,
)


def row(nid, start, end=None, target=0, kind="expression_statement",
        text="x = 1;", filename="buggy_1.sol"):
    return {
        "file": filename, "original_graph_node_id": nid, "target": target,
        "node_type": kind, "graph_stored_source_lines": [
            [start] if end is None else [start, end]],
        "graph_label_anchor": text,
    }


def test_comments_preserve_string_literals_and_line_positions():
    source = 'string x = "https://x/*y*/"; // stop\n/* two\nlines */uint y=1;\n'
    stripped = strip_comments(source)
    assert '"https://x/*y*/"' in stripped
    assert "stop" not in stripped
    assert "two" not in stripped
    assert len(source) == len(stripped)
    assert source.count("\n") == stripped.count("\n")


def test_comments_preserve_escaped_quotes():
    source = 'string x = "a\\"//b"; /* no */uint x=1;'
    stripped = strip_comments(source)
    assert '"a\\"//b"' in stripped
    assert "no" not in stripped


def test_forward_match_repeated_lines_and_unmapped_audit():
    original = "// heading\nuint a = 1;\nx();\n// gap\nx();\ny();\n"
    cleaned = "uint a=1;\nx();\nunknown();\nx();\n"
    result = map_lines(original, cleaned)
    assert result["raw_to_clean"] == {2: 1, 3: 2, 5: 4}
    assert result["unmapped_cleaned"] == [{"line": 3, "normalized_text": "unknown();"}]
    assert result["unmapped_original"] == [{"line": 6, "normalized_text": "y();"}]


def test_forward_match_never_goes_backwards():
    result = map_lines("a();\nb();\n", "b();\na();\n")
    assert result["raw_to_clean"] == {2: 1}
    assert result["unmapped_cleaned_lines"] == 1


def test_comment_like_string_is_not_removed_from_mapping():
    result = map_lines('string x="a//b"; // ok\n', 'string x = "a//b";\n')
    assert result["raw_to_clean"] == {1: 1}


@pytest.mark.parametrize("kind,lines,expected", [
    ("expression_statement", {3}, 1),
    ("expression_statement", {7}, 0),
    ("contract_declaration", {3}, 0),
    ("contract_declaration", {2}, 1),
    ("library_declaration", {3}, 1),
])
def test_author_rule_is_inclusive_except_contract_start(kind, lines, expected):
    assert inferred_label(row(1, 2, 5, kind=kind), lines) == expected


def test_multiple_node_spans_are_not_merged_into_continuous_range():
    r = row(1, 1)
    r["graph_stored_source_lines"] = [[1, 2], [8, 9]]
    assert node_lines(r) == {1, 2, 8, 9}
    assert inferred_label(r, {5}) == 0


def test_invalid_spans_rejected():
    with pytest.raises(ValueError):
        node_lines(row(1, 5, 1))


def test_nested_overlap_not_only_adjacent_intervals():
    records = parse_buglog("loc,length\n5,20\n10,2\n15,2\n")
    overlap = first_overlap(records)
    assert overlap["current"]["entry"] == 2
    assert overlap["previous"][0]["entry"] == 1
    assert overlap["overlap_start"] == 10


def test_interval_inclusive_endpoint_overlap():
    overlapping = parse_buglog("loc,length\n10,4\n13,3\n")
    disjoint = parse_buglog("loc,length\n10,4\n14,3\n")
    assert first_overlap(overlapping)["overlap_start"] == 13
    assert first_overlap(disjoint) is None


def test_truncation_uses_missing_positives_not_all_disagreements():
    rows = [row(i, i, target=0) for i in range(1, 22)]
    truth = {i: 1 for i in range(1, 22)}
    mapping = {i: i for i in range(1, 50)}
    assert truncation_evidence(rows, truth, mapping, [])["truncated"]
    rows[-1]["target"] = 1
    assert not truncation_evidence(rows, truth, mapping, [])["truncated"]
    extra = [row(i, i, target=1) for i in range(22, 45)]
    truth.update({i: 0 for i in range(22, 45)})
    result = truncation_evidence(rows + extra, truth, mapping, [])
    assert len(result["excess_positive_nodes"]) == 23
    assert not result["truncated"]


def test_positive_node_start_not_mistaken_for_full_span_or_attached_cutoff():
    rows = [row(1, 5, 8, target=1, kind="function_definition")]
    result = truncation_evidence(rows, {1: 1}, {x: x for x in range(1, 10)},
                                [], [5, 50])
    assert result["last_positive_node_start_raw"] == 5
    assert result["last_positive_node_covered_clean"] == 8
    assert result["last_attached_bug_line_clean"] == 50
    assert result["last_mappable_attached_bug_line_raw"] == 5


def test_missing_csv_rejected():
    with pytest.raises(ValueError, match="missing pinned BugLog"):
        audit_file("x();", "x();", [row(1, 1)], None, "re_ent")


def test_views_immutable_and_spill_evidence_explicit():
    source = "contract C {\nuint owner;\nfunction txorigin1() {\nx();\n}\n}\n"
    rows = [
        row(1, 1, 6, kind="contract_declaration", text="contract C {"),
        row(2, 2, target=1, kind="new_variable", text="uint owner;"),
        row(3, 3, 5, target=1, kind="function_definition", text="function txorigin1(){"),
        row(4, 4, target=1, text="x();"),
    ]
    before = copy.deepcopy(rows)
    result = audit_file(source, source, rows,
                        parse_buglog("loc,length\n2,4\n"), "txorigin")
    assert rows == before
    byid = {r["node_id"]: r for r in result["nodes"]}
    assert not byid[1]["C2_include"]
    assert not byid[2]["C2_include"]
    assert byid[3]["C2_include"] and byid[4]["C2_include"]
    assert byid[4]["lexical_prediction"] == 1
    spill = next(s for s in result["spill_candidates"] if s["node_id"] == 2)
    assert spill["buglog_evidence"][0]["raw_lines"] == [{"line": 2, "text": "uint owner;"}]


def test_c1_only_changes_truncated_files():
    source = "\n".join("x%d();" % i for i in range(1, 23))
    rows = [row(i, i, target=0) for i in range(1, 23)]
    result = audit_file(source, source, rows, parse_buglog("loc,length\n1,22\n"), "re_ent")
    assert result["truncation"]["truncated"]
    assert sum(n["C1"] for n in result["nodes"]) == 22
    assert sum(n["orig"] for n in result["nodes"]) == 0


def test_non_solidifi_annotations_report_without_relabel_or_next_line_guess():
    source = "/* @vulnerable_at_lines: 4 */\n// <yes> <report>\nuint x;\nx();\n"
    cleaned = "uint x;\nx();\n"
    rows = [row(1, 1, filename="real.sol"), row(2, 2, filename="real.sol")]
    result = audit_file(source, cleaned, rows, None, "txorigin")
    assert all(n["C1"] == 0 for n in result["nodes"])
    header = next(a for a in result["annotation_evidence"] if a["annotation_kind"] == "vulnerable_at_lines")
    comment = next(a for a in result["annotation_evidence"] if a["annotation_kind"] == "yes_report_comment")
    assert header["raw_line"] == 4 and header["cleaned_line"] == 2
    assert header["nodes_covering_mapped_line"][0]["node_id"] == 2
    assert comment["cleaned_line"] is None
    assert comment["following_code_line_context_only"] == 3


def test_header_text_in_string_does_not_create_annotation():
    source = 'string x="@vulnerable_at_lines: 5";\n'
    assert annotation_evidence(source, [], {1: 1}) == []


def test_special_file_exclusion_keeps_orig_and_c1_unchanged():
    r = row(1, 1, target=1, filename="parity_wallet_bug_2.sol")
    result = audit_file("x();", "x();", [r], None, "txorigin")
    assert result["nodes"][0]["orig"] == result["nodes"][0]["C1"] == 1
    assert result["nodes"][0]["C2_include"] is False


def test_duplicate_identity_rejected():
    r = row(1, 1)
    with pytest.raises(ValueError, match="duplicate"):
        audit_file("x();", "x();", [r, r], [], "re_ent")


def test_review_comparison_retains_difference():
    ours = {"x": {"truncated_files": ["a"], "rule_agreement_non_truncated": [2, 3],
                  "per_file": {}, "scores": {}}}
    review = copy.deepcopy(ours)
    review["x"]["truncated_files"] = []
    result = compare_review(ours, review)
    assert result["status"] == "differences_retained"
    assert len(result["differences"]) == 1
    assert ours["x"]["truncated_files"] == ["a"]


def test_line_comment_with_stars_does_not_open_block_comment():
    raw = "//*****\nlibrary SafeMath {\n/** doc */\nuint x;\n"
    cleaned = "library SafeMath {\nuint x;\n"
    result = map_lines(raw, cleaned)
    assert result["raw_to_clean"] == {2: 1, 4: 2}
    assert result["unmapped_cleaned_lines"] == 0

def test_attached_null_and_literal_records():
    from scripts.DFG.dfg_v2.diagnostics8c.labels import attached_records
    class Graph:
        def nodes(self, data=False):
            return [(1, {"source_file": "a.sol", "node_info_vulnerabilities": None}),
                    (2, {"source_file": "a.sol", "node_info_vulnerabilities":
                         repr(repr([{"lines": [3, 4], "category": "c"}]))})]
    assert attached_records(Graph()) == {"a.sol": [{"lines": [3, 4], "category": "c"}]}


def test_marker_in_parameter_does_not_mark_entire_function_body():
    source = "function normal(uint txorigin_arg) {\nx();\n}\n"
    rows = [row(1, 1, 3, kind="function_definition", text="function normal(uint txorigin_arg) {"),
            row(2, 2, text="x();")]
    result = audit_file(source, source, rows, [], "txorigin")
    assert result["nodes"][0]["lexical_prediction"] == 1
    assert result["nodes"][1]["lexical_prediction"] == 0

def test_frozen_target_mismatch_rejected():
    from scripts.DFG.dfg_v2.diagnostics8c.labels import verify_frozen_labels
    class Graph:
        nodes = {1: {"source_file": "buggy_1.sol", "node_type": "expression_statement",
                     "node_info_vulnerabilities": None, "node_source_code_lines": [[1]]}}
    assert verify_frozen_labels(Graph(), [row(1, 1)]) == 1
    with pytest.raises(ValueError, match="target"):
        verify_frozen_labels(Graph(), [row(1, 1, target=1)])
