"""Unit tests for hcg: schema, annotations, labels, features, I/O. No network."""
import csv
import hashlib

import networkx as nx
import numpy as np
import pytest

from hcg.cfg import author_schema as schema
from hcg.features import tokens
from hcg.labels import projection
from hcg.sources import annotations as ann
from hcg.store import io


# ----------------------------------------------------------- authors' schema --
@pytest.mark.parametrize("text", ['plain', 'two\nlines', 'say "hi"', ''])
def test_quote_round_trip(text):
    quoted = schema.quote(text)
    assert quoted.startswith('"') and quoted.endswith('"') and "\n" not in quoted
    assert schema.unquote(quoted) == text


def test_quote_leaves_backslashes_like_the_authors():
    # The authors' encoding does not escape backslashes, so a literal backslash-n in
    # code is indistinguishable from an escaped newline; quote() reproduces that.
    assert schema.quote('a\\nb') == '"a\\nb"'


def test_quote_matches_authors_example():
    assert schema.quote('if (a == 0) {\n  return 0;\n}') == '"if (a == 0) {\\n  return 0;\\n}"'


def test_endpoints_and_labels():
    assert schema.endpoints("30-if-4-6", "if") == [[4, 6]]
    assert schema.endpoints("3_ end_if-6-6", "end_if") == [[3]]
    assert schema.author_label("3_ end_if-6-6", "end_if") == "3_ end_if"
    assert schema.author_label("7_ x = 1;\n12-expression_statement-9-9", "expression_statement") \
        == "7_ x = 1;\n12-expression_statement-9-9"
    assert schema.label_endpoints([[4, 9]]) == [4, 9]
    assert schema.label_endpoints([[3]]) == [3]
    with pytest.raises(ValueError):
        schema.endpoints("no range here", "expression_statement")


def test_site_table_is_a_function_and_unknown_sites_fail():
    assert schema.author_edge_names("L231", "if_true") == ("pos_next", "pos_next")
    assert schema.author_edge_names("L627", "next") == ("loop_update", "next_line")
    with pytest.raises(schema.UnmappedEdge):
        schema.author_edge_names("L864", "next")
    edge_types = {v[1] for v in schema.SITE_TABLE.values()}
    assert edge_types == {"first_next_line", "pos_next", "neg_next", "recursive_method_call",
                          "internal_call", "external_call", "next_line", "end_if"}


def test_builder_file_is_the_pinned_one():
    from hcg.cfg.builder import _CFG_DIR
    digest = hashlib.sha256((_CFG_DIR / "CFG_solidity.py").read_bytes()).hexdigest()
    assert digest == schema.CFG_SOLIDITY_SHA256


# --------------------------------------------------------------- annotations --
SOURCE = "pragma solidity ^0.4.24;\n\n// comment line\ncontract C {\n  uint x; /* c */\n\n  function f() {\n    x = 1; // set\n  }\n}\n"


def test_preprocess_with_map_tracks_original_lines():
    text, line_map = ann.preprocess_with_map(SOURCE)
    assert text == ann.preprocess(SOURCE)
    assert text.split("\n")[1] == "contract C {"
    assert line_map == [[1], [4], [5], [7], [8], [9], [10]]


def test_project_maps_original_to_preprocessed_lines():
    _, line_map = ann.preprocess_with_map(SOURCE)
    assert ann.project([{"category": "c", "lines": [3, 8]}], line_map) == \
        [{"category": "c", "lines": [5]}]


def test_buglog_merges_intervals(tmp_path):
    source = tmp_path / "buggy_1.sol"
    source.write_text("\n".join("line %d" % i for i in range(1, 21)))
    log = tmp_path / "BugLog_1.csv"
    with open(log, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["loc", "length", "bug type", "approach"])
        writer.writerows([[3, 2, "x", "y"], [4, 3, "x", "y"], [10, 1, "x", "y"]])
    records, rows = ann._buglog_record(log, source, "cat")
    assert rows == 3 and records == [{"category": "cat", "lines": [3, 4, 5, 6, 10]}]


