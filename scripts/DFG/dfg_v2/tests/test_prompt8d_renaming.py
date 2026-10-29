"""Prompt 8D neutral interventions: no graph/model mutation or training."""
import copy
from types import SimpleNamespace

import pytest

from scripts.DFG.dfg_v2.diagnostics8d import renaming as r


@pytest.fixture(scope="module")
def encoder():
    from scripts.DFG.experiments.prepare import cached_tokenizer
    return SimpleNamespace(_tokenizer=cached_tokenizer())


@pytest.fixture(scope="module")
def candidates(encoder):
    return r.NeutralCandidates(encoder)


def source_for(names):
    return "pragma solidity ^0.4.24; contract A { " + " ".join(
        "uint %s;" % name for name in names) + " }"


def test_marker_order_unique_and_skip_strings_comments():
    source = 'uint x_re_ent1; string s="y_re_ent2"; // z_re_ent3\n x_re_ent1++; uint f_txorigin4;'
    assert r.marker_names(source) == ["x_re_ent1", "f_txorigin4"]


def test_generic_rewrite_preserves_strings_comments_and_unselected_markers():
    code = '"counter += txorigin9; \\"counter\\"; // counter\\n counter++;"'
    rewritten, edits = r.rewrite_node(code, {"counter": "omega"})
    assert rewritten == '"omega += txorigin9; \\"counter\\"; // counter\\n omega++;"'
    assert len(edits) == 2


def test_nonmarker_declaration_positive_not_keyword_subtraction():
    source = """pragma solidity ^0.4.24;
    contract A { uint stored; function test(uint parameter) public {
      uint local=parameter; unknown(); externalObject.someUnknown(local);
      require(local > 0); msg.sender.transfer(local);
    }}"""
    result = r.declared_user_names(source)
    assert {"A", "stored", "test", "parameter", "local"} <= set(result["names"])
    assert not {"unknown", "externalObject", "someUnknown", "require", "msg",
                "sender", "transfer"} & set(result["names"])


@pytest.mark.parametrize("name", ["transfer", "send", "call", "value", "balance",
                                  "sender", "origin", "gasleft", "require", "msg",
                                  "tx", "block", "this", "now", "address", "uint256"])
def test_builtin_exclusions_are_not_overridden_by_declared_spelling(name):
    assert name in r.EXCLUDED_NAMES


def test_builtin_named_user_declaration_conservatively_excluded():
    result = r.declared_user_names(source_for(["sender", "value", "legitimate"]))
    assert "legitimate" in result["names"]
    assert "sender" not in result["names"]
    assert result["rejected"]["sender"] == "reserved_builtin_or_global_name"


def test_exact_full_placebo_fails_instead_of_reducing_count(encoder):
    source = source_for(["withdraw_re_ent23", "v"])
    check = r.placebo_selection(source, encoder)
    assert not check["passed"]
    assert check["required_count"] == 1
    assert check["shortages"]
    with pytest.raises(ValueError, match="infeasible"):
        r.prepare_file(source, [(1, source)], encoder, "C")


def test_matched_selection_equal_histogram_first_occurrence(monkeypatch):
    names = ["m_re_ent1", "second", "n_re_ent2", "third", "last", "p_re_ent3"]
    source = source_for(names)
    lengths = dict(A=1, m_re_ent1=4, n_re_ent2=4, p_re_ent3=5,
                   second=4, third=4, last=3)
    monkeypatch.setattr(r, "token_count", lambda encoder, text: lengths[text])
    result = r.matched_selection(source, object())
    assert result["marker_names"] == ["m_re_ent1", "n_re_ent2"]
    assert result["nonmarker_names"] == ["second", "third"]
    assert result["matched_histogram"] == {"4": 2}
    assert result["unmatched_marker_names"] == ["p_re_ent3"]


def test_zero_match_file_retained_with_empty_maps(encoder, candidates):
    source = source_for(["withdraw_re_ent23", "v"])
    result = r.prepare_bundle_file(source, [(1, '"uint withdraw_re_ent23;"')], encoder, candidates)
    assert result["matching"]["matched_count"] == 0
    assert result["matching"]["zero_matched_file_retained"]
    assert result["views"]["B_matched"]["mapping"] == {}
    assert result["views"]["C_matched"]["mapping"] == {}
    assert len(result["views"]["C_matched"]["nodes"]) == 1


def test_fixed_candidates_are_neutral_deterministic_and_equal_length(encoder):
    a, b = r.NeutralCandidates(encoder, suffixes=4, max_words=3), r.NeutralCandidates(encoder, suffixes=4, max_words=3)
    for length in range(1, 10):
        assert a.for_length(length) == b.for_length(length)
        assert all(r.token_count(encoder, word) == length and not r.is_marker(word)
                   for word in a.for_length(length))


