"""Prompt 8E regression checks: fixed policy, strict identities, no model fits."""
import copy
from collections import Counter

import pytest

from scripts.DFG.dfg_v2.benchmark_v2.real_names import (
    inspect_source, build_pool, make_mapping, verify_rewrite, excluded)
from scripts.DFG.dfg_v2.benchmark_v2.leakage_probes import (
    fit_name_memory, p2_fold, p2_all, p1, p3_samples, run_p3, name_set)

SOURCE = """pragma solidity ^0.5.0;
contract C {
  uint vault;
  struct Data { uint quantity; }
  event Paid(uint payment);
  modifier allowed() { _; }
  function ordinary(uint amount) public { uint result = amount; vault = result; }
  uint funds_re_ent;
  function withdraw_re_ent(uint amount_re_ent) public {
    uint temp_re_ent = amount_re_ent; funds_re_ent = temp_re_ent;
  }
}"""
POOL = """pragma solidity ^0.5.0;
contract Other {
 uint stored; struct Data { uint lengthOfOrder; }
 event Completed(uint units); modifier permitted() { _; }
 function process(uint inputAmount) public { uint saved = inputAmount; stored = saved; }
}"""


def test_role_pool_includes_struct_member_and_excludes_injection_scope():
    a, b = inspect_source(SOURCE), inspect_source(POOL)
    pool = build_pool({"a": a, "b": b})
    for role, name in (("function", "ordinary"), ("state", "vault"),
                       ("local", "result"), ("parameter", "amount"),
                       ("field", "quantity"), ("event", "Paid"), ("modifier", "allowed")):
        assert pool["roles"][role][name] > 0
    assert not any("re_ent" in n for role in pool["roles"].values() for n in role)


@pytest.mark.parametrize("word", ["msg", "require", "now", "uint256", "id12",
                                 "foo_txorigin", "funds_re_ent", "balance"])
def test_builtin_marker_and_placeholder_exclusions(word):
    assert excluded(word)


def test_mapping_deterministic_role_correct_and_collision_free():
    inv = inspect_source(SOURCE)
    pool = build_pool({"source": inv, "ordinary": inspect_source(POOL)})
    first = make_mapping(inv, pool)
    assert first == make_mapping(inv, pool)
    existing = {r["word"] for r in inv["lexemes"]}
    assert not set(first["mapping"].values()) & existing
    assert len(set(first["mapping"].values())) == len(first["mapping"])
    for old, new in first["mapping"].items():
        assert new in pool["roles"][inv["marker_roles"][old]]
    changed, checks = verify_rewrite(SOURCE, first["mapping"], inv)
    assert checks["ast_topology_identical"]
    assert checks["declaration_counts"] == inv["counts"]
    assert "withdraw_re_ent" not in changed
    assert changed.count("stored") >= 2


def test_mapping_rejects_exhausted_pool():
    inv = inspect_source(SOURCE)
    with pytest.raises(ValueError, match="Insufficient"):
        make_mapping(inv, build_pool({"source": inv}))


def test_conflicting_marker_declaration_roles_rejected():
    with pytest.raises(ValueError, match="ambiguous"):
        inspect_source("contract C { uint same_re_ent; function f(uint same_re_ent) public {} }")


def test_missing_marker_declaration_rejected():
    with pytest.raises(ValueError, match="Missing"):
        inspect_source("contract C { function f() public { x_re_ent(); } }")


def test_parse_errors_rejected():
    with pytest.raises(Exception):
        inspect_source("contract C { function f( { definitely ??? }")


def test_scope_witness_mismatch_rejected():
    with pytest.raises(ValueError, match="scope identity"):
        inspect_source(SOURCE, [("withdraw_re_ent", 999, 1000)])


def test_rewrite_preserves_string_comment_and_utf8_offsets():
    source = SOURCE.replace("uint vault;", '/* 中文 */ uint vault; string text = "funds_re_ent";')
    inv = inspect_source(source)
    mapping = make_mapping(inv, build_pool({"a": inv, "b": inspect_source(POOL)}))["mapping"]
    changed, _ = verify_rewrite(source, mapping, inv)
    assert '"funds_re_ent"' in changed
    assert "/* 中文 */" in changed


def row(file, nid, own, label, fn=None):
    return dict(file=file, source_sha256=file*3, original_graph_node_id=nid,
                own_code=own, function_code=fn, orig=label, C1=label, solidifi=True)


def toy_rows():
    return [row("train", i, "shared(); shared();", int(i < 3)) for i in range(6)] + [
        row("val", 6, "valOnly();", 1),
        row("test", 7, "different();", 1, "function shared() {}"),
        row("test", 8, "testOnly();", 0)]


def fold():
    return dict(fold=0, inner_train_files=["train"], inner_val_files=["val"],
                outer_test_files=["test"])


def test_p2_counts_nodes_not_occurrences_and_accepts_exact_half():
    memory = fit_name_memory(toy_rows(), ["train"], "orig")
    assert memory["shared"] == dict(support=6, positive=3, fraction=0.5)
    assert "valOnly" not in memory and "testOnly" not in memory