def test_compare_sources_allows_comments_only(tmp_path):
    a, b, c = tmp_path / "a.sol", tmp_path / "b.sol", tmp_path / "c.sol"
    a.write_text("contract C {\n  uint x; // one\n}\n")
    b.write_text("contract C {\n  uint x; // two\n}\n")
    c.write_text("contract C {\n  uint y;\n}\n")
    assert ann.compare_sources(a, b)["source_comparison"] == "comments_or_blank_lines_only"
    with pytest.raises(ValueError):
        ann.compare_sources(a, c)


# -------------------------------------------------------------------- labels --
def _graph():
    g = nx.MultiDiGraph(name="G")
    g.add_node(0, source_file="a.sol", node_type="function_definition",
               node_source_code_lines=[[2, 6]])
    g.add_node(1, source_file="a.sol", node_type="expression_statement",
               node_source_code_lines=[[4, 4]])
    g.add_node(2, source_file="a.sol", node_type="end_if", node_source_code_lines=[[0]])
    g.add_node(3, source_file="b.sol", node_type="expression_statement",
               node_source_code_lines=[[2, 2]])
    g.add_edge(0, 1, key="0", edge_type="next_line")
    return g


TEXTS = {"a.sol": ["contract A {", "function f(", "uint x", ") public {", "g(", "}"],
         "b.sol": ["contract B {", "h();", "}"]}


def test_label_nodes_uses_endpoints_not_full_range():
    g = _graph()
    projected = {"a.sol": [{"category": "c", "lines": [4]}], "b.sol": []}
    positives, reached = projection.label_nodes(g, projected, TEXTS)
    assert positives == 1 and reached["a.sol"] == dict(endpoint=1, statement=0, header=0, unreached=0)
    assert g.nodes[0]["node_info_vulnerabilities"] is None   # 4 is inside, not an endpoint
    assert g.nodes[1]["node_info_vulnerabilities"] == schema.quote("[{'category': 'c', 'lines': [4]}]")
    assert g.nodes[2]["node_info_vulnerabilities"] is None   # marker 0 is allowed


def _statement_graph():
    g = nx.MultiDiGraph(name="G")
    g.add_node(0, source_file="a.sol", node_type="function_definition", node_source_code_lines=[[2, 6]])
    g.add_node(1, source_file="a.sol", node_type="expression_statement", node_source_code_lines=[[5, 6]])
    g.add_node(2, source_file="a.sol", node_type="contract_declaration", node_source_code_lines=[[1, 6]])
    g.add_node(3, source_file="b.sol", node_type="expression_statement", node_source_code_lines=[[2, 2]])
    return g


@pytest.mark.parametrize("line, rule, vulnerable, step", [
    (3, "endpoints", [], "unreached"),            # a parameter line: no endpoint
    (3, "statement", [0], "header"),              # ... belongs to the function's header
    (4, "statement", [0], "header"),              # the line opening the body is still header
    (5, "statement", [1], "endpoint"),
    (6, "statement", [0, 1, 2], "endpoint"),      # endpoints hit as before
])
def test_statement_rule_maps_a_line_to_the_node_it_belongs_to(line, rule, vulnerable, step):
    g = _statement_graph()
    projected = {"a.sol": [{"category": "c", "lines": [line]}], "b.sol": []}
    positives, reached = projection.label_nodes(g, projected, TEXTS, rule)
    assert sorted(n for n, d in g.nodes(data=True) if d["node_info_vulnerabilities"]) == vulnerable
    assert positives == len(vulnerable) and reached["a.sol"][step] == 1


