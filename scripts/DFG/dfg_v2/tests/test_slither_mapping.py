"""Prompt 6d mapping proofs. Synthetic syntax tests, no solc invocation."""
import copy
from types import SimpleNamespace as NS
import pytest
from scripts.DFG.dfg_v2 import slither_mapping as sm

RAW = b"pragma solidity ^0.4.0; contract C { function f(uint x) { x; } }"


def record(raw=RAW, expression="x"):
    start = raw.rindex(b"x;")
    return dict(mapping=dict(start=start, length=1), expression=expression,
                text_origin=sm.TEXT_ORIGIN,
                events=[dict(layer="L1", name="x", kind="USE", tags=[])])


def test_exact_independent_expression_proves_without_mutation():
    nodes = [record()]
    before = copy.deepcopy(nodes)
    result = sm.prove_single_source(RAW, nodes)
    assert result["status"] == "proved" and result["proven_nodes"] == 1
    assert nodes == before
    facts = sm.proved_reference(RAW, nodes, result)
    assert facts["L1"] == {(1, "x", "USE"): set()}
    assert nodes == before


def test_import_directive_rejects_whole_file():
    raw = b'import "lib.sol"; ' + RAW
    proof = sm.prove_single_source(raw, [record(raw)])
    assert proof["status"] == "not_comparable"
    assert proof["failure_counts"]["source_has_import"] == 1
    with pytest.raises(ValueError, match="All-node proof"):
        sm.proved_reference(raw, [record(raw)], proof)


def test_import_word_inside_comment_or_string_is_not_a_directive():
    raw = b'// import "lib.sol";\n' + RAW
    assert sm.prove_single_source(raw, [record(raw)])["status"] == "proved"
    raw = b'contract C { string s="import"; function f(uint x) { x; } }'
    assert sm.prove_single_source(raw, [record(raw)])["status"] == "proved"


@pytest.mark.parametrize("text", ["y", " x", "x ", "(x)", "uint256(x)"])
def test_text_mismatch_never_normalized(text):
    proof = sm.prove_single_source(RAW, [record(expression=text)])
    assert proof["status"] == "not_comparable"
    assert proof["failure_counts"]["text_mismatch"] == 1


def test_entry_point_without_independent_expression_blocks_partial_rescue():
    good = record()
    entry = dict(mapping=dict(start=0, length=len(RAW)),
                 expression=None, text_origin=None, events=[])
    nodes = [good, entry]
    proof = sm.prove_single_source(RAW, nodes)
    assert proof["status"] == "not_comparable"
    assert proof["proven_nodes"] == 1 and not proof["partial_mapping_committed"]
    with pytest.raises(ValueError):
        sm.proved_reference(RAW, nodes, proof)


def test_source_slice_cannot_be_presented_as_independent_text():
    node = record()
    node["text_origin"] = "target_source_slice"
    proof = sm.prove_single_source(RAW, [node])
    assert proof["status"] == "not_comparable"
    assert proof["failure_counts"]["missing_independent_expression"] == 1


@pytest.mark.parametrize("start,length", [(-1, 1), (0, 0), (0, -1), (0, 99999),
                                          (True, 1), (1, True), ("1", 1), (1, None)])
def test_invalid_or_empty_spans_rejected(start, length):
    node = record()
    node["mapping"].update(start=start, length=length)
    assert sm.prove_single_source(RAW, [node])["failure_counts"] == {
        "invalid_or_empty_byte_span": 1}


def test_invalid_utf8_boundary_rejected():
    raw = RAW.replace(b"function", b"/* \xc3\xa9 */ function")
    node = record(raw)
    node["mapping"] = dict(start=raw.index(b"\xa9"), length=1)
    assert sm.prove_single_source(raw, [node])["failure_counts"] == {
        "invalid_utf8_boundary": 1}


def test_unparsed_source_or_no_nodes_rejected():
    assert sm.prove_single_source(b"contract {", [record()])["status"] == "not_comparable"
    assert sm.prove_single_source(RAW, [])["failure_counts"] == {"no_cfg_nodes": 1}


def test_tampered_proof_does_not_unlock_reference():
    nodes = [record(expression="wrong")]
    proof = sm.prove_single_source(RAW, nodes)
    proof["status"] = "proved"
    with pytest.raises(ValueError):
        sm.proved_reference(RAW, nodes, proof)


def test_collector_does_not_access_source_slice_property():
    class Node:
        source_mapping = {"start": 0, "length": 1}
        expression = "x"
        node_id = 1
        type = "EXPRESSION"
        @property
        def content(self):
            raise AssertionError("Target-backed content is not independent evidence")
    function = NS(nodes=[Node()], name="f", contract_declarer=None)
    slither = NS(contracts=[NS(functions=[function], modifiers=[], name="C")])
    rows = sm.collect_nodes(slither)
    assert rows[0]["expression"] == "x"
    assert rows[0]["text_origin"] == sm.TEXT_ORIGIN


def test_output_directory_refuses_overwrite_before_compiler(tmp_path):
    with pytest.raises(FileExistsError):
        sm.run("not_read", "not_read", "not_read", tmp_path)
