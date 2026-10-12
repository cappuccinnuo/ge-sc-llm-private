import copy
from types import SimpleNamespace
import numpy as np
import pytest
from scripts.DFG.experiments.prepare import (
    build_pairs, check_labels, coverage, verify_features, verify_raw, positive)
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.tests.test_projection import assets, SOURCE
from scripts.encode_tokenizer_features import encode_ids


class Tokenizer:
    pad_token_id = 0
    eos_token_id = 2
    def __call__(self, code, add_special_tokens):
        assert add_special_tokens
        return SimpleNamespace(input_ids=[1] + [ord(c) for c in code] + [2])


def featured():
    graph, _ = assets()
    tok = Tokenizer()
    for n, d in graph.nodes(data=True):
        d["token"] = encode_ids(tok(d.get("code") or "", True).input_ids, 512, 0)
        d["node_info_vulnerabilities"] = None
    graph.nodes[next(iter(graph))]["node_info_vulnerabilities"] = [{"category": "reentrancy", "lines": [1]}]
    return graph


def test_all_features_recomputed_without_mutation():
    g = featured()
    before = fingerprint(g)
    report = verify_features(g, Tokenizer())
    assert report["verified_nodes"] == len(g)
    assert fingerprint(g) == before
    g.nodes[next(iter(g))]["token"][4] += 1
    with pytest.raises(ValueError, match="differs"):
        verify_features(g, Tokenizer())


@pytest.mark.parametrize("bad", [np.zeros(512, dtype=np.float64),
                                  np.zeros(10, dtype=np.float32),
                                  np.full(512, np.nan, dtype=np.float32)])
def test_invalid_feature_rejected(bad):
    g = featured()
    g.nodes[next(iter(g))]["token"] = bad
    with pytest.raises(ValueError, match="float32"):
        verify_features(g, Tokenizer())


def test_graph_labels_exact_and_clean_positive_rejected():
    g = featured()
    assert check_labels(g, [{"contract_name": "a.sol", "targets": 1}]) == {"a.sol": 1}
    for labels in ([{"contract_name": "a.sol", "targets": 0}],
                   [{"contract_name": "b.sol", "targets": 1}],
                   [{"contract_name": "a.sol", "targets": 1}] * 2):
        with pytest.raises(ValueError):
            check_labels(g, labels)
    with pytest.raises(ValueError):
        positive({"node_info_vulnerabilities": "malformed"})


def test_raw_graph_preserved_except_existing_features():
    g = featured()
    raw = copy.deepcopy(g)
    for _, d in raw.nodes(data=True):
        del d["token"]
    assert verify_raw(raw, g)
    g.nodes[next(iter(g))]["node_info_vulnerabilities"] = None
    with pytest.raises(ValueError, match="attributes"):
        verify_raw(raw, g)


def test_pair_adds_edges_keeps_ids_labels_features_and_buggy_population():
    g = featured()
    # Add a separate clean file with a deliberately nonconsecutive ID.
    g.add_node(99999, source_file="clean.sol", node_type="expression_statement",
               code="x;", label="not-an-anchor", token=np.zeros(512, dtype=np.float32),
               node_info_vulnerabilities=None)
    before = fingerprint(g)
    pairs, audit, inv = build_pairs(g, {"a.sol": SOURCE}, {"a.sol": 1, "clean.sol": 0})
    assert fingerprint(g) == before == fingerprint(pairs["E0"]["contract"])
    assert inv["contract"]["ddg_edges"] > 0
    assert 99999 in pairs["E1"]["contract"] and 99999 not in pairs["E1"]["node"]
    assert list(pairs["E0"]["node"]) == [n for n in g if n != 99999]
    report = coverage(g, pairs["E1"]["contract"], audit, {"a.sol": SOURCE})
    assert report["all_samples_retained"]
    assert report["files_total"] == 2 and report["files_with_ddg"] == 1
    assert report["functions_supported"] > 0
    assert report["diagnostic_kinds"]["file_fallback"] == 1


def test_all_fallback_is_retained_not_invented_ddg():
    g = featured()
    pairs, audit, inv = build_pairs(g, {}, {"a.sol": 1})
    assert fingerprint(pairs["E0"]["contract"]) == fingerprint(pairs["E1"]["contract"])
    assert inv["contract"]["ddg_edges"] == 0
    report = coverage(g, pairs["E1"]["contract"], audit, {})
    assert report["functions_supported"] == 0 and report["files_with_ddg"] == 0

def test_author_serialized_annotation_read_without_mutation():
    d = {"node_info_vulnerabilities": "[{'category': 'reentrancy', 'lines': [4]}]"}
    before = copy.deepcopy(d)
    assert positive(d) == 1
    assert d == before
    assert positive({"node_info_vulnerabilities": repr(d["node_info_vulnerabilities"])}) == 1
    assert positive({"node_info_vulnerabilities": "None"}) == 0
    assert positive({"node_info_vulnerabilities": "[]"}) == 0
