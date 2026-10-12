"""Nested split and semantic parameter identity regression tests (Codex)."""
import copy
import math
import pytest
import torch
from torch import nn

from scripts.DFG.experiments.protocol import (
    make_fold_document, validate_fold_document, paired_initialize, _doc_digest, _digest,
)


def labels(task):
    if task == "node":
        return {"buggy_%03d.sol" % i: 1 for i in range(30)}
    return {"contract_%03d.sol" % i: i % 2 for i in range(40)}


@pytest.mark.parametrize("task,k", [("node", 10), ("contract", 5)])
def test_splits_deterministic_exhaustive_nested(task, k):
    a = make_fold_document(labels(task), task, "a" * 64, seed=7)
    b = make_fold_document(dict(reversed(list(labels(task).items()))), task,
                           "a" * 64, seed=7)
    assert a == b
    assert len(a["folds"]) == k
    assert validate_fold_document(a) is a
    heldout = []
    for fold in a["folds"]:
        tr, va, te = (set(fold[x]) for x in
                      ("inner_train_files", "inner_val_files", "outer_test_files"))
        assert not tr & va and not tr & te and not va & te
        assert tr | va | te == set(a["files"])
        heldout.extend(te)
    assert sorted(heldout) == a["files"]


def test_changed_seed_changes_fixed_split():
    assert make_fold_document(labels("node"), "node", "a" * 64, seed=1)["split_sha256"] != \
        make_fold_document(labels("node"), "node", "a" * 64, seed=2)["split_sha256"]


def test_hash_and_leakage_rejected_even_with_recomputed_hash():
    doc = make_fold_document(labels("node"), "node", "a" * 64)
    bad = copy.deepcopy(doc)
    bad["seed"] = 99
    with pytest.raises(ValueError, match="hash"):
        validate_fold_document(bad)
    bad = copy.deepcopy(doc)
    bad["folds"][0]["inner_train_files"].append(bad["folds"][0]["outer_test_files"][0])
    bad["folds"][0]["inner_train_files"].sort()
    bad["split_sha256"] = _doc_digest(bad)
    with pytest.raises(ValueError, match="overlap"):
        validate_fold_document(bad)


@pytest.mark.parametrize("mutation", ["duplicate", "omit", "repeated_outer"])
def test_invalid_population_partitions_rejected(mutation):
    doc = make_fold_document(labels("node"), "node", "a" * 64)
    if mutation == "duplicate":
        tr = doc["folds"][0]["inner_train_files"]
        tr.append(tr[0])
        tr.sort()
    elif mutation == "omit":
        doc["folds"][0]["inner_val_files"].pop()
    else:
        doc["folds"][1] = copy.deepcopy(doc["folds"][0])
        doc["folds"][1]["fold"] = 1
    doc["split_sha256"] = _doc_digest(doc)
    with pytest.raises(ValueError):
        validate_fold_document(doc)


def test_node_population_cannot_include_clean_contracts():
    with pytest.raises(ValueError, match="buggy"):
        make_fold_document(labels("contract"), "node", "a" * 64)


def test_graph_population_requires_both_classes_and_enough_files():
    with pytest.raises(ValueError, match="Each graph class"):
        make_fold_document(labels("node"), "contract", "a" * 64)


class FakeLayer(nn.Module):
    def __init__(self, ntypes, relations):
        super().__init__()
        for prefix in ("k_linears", "q_linears", "v_linears", "a_linears"):
            setattr(self, prefix, nn.ModuleList([nn.Linear(4, 4) for _ in ntypes]))
        self.norms = nn.ModuleList([nn.LayerNorm(4) for _ in ntypes])
        self.skip = nn.Parameter(torch.rand(len(ntypes)))
        self.relation_pri = nn.Parameter(torch.rand(len(relations), 2))
        self.relation_att = nn.Parameter(torch.rand(len(relations), 2, 2, 2))
        self.relation_msg = nn.Parameter(torch.rand(len(relations), 2, 2, 2))


class FakeModel(nn.Module):
    def __init__(self, nodes, relations):
        super().__init__()
        self.ntypes_dict = {name: i for i, name in enumerate(nodes)}
        self.etypes_dict = {name: i for i, name in enumerate(relations)}
        self.adapt_ws = nn.ModuleList([nn.Linear(8, 4) for _ in nodes])
        self.gcs = nn.ModuleList([FakeLayer(nodes, relations), FakeLayer(nodes, relations)])
        self.classify = nn.Linear(4, 2)


A = ("assignment", "next", "return")
B = ("return", "next", "assignment")
DDG = ("assignment", "DATA_DEF_USE", "return")


