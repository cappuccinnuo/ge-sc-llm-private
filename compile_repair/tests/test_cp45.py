"""Definition-anchored ordinary scoring. Node offsets identify the intended winners."""
import pytest

from compile_repair.evaluation.benchmark import _identity, _ordinary_correspondence, score_graphs


P4, P8 = "TMP_4(uint256) = x (c)+ 1", "TMP_8(uint256) = x (c)+ 1"
U4, U8, U5 = ("y(uint256) := TMP_{}(uint256)".format(i) for i in (4, 8, 5))
Q5, Q9 = "TMP_5(uint256) = y (c)* 2", "TMP_9(uint256) = y (c)* 2"
CASES = [
    ("correct_shift", [P4,U4,Q5], [P8,U8,Q9], (0,2,4)),
    ("one_stale_use", [P4,U4,Q5], [P8,U4,Q9], (0,4)),
    ("three_stale_uses", [P4,U4,U4,U4,Q5], [P8,U4,U4,U4,Q9], (0,8)),
    ("unshifted_wrong_use", [P4,U4,Q5], [P4,U5,Q5], (0,4)),
]


def measure(left, right, reverse=False):
    def nodes(ops):
        rows = [dict(key5=["T","f()","EXPRESSION",2*i,1], node_type="EXPRESSION", length=1,
                     ir=[op] if isinstance(op,str) else op) for i,op in enumerate(ops)]
        return dict(nodes=rows[::-1] if reverse else rows)
    truth, fixed = nodes(left), nodes(right)
    files = {"": b"abcdefghij"}
    score = score_graphs(truth, fixed, files, files, files, {}, {}, 0, True)
    aligned = {_identity(row):_identity(row) for row in truth["nodes"]}
    counts = dict.fromkeys(("candidate","structural","name_mismatch","disputed","unanchored_shift"), 0)
    _, _, _, equal = _ordinary_correspondence(truth, fixed, aligned, {}, None, files, files, counts)
    assert counts == score["counter_correspondence"]["nodes"]
    assert score["kept"]["equal"] == len(equal) and score["surviving"]["kept"] == score["kept"]
    return score, tuple(sorted(key[3] for _,key in equal))


@pytest.mark.parametrize("reverse", [False,True])
@pytest.mark.parametrize("case,left,right,expected", CASES, ids=[x[0] for x in CASES])
def test_stale_uses(case, left, right, expected, reverse):
    score, offsets = measure(left, right, reverse)
    assert offsets == expected
    assert score["exact"] == (case == "correct_shift")
    assert score["counter_correspondence"]["status"] == {
        "correct_shift":"verified", "unshifted_wrong_use":"identical"}.get(case, "partial")


def test_changed_definition_and_shifted_use():
    score, offsets = measure([P4,U4,Q5], [P8.replace("+ 1","+ 2"),U8,Q9])
    assert offsets == (4,) and not score["exact"]
    assert score["counter_correspondence"]["nodes"] == dict(candidate=2,structural=1,name_mismatch=1,
                                                            disputed=0,unanchored_shift=1)


def test_two_definitions_with_one_image():
    score, offsets = measure([P4,U4,Q5], [P8,U8,Q9.replace("TMP_9","TMP_8")])
    assert offsets == () and not score["exact"]
    assert score["counter_correspondence"]["nodes"]["disputed"] == 3


def test_repeated_definition_in_one_node_even_if_spelling_is_identical():
    score, offsets = measure([[P4,P4],U4,Q5], [[P4,P4],U4,Q5])
    assert offsets == (4,) and score["raw"]["exact"] and not score["exact"]
    assert score["counter_correspondence"]["nodes"]["disputed"] == 2


def test_unanchored_spelling_cannot_reuse_an_anchor_image():
    score, offsets = measure([P4,U8,U5], [P8,U8,U5])
    assert offsets == (0,4) and not score["exact"]


@pytest.mark.parametrize("stale", [False, True])
def test_reference_write_through_uses_the_binding(stale):
    binding, write = "REF_4(uint256) -> bal[a]", "REF_4(uint256) (->bal) := x(uint256)"
    score, offsets = measure([binding,write], [binding.replace("REF_4","REF_8"),
                             write if stale else write.replace("REF_4","REF_8")])
    assert offsets == ((0,) if stale else (0,2))
    assert score["exact"] == (not stale) and score["counter_correspondence"]["nodes"]["disputed"] == 0


@pytest.mark.parametrize("kind", ["array","delete_ref","delete_tmp"])
@pytest.mark.parametrize("stale", [False,True])
def test_witnessed_write_checks_every_operand(kind, stale):
    root = "TMP_4" if kind == "delete_tmp" else "REF_4"
    binding = (root+"(array) = INTERNAL_CALL, T.values()()" if kind == "delete_tmp"
               else root+"(array) -> entries[i]")
    if kind == "array":
        ops = [binding, root+"(array) = ['0(uint256)']"]
    else:
        ops = [binding, "REF_5(uint256) -> "+root+"[i]", root+" = delete REF_5 "]
    new_root = root.replace("4","8")
    repaired = [ir.replace(root,new_root).replace("REF_5","REF_9") for ir in ops]
    if stale:
        repaired[-1] = repaired[-1].replace(new_root,root)
    result, offsets = measure([ops,"RETURN "+root], [repaired,"RETURN "+new_root])
    assert offsets == ((2,) if stale else (0,2))
    assert result["exact"] == (not stale) and result["counter_correspondence"]["nodes"]["disputed"] == 0


@pytest.mark.parametrize("last", ["REF_4 = delete REF_6 ", "REF_4(uint256[]) -> other[i]"])
def test_missing_selector_or_second_binding_stays_disputed(last):
    ops = ["REF_4(uint256[]) -> entries[i]", "REF_6(uint256) -> elsewhere[i]", last]
    result, offsets = measure([ops,"RETURN REF_4"], [ops,"RETURN REF_4"])
    assert offsets == () and result["raw"]["exact"] and not result["exact"]
    assert result["counter_correspondence"]["nodes"]["disputed"] == 2