def test_b_full_preserves_actual_token_positions_and_input(encoder, candidates):
    source = source_for(["withdraw_re_ent23"])
    codes = [(1, '"uint withdraw_re_ent23;"'),
             (2, '"withdraw_re_ent23 += withdraw_re_ent23;"')]
    saved = copy.deepcopy(codes)
    result = r.prepare_file(source, codes, encoder, "B_full", candidates)
    assert codes == saved
    assert result["mapping"]["withdraw_re_ent23"] != "withdraw_re_ent23"
    assert result["full_token_length_preserved"]
    for row in result["nodes"]:
        assert row["before_length"] == row["after_length"]
        assert row["position_proof"]["unedited_token_ids_equal"]
        assert row["position_proof"]["occurrence_token_positions_equal"]


def test_collision_candidates_are_skipped(encoder, candidates):
    old = "withdraw_re_ent23"
    first = r.prepare_file(source_for([old]), [(1, old)], encoder, "B_full", candidates)
    collision = first["mapping"][old]
    source = source_for([old, collision])
    second = r.prepare_file(source, [(1, old)], encoder, "B_full", candidates)
    assert second["mapping"][old] != collision
    assert second["identifiers"][0]["neutral_token_count"] == r.token_count(encoder, old)


def test_untruncated_length_check_detects_changes_beyond512(encoder):
    old = "x_re_ent123"
    code = "uint counter = 0;\n" * 100 + old
    assert len(r.token_ids(encoder, code)) > 512
    with pytest.raises(ValueError, match="Full node token length"):
        r.length_audit([(1, code)], {old: "x"}, encoder)


def test_same_total_length_does_not_prove_local_token_positions(encoder):
    code = "alpha; alpha_beta_gamma0;"
    changed, _ = r.rewrite_node(code, {
        "alpha": "alpha_beta_gamma0", "alpha_beta_gamma0": "alpha"})
    assert len(r.token_ids(encoder, code)) == len(r.token_ids(encoder, changed))
    with pytest.raises(ValueError, match="token positions"):
        r.position_audit(code, {"alpha": "alpha_beta_gamma0", "alpha_beta_gamma0": "alpha"}, encoder)


def test_nonselected_identifier_token_ids_must_stay_equal(encoder):
    proof = r.position_audit("uint x = alpha; // unchanged", {}, encoder)
    assert proof["unedited_token_ids_equal"]
    assert proof["edited_occurrences"] == 0


def test_reject_duplicate_node_identity(encoder):
    with pytest.raises(ValueError, match="Duplicate"):
        r.prepare_file(source_for(["f_re_ent1"]), [(1, "a"), (1, "b")], encoder)


def test_reject_node_marker_missing_in_source(encoder):
    with pytest.raises(ValueError, match="absent"):
        r.prepare_file(source_for(["f_re_ent1"]), [(1, "other_re_ent2")], encoder)


def test_reject_unknown_mode(encoder):
    with pytest.raises(ValueError, match="Unknown"):
        r.prepare_file("", [], encoder, "loosen_matching")


def test_reject_ineligible_matched_names(encoder):
    with pytest.raises(ValueError, match="ineligible"):
        r.prepare_file(source_for(["f_re_ent1"]), [(1, "f_re_ent1")], encoder,
                       mode="C_matched", selected_names=["f_re_ent1"])


def test_require_explicit_matched_selection(encoder):
    with pytest.raises(ValueError, match="explicit"):
        r.prepare_file(source_for(["f_re_ent1"]), [(1, "f_re_ent1")], encoder,
                       mode="B_matched")


@pytest.mark.parametrize("name", ["_weiToWithdraw", "ApproveAndCallFallBack"])
def test_real_context_neutral_names_preserve_leading_underscore_and_space_signature(
        name, encoder, candidates):
    source = source_for([name, "f_re_ent1"])
    codes = [(1, '"uint %s;"' % name), (2, '"object.%s;"' % name)]
    result = r.prepare_file(source, codes, encoder, mode="C_matched",
                            candidates=candidates, selected_names=[name])
    replacement = result["mapping"][name]
    assert r.token_count(encoder, replacement) == r.token_count(encoder, name)
    assert r.token_count(encoder, " " + replacement) == r.token_count(encoder, " " + name)
    assert all(row["position_proof"]["occurrence_token_positions_equal"]
               for row in result["nodes"])


def test_no_marker_zero_subset_records_remain(monkeypatch):
    source = source_for(["safe_variable"])
    monkeypatch.setattr(r, "token_count", lambda encoder, text: 2)
    result = r.matched_selection(source, object())
    assert result["full_marker_count"] == 0
    assert result["matched_count"] == 0
    assert result["pairs"] == []
    assert result["zero_matched_file_retained"]
