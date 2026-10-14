from collections import Counter

import dgl
import pytest
import torch

from scripts.DFG.experiments.audit.ddg_diagnostics_v1.rewiring import rewire_ddg


def graph_and_metadata():
    graph = dgl.heterograph({
        ("s", "DATA_DEF_USE", "s"): ([0, 1, 2, 3, 8, 9, 10, 11], [4, 5, 6, 7, 12, 13, 14, 15]),
        ("s", "next", "s"): ([0, 0, 1, 8], [4, 4, 5, 12]),
    }, num_nodes_dict={"s": 16})
    graph.nodes["s"].data["inp"] = torch.arange(32).reshape(16, 2).float()
    graph.nodes["s"].data["label"] = torch.arange(16) % 2
    for i, c in enumerate(graph.canonical_etypes):
        graph.edges[c].data["id"] = torch.full((graph.num_edges(c),), i, dtype=torch.long)
    return graph, {"s": ["a.sol"]*8 + ["b.sol"]*8}, {"s": ["fa"]*8 + ["fb"]*8}


@pytest.mark.parametrize("seed", [101, 102, 103])
def test_rewiring_preserves_canonical_degrees_function_file_and_base_parallel(seed):
    graph, files, functions = graph_and_metadata()
    result, audit = rewire_ddg(graph, files, functions, seed=seed)
    assert result is not graph
    assert result.canonical_etypes == graph.canonical_etypes
    assert result.ntypes == graph.ntypes
    for c in graph.canonical_etypes:
        old = list(zip(*[x.tolist() for x in graph.edges(etype=c)]))
        new = list(zip(*[x.tolist() for x in result.edges(etype=c)]))
        assert len(old) == len(new)
        assert torch.equal(result.edges[c].data["id"], graph.edges[c].data["id"])
        if c[1] == "next":
            assert new == old  # EID order and parallel base edges stay exact.
        else:
            assert Counter(a for a, b in old) == Counter(a for a, b in new)
            assert Counter(b for a, b in old) == Counter(b for a, b in new)
            assert len(set(new)) == len(new)
            for a, b in new:
                assert a != b
                assert files["s"][a] == files["s"][b]
                assert functions["s"][a] == functions["s"][b]
    assert audit["labels_read"] is False
    assert audit["replaced_semantic_edges"] > 0
    assert torch.equal(graph.nodes["s"].data["inp"], result.nodes["s"].data["inp"])
    # Cloned data must not alias frozen input tensors.
    result.nodes["s"].data["inp"][0, 0] = -999
    assert graph.nodes["s"].data["inp"][0, 0] == 0


def test_rewiring_is_seed_reproducible_and_label_independent():
    graph, files, functions = graph_and_metadata()
    one, first = rewire_ddg(graph, files, functions, seed=101)
    graph.nodes["s"].data["label"] = 1 - graph.nodes["s"].data["label"]
    two, second = rewire_ddg(graph, files, functions, seed=101)
    assert first == second
    for c in graph.canonical_etypes:
        assert all(torch.equal(x, y) for x, y in zip(one.edges(etype=c), two.edges(etype=c)))


def test_unknown_function_group_frozen_not_counted_successful():
    graph, files, functions = graph_and_metadata()
    functions["s"] = [None]*16
    result, audit = rewire_ddg(graph, files, functions)
    assert audit["unknown_or_mismatched_function_edges"] == 8
    assert audit["replaced_semantic_edges"] == 0
    assert audit["groups_with_semantic_perturbation"] == 0
    assert all(not r["effective_semantic_perturbation"] for r in audit["group_details"])
    for c in graph.canonical_etypes:
        assert all(torch.equal(x, y) for x, y in zip(graph.edges(etype=c), result.edges(etype=c)))


def test_unrewirable_entry_star_reported_honestly():
    graph = dgl.heterograph({("s", "DATA_DEF_USE", "s"): ([0, 0, 0], [1, 2, 3])})
    result, audit = rewire_ddg(graph, {"s": ["a"]*4}, {"s": ["f"]*4})
    assert audit["group_details"][0]["reason"] == "single_unique_source"
    assert audit["group_details"][0]["attempts"] == 0
    assert audit["semantic_perturbation_fraction"] == 0


def test_no_ddg_and_misaligned_metadata():
    graph = dgl.heterograph({("s", "next", "s"): ([0, 1], [1, 0])})
    result, audit = rewire_ddg(graph, {"s": ["a", "a"]}, {"s": ["f", "f"]})
    assert audit["ddg_edges"] == 0
    assert all(torch.equal(x, y) for x, y in zip(graph.edges(), result.edges()))
    with pytest.raises(ValueError, match="misaligned"):
        rewire_ddg(graph, {"s": ["a"]}, {"s": ["f", "f"]})