def test_p2_uses_enclosing_function_and_never_test_targets_to_fit():
    rows = toy_rows()
    original = p2_fold(rows, fold(), "orig")
    changed = copy.deepcopy(rows)
    for r in changed:
        if r["file"] != "train":
            r["orig"] = 1 - r["orig"]
    alternative = p2_fold(changed, fold(), "orig")
    assert original["learned_names"] == alternative["learned_names"]
    assert [r["prediction"] for r in original["predictions"]] == [1, 0]
    assert [r["prediction"] for r in original["predictions"]] == [
        r["prediction"] for r in alternative["predictions"]]


def test_p2_duplicate_or_missing_oof_rejected():
    with pytest.raises(ValueError, match="OOF"):
        p2_all(toy_rows(), [fold(), fold()], "orig")


def test_p2_overlapping_split_rejected():
    f = fold(); f["inner_train_files"].append("test")
    with pytest.raises(ValueError, match="overlap"):
        p2_fold(toy_rows(), f, "orig")


def test_p2_names_ignore_comments_literals_builtins():
    assert name_set('require(ok); // hidden\n emit Paid("secret");') == {"ok", "Paid"}


def test_p1_requires_actual_ordinary_witness():
    inv = {"a": inspect_source(SOURCE), "b": inspect_source(POOL)}
    pool = build_pool(inv)
    mapping = make_mapping(inv["a"], pool)["mapping"]
    accepted = p1(inv, {"a": mapping}, pool)
    assert accepted["passed"] and accepted["ordinary_witness_rate"] == 1
    assert not p1(inv, {"a": {"funds_re_ent": "id45"}}, pool)["passed"]


def test_p3_file_and_duplicate_groups_are_disjoint_and_complete():
    samples = []
    for i in range(10):
        for label in (0, 1):
            samples.append(dict(file_id="test/f%d" % i, group="g%d" % (i//2),
                                role="local", original="name", name=("clear" if label else "plain")+str(i),
                                target=label))
    report = run_p3(samples, n_splits=5)
    assert report["classifier_fits"] == 5
    assert len(report["predictions"]) == 20
    for f in report["folds"]:
        assert not set(f["train_groups"]) & set(f["test_groups"])
    assert 0 <= report["auc"] <= 1


def test_p3_role_samples_not_lexical_token_counts():
    inv = inspect_source(SOURCE)
    samples = p3_samples({"task/a": inv}, {}, {"task/a": "g"})
    keys = [(r["role"], r["original"], r["target"]) for r in samples]
    assert len(set(keys)) == len(keys)
    assert any(r["original"] == "withdraw_re_ent" and r["target"] == 1 for r in samples)
    assert any(r["original"] == "ordinary" and r["target"] == 0 for r in samples)


def test_semantic_parity_preserves_facts_labels_edges_and_features():
    from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE
    from scripts.DFG.dfg_v2.tests.test_l3 import Encoder
    from scripts.DFG.dfg_v2.pipeline import build
    from scripts.DFG.dfg_v2.benchmark_v2.rename_parity import check_file
    from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
    base = graph_for(SOURCE)
    before = graph_fingerprint(base)
    archived, audit = build(base, {FILE: SOURCE}, {}, ["L1", "L2", "L3"], Encoder())
    inv = inspect_source(SOURCE)
    mapping = make_mapping(inv, build_pool({"a": inv, "b": inspect_source(POOL)}))["mapping"]
    result = check_file(base, archived, audit, SOURCE, FILE, mapping, None, Encoder())
    assert result["normalized_facts_exact"]
    assert result["projected_endpoints_exact"]
    assert graph_fingerprint(base) == before


def test_semantic_parity_rejects_tampered_old_evidence():
    from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE
    from scripts.DFG.dfg_v2.tests.test_l3 import Encoder
    from scripts.DFG.dfg_v2.pipeline import build
    from scripts.DFG.dfg_v2.benchmark_v2.rename_parity import check_file
    base = graph_for(SOURCE)
    archived, audit = build(base, {FILE: SOURCE}, {}, ["L1", "L2", "L3"], Encoder())
    audit["layers"]["L1"]["evidence"][0]["target"] = -999
    inv = inspect_source(SOURCE)
    mapping = make_mapping(inv, build_pool({"a": inv, "b": inspect_source(POOL)}))["mapping"]
    with pytest.raises(AssertionError, match="evidence differs"):
        check_file(base, archived, audit, SOURCE, FILE, mapping, None, Encoder())


def test_semantic_parity_rejects_edge_loss_in_archived_graph():
    from scripts.DFG.dfg_v2.tests.test_l1 import graph_for, FILE
    from scripts.DFG.dfg_v2.tests.test_l3 import Encoder
    from scripts.DFG.dfg_v2.pipeline import build
    from scripts.DFG.dfg_v2.benchmark_v2.rename_parity import check_file
    base = graph_for(SOURCE)
    archived, audit = build(base, {FILE: SOURCE}, {}, ["L1", "L2", "L3"], Encoder())
    s, t, k = next((s,t,k) for s,t,k,d in archived.edges(keys=True,data=True)
                   if d["edge_type"] == "DATA_DEF_USE")
    archived.remove_edge(s, t, k)
    inv = inspect_source(SOURCE)
    mapping = make_mapping(inv, build_pool({"a": inv, "b": inspect_source(POOL)}))["mapping"]
    with pytest.raises(AssertionError, match="endpoint"):
        check_file(base, archived, audit, SOURCE, FILE, mapping, None, Encoder())