def test_statement_rule_prefers_the_smallest_statement_and_never_labels_a_body_line_on_its_declaration():
    g = _statement_graph()
    g.add_node(4, source_file="a.sol", node_type="if", node_source_code_lines=[[4, 6]])
    g.nodes[1]["node_source_code_lines"] = [[4, 6]]
    g.add_node(5, source_file="a.sol", node_type="expression_statement", node_source_code_lines=[[5, 5]])
    g.nodes[5]["node_source_code_lines"] = [[4, 5]]
    # line 5: endpoint of node 5 only
    _, reached = projection.label_nodes(g, {"a.sol": [{"category": "c", "lines": [5]}], "b.sol": []}, TEXTS,
                                        "statement")
    assert [n for n, d in g.nodes(data=True) if d["node_info_vulnerabilities"]] == [5]
    g.remove_node(5)
    g.nodes[4]["node_source_code_lines"] = [[4, 6]]
    g.nodes[1]["node_source_code_lines"] = [[4, 6]]
    g.add_node(6, source_file="a.sol", node_type="if", node_source_code_lines=[[4, 6]])
    projection.label_nodes(g, {"a.sol": [{"category": "c", "lines": [5]}], "b.sol": []}, TEXTS, "statement")
    assert [n for n, d in g.nodes(data=True) if d["node_info_vulnerabilities"]] == [1]   # smallest, lowest id
    g = _statement_graph()
    g.remove_node(1)
    _, reached = projection.label_nodes(g, {"a.sol": [{"category": "c", "lines": [5]}], "b.sol": []}, TEXTS,
                                        "statement")
    assert all(d["node_info_vulnerabilities"] is None for _, d in g.nodes(data=True))
    assert reached["a.sol"]["unreached"] == 1


def test_reached_summary_totals_overall_and_per_source():
    reached = {"a.sol": dict(endpoint=2, statement=1, header=0, unreached=1),
               "b.sol": dict(endpoint=1, statement=0, header=1, unreached=0),
               "c.sol": dict.fromkeys(projection.STEPS, 0)}
    out = projection.reached_summary(reached, {"a.sol": "X", "b.sol": "Y", "c.sol": "Z"})
    assert out["all"] == dict(endpoint=3, statement=1, header=1, unreached=1)
    assert out["X"]["unreached"] == 1 and out["Y"]["header"] == 1 and "Z" not in out


def test_label_nodes_rejects_out_of_bounds_and_unknown_rules():
    g = _graph()
    with pytest.raises(ValueError):
        projection.label_nodes(g, {"a.sol": [], "b.sol": []}, {"a.sol": ["x"] * 3, "b.sol": ["x"] * 3})
    with pytest.raises(ValueError, match="unknown node-label rule"):
        projection.label_nodes(g, {"a.sol": [], "b.sol": []}, TEXTS, "range")


def test_line_level_keeps_target_contracts_and_renumbers():
    g = _graph()
    sub, old = projection.line_level(g, {"a.sol": 1, "b.sol": 0})
    assert old == [0, 1, 2] and sorted(sub.nodes()) == [0, 1, 2]
    assert sub.graph == {"name": "G"} and sub.number_of_edges() == 1


def test_training_consumer_reads_quoted_labels():
    pytest.importorskip("dgl")
    from mando.models.graph_utils import get_node_label
    g = _graph()
    projection.label_nodes(g, {"a.sol": [{"category": "c", "lines": [4]}], "b.sol": []}, TEXTS)
    targets, _, _ = get_node_label(g)
    assert list(targets) == [0, 1, 0, 0]


# ------------------------------------------------------------ features / io --
def test_encode_ids_matches_existing_encoder():
    def original(ids, size, pad_id):
        """encode_ids of the former scripts/encode_tokenizer_features.py (archive branch), verbatim."""
        out = np.full(size, pad_id, dtype=np.float32)
        n = min(len(ids), size)
        if n:
            out[:n] = np.asarray(ids[:n], dtype=np.float32)
        return out

    for ids in ([], [5, 6, 7], list(range(600))):
        assert np.array_equal(tokens.encode_ids(ids, 512, 0), original(ids, 512, 0))


def test_gpickle_protocol_4(tmp_path):
    path = tmp_path / "g.gpickle"
    io.write_gpickle(_graph(), path)
    assert path.read_bytes()[:2] == b"\x80\x04"
    assert io.read_gpickle(path).nodes[1]["node_type"] == "expression_statement"


# ----------------------------------------------------------------------- cli --
def test_cli_accepts_label_root_after_the_subcommand(tmp_path):
    from hcg.__main__ import build_parser
    args = build_parser().parse_args(["build", "--label-root", str(tmp_path), "--no-tokens"])
    assert args.label_root == tmp_path and args.no_tokens
    assert build_parser().parse_args(["fetch", "--label-root", str(tmp_path)]).command == "fetch"


def test_cli_rejects_unknown_category():
    from hcg.__main__ import main
    with pytest.raises(SystemExit, match="unknown categories"):
        main(["build", "--categories", "not_a_class", "--no-tokens"])