def models():
    return (FakeModel(["assignment", "return"], [A, B]),
            FakeModel(["return", "assignment"], [DDG, B, A]))


def test_paired_semantic_parameters_with_permuted_type_and_relation_ids():
    torch.manual_seed(9)
    a, b = models()
    before = {k: v.clone() for k, v in a.state_dict().items()}
    audit = paired_initialize(a, b, seed=17)
    for name, value in a.state_dict().items():
        assert torch.equal(value, before[name]), name
    for node in a.ntypes_dict:
        i, j = a.ntypes_dict[node], b.ntypes_dict[node]
        for suffix in ("weight", "bias"):
            assert torch.equal(getattr(a.adapt_ws[i], suffix), getattr(b.adapt_ws[j], suffix))
        for la, lb in zip(a.gcs, b.gcs):
            assert torch.equal(la.skip[i], lb.skip[j])
            for prefix in ("k_linears", "q_linears", "v_linears", "a_linears", "norms"):
                for suffix in ("weight", "bias"):
                    assert torch.equal(getattr(getattr(la, prefix)[i], suffix),
                                       getattr(getattr(lb, prefix)[j], suffix))
    for edge in a.etypes_dict:
        for la, lb in zip(a.gcs, b.gcs):
            for key in ("relation_pri", "relation_att", "relation_msg"):
                assert torch.equal(getattr(la, key)[a.etypes_dict[edge]],
                                   getattr(lb, key)[b.etypes_dict[edge]])
    assert torch.equal(a.classify.weight, b.classify.weight)
    assert torch.equal(a.classify.bias, b.classify.bias)
    assert audit["new_canonical_relations"] == [list(DDG)]
    assert audit["e1_parameters"] > audit["e0_parameters"]


def test_new_relation_initialization_isolated_from_rng_and_construction_order():
    torch.manual_seed(123)
    a, b = models()
    before_rng = torch.get_rng_state().clone()
    audit1 = paired_initialize(a, b, seed=35)
    assert torch.equal(torch.get_rng_state(), before_rng)
    torch.manual_seed(987)
    c = FakeModel(["assignment", "return"], [A, DDG, B])
    audit2 = paired_initialize(a, c, seed=35)
    assert audit1["shared_semantic_sha256"] == audit2["shared_semantic_sha256"]
    assert audit1["new_relations_sha256"] == audit2["new_relations_sha256"]
    for lb, lc in zip(b.gcs, c.gcs):
        for key in ("relation_pri", "relation_att", "relation_msg"):
            assert torch.equal(getattr(lb, key)[b.etypes_dict[DDG]],
                               getattr(lc, key)[c.etypes_dict[DDG]])
    other = FakeModel(["assignment", "return"], [A, DDG, B])
    audit3 = paired_initialize(a, other, seed=36)
    assert audit1["new_relations_sha256"] != audit3["new_relations_sha256"]


def test_pair_rejects_missing_node_type():
    a, b = models()
    b.ntypes_dict = {"return": 0}
    with pytest.raises(ValueError, match="node type"):
        paired_initialize(a, b)


def test_pair_rejects_removed_base_relation():
    a = FakeModel(["assignment", "return"], [A, B])
    b = FakeModel(["assignment", "return"], [A, DDG])
    with pytest.raises(ValueError, match="removed"):
        paired_initialize(a, b)


def test_pair_rejects_additional_non_ddg_relation():
    a = FakeModel(["assignment", "return"], [A])
    b = FakeModel(["assignment", "return"], [A, B])
    with pytest.raises(ValueError, match="Only forward"):
        paired_initialize(a, b)


def test_pair_rejects_already_enhanced_baseline():
    a = FakeModel(["assignment", "return"], [A, DDG])
    b = FakeModel(["assignment", "return"], [A, DDG])
    with pytest.raises(ValueError, match="unenhanced"):
        paired_initialize(a, b)


def test_new_relation_uses_native_full_bank_xavier_distribution():
    a, b = models()
    paired_initialize(a, b, seed=19)
    for layer_index, layer in enumerate(b.gcs):
        for kind in ("att", "msg"):
            name = "gcs.%d.relation_%s" % (layer_index, kind)
            bank = getattr(layer, "relation_" + kind)
            fan_in, fan_out = torch.nn.init._calculate_fan_in_and_fan_out(bank)
            bound = math.sqrt(6.0 / float(fan_in + fan_out))
            isolated_seed = int(_digest([19, name, DDG])[:15], 16)
            expected = torch.empty_like(bank[b.etypes_dict[DDG]])
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(isolated_seed)
                expected.uniform_(-bound, bound)
            assert torch.equal(bank[b.etypes_dict[DDG]], expected)
            assert float(expected.abs().max()) <= bound
