"""Prompt 8C D lexical intervention and archived-parity guards (CPU only).

Synthetic text cases validate rewriting, not Solidity compilation. Model fitting
and CUDA are deliberately not invoked by these tests.
"""
import copy

import numpy as np
import pydot
import pytest

from scripts.DFG.dfg_v2.diagnostics8c.inference import (
    assert_archive_equal, identifiers, replacement_map, rewrite_code, serialized_view)


def test_map_uses_first_source_occurrence_and_avoids_existing_id_names():
    source = """uint id0; uint id2;
    function re_ent9(uint owner_txorigin) public {
      re_ent9(owner_txorigin); uint txoriginLast;
    }"""
    expected = {"re_ent9": "id1", "owner_txorigin": "id3", "txoriginLast": "id4"}
    assert replacement_map(source) == expected
    assert replacement_map(source) == expected


def test_comment_and_string_markers_are_not_identifier_occurrences():
    source = """// txoriginComment
    /* re_entComment */ string a="txoriginString";
    string b='re_entString'; uint real_txorigin;
    uint re_entCount;"""
    mapping = replacement_map(source)
    assert mapping == {"real_txorigin": "id0", "re_entCount": "id1"}
    names = [x[0] for x in identifiers(source)]
    assert "txoriginComment" not in names
    assert "re_entString" not in names


@pytest.mark.parametrize("serialized", [False, True])
def test_rewrite_changes_only_exact_identifier_spans(serialized):
    source = """// txoriginComment
    function re_ent9(uint owner_txorigin) public {
      string memory a = "txoriginString";
      /* re_entComment */ owner_txorigin += re_ent9;
    }"""
    expected = source.replace("re_ent9", "id0").replace("owner_txorigin", "id1")
    code = pydot.quote_if_necessary(source) if serialized else source
    output, edits = rewrite_code(code, replacement_map(source))
    assert output == (pydot.quote_if_necessary(expected) if serialized else expected)
    assert len(edits) == 4
    position = 0
    pieces = []
    for lo, hi, old, new in edits:
        assert code[lo:hi] == old
        pieces.extend((code[position:lo], new))
        position = hi
    pieces.append(code[position:])
    assert output == "".join(pieces)


def test_exact_substrings_not_changed_when_identifier_name_differs():
    source = "uint re_ent; uint _re_ent_more; uint txOrigin; uint ordinary;"
    rewritten, edits = rewrite_code(source, replacement_map(source))
    assert rewritten == "uint id0; uint id1; uint txOrigin; uint ordinary;"
    assert len(edits) == 2


def test_serialized_literal_backslashes_do_not_shift_string_boundaries():
    # Pydot preserves literal backslashes; it only adds one before each quote.
    source = ('string memory a = "C:' + chr(92) * 2 +
              '"; string memory b = "txoriginFake"; txoriginReal++;')
    code = pydot.quote_if_necessary(source)
    mapping = replacement_map(source)
    assert mapping == {"txoriginReal": "id0"}
    output, edits = rewrite_code(code, mapping)
    assert output == pydot.quote_if_necessary(source.replace("txoriginReal", "id0"))
    assert len(edits) == 1
    assert "txoriginFake" in output


@pytest.mark.parametrize("slashes", [1, 3])
def test_escaped_quote_inside_literal_never_becomes_identifier(slashes):
    source = ('string memory a = "quote ' + chr(92) * slashes +
              '" txoriginFake"; re_entReal++;')
    mapping = replacement_map(source)
    assert mapping == {"re_entReal": "id0"}
    output, edits = rewrite_code(pydot.quote_if_necessary(source), mapping)
    assert output == pydot.quote_if_necessary(source.replace("re_entReal", "id0"))
    assert len(edits) == 1


def test_unknown_node_identifier_fails_instead_of_renaming_by_guess():
    with pytest.raises(ValueError, match="absent from bound source"):
        rewrite_code("txoriginUnbound++;", {"txoriginOther": "id0"})


def test_noop_keeps_serialized_text_identical():
    code = pydot.quote_if_necessary('require(msg.sender == owner); string s="re_entFake";')
    rewritten, edits = rewrite_code(code, {})
    assert rewritten == code and edits == []


def _rows():
    return [
        {"file": "a.sol", "original_graph_node_id": 3, "best": 1,
         "best_positive_probability": float(np.float32(.75))},
        {"file": "b.sol", "original_graph_node_id": 3, "best": 0,
         "best_positive_probability": float(np.float32(.25))},
    ]


def test_archive_gate_aligns_file_and_original_node_identity_not_row_order():
    rows = _rows()
    frozen = copy.deepcopy(rows)
    result = assert_archive_equal(rows[::-1], [1, 0], [.75, .25], [3, 3], ["a.sol", "b.sol"])
    assert result["passed"] and result["probability_float32_bitwise"]
    assert rows == frozen


def test_archive_gate_detects_one_float32_ulp_difference():
    changed = np.nextafter(np.float32(.75), np.float32(1), dtype=np.float32)
    result = assert_archive_equal(_rows(), [1, 0], [float(changed), .25],
                                  [3, 3], ["a.sol", "b.sol"])
    assert result["argmax_bitwise"]
    assert not result["probability_float32_bitwise"] and not result["passed"]
    assert result["maximum_probability_difference"] > 0


def test_archive_gate_bits_distinguish_signed_zero_and_argmax_changes():
    rows = _rows()
    rows[0]["best_positive_probability"] = 0.0
    result = assert_archive_equal(rows, [1, 0], [-0.0, .25], [3, 3], ["a.sol", "b.sol"])
    assert result["maximum_probability_difference"] == 0
    assert not result["passed"]
    result = assert_archive_equal(_rows(), [0, 0], [.75, .25], [3, 3], ["a.sol", "b.sol"])
    assert result["probability_float32_bitwise"] and not result["argmax_bitwise"]


@pytest.mark.parametrize("rows,ids,files", [
    (_rows(), [3, 3], ["a.sol", "wrong.sol"]),
    (_rows(), [3, 3], ["a.sol", "a.sol"]),
    (_rows() + [_rows()[0]], [3, 3, 3], ["a.sol", "b.sol", "a.sol"]),
])
def test_archive_gate_rejects_missing_or_duplicate_identity(rows, ids, files):
    with pytest.raises(ValueError):
        assert_archive_equal(rows, [r["best"] for r in rows],
                             [r["best_positive_probability"] for r in rows], ids, files)


def test_archive_gate_rejects_truncated_prediction_array():
    with pytest.raises(ValueError, match="size differs"):
        assert_archive_equal(_rows(), [1], [.75], [3, 3], ["a.sol", "b.sol"])
