"""NS-P2b documentation transport guard; never loads a model."""
import json
import pytest

from scripts.node_sem.doc_check import check, main, parse_target
from scripts.node_sem import RUNTIME_MODULES


def test_valid_chinese_utf8(tmp_path):
    path = tmp_path / "report.md"
    path.write_bytes("## \u5b9e\u65bd\u8bb0\u5f55\n\u901a\u8fc7\u9a8c\u6536\n".encode("utf8"))
    assert check(path,expect_cjk=True)["cjk_characters"] == 8


@pytest.mark.parametrize("text", ["????", "## ???", "English ??? text"])
def test_literal_question_runs_fail(tmp_path,text):
    path=tmp_path/"report.md";path.write_bytes(text.encode("utf8"))
    with pytest.raises(ValueError,match="question marks"):check(path)


def test_invalid_utf8_always_fails_even_before_append(tmp_path):
    path=tmp_path/"report.md";path.write_bytes(b"\xff\nok\n")
    with pytest.raises(ValueError,match="strict UTF-8"):check(path,2)


def test_prior_question_runs_are_ignored_for_append(tmp_path):
    path=tmp_path/"report.md"
    old=b"## ????\n"
    path.write_bytes(old+"## \u66f4\u6b63\n\u5df2\u6838\u9a8c\n".encode("utf8"))
    assert check(path,len(old),expect_cjk=True)["passed"]
    with pytest.raises(ValueError):check(path,expect_cjk=True)


@pytest.mark.parametrize("offset",[-1,99,True,1.5,"0"])
def test_invalid_offsets_fail(tmp_path,offset):
    path=tmp_path/"report.md";path.write_bytes(b"abc")
    with pytest.raises(ValueError,match="offset"):check(path,offset)


def test_offset_cannot_split_multibyte_character(tmp_path):
    path=tmp_path/"report.md";path.write_bytes("\u4e2d\u6587".encode("utf8"))
    with pytest.raises(ValueError,match="splits"):check(path,1)


def test_english_allowed_unless_chinese_declared(tmp_path):
    path=tmp_path/"README.md";path.write_bytes(b"## Results\nPassed\n")
    assert check(path)["passed"]
    with pytest.raises(ValueError,match="no CJK"):check(path,expect_cjk=True)


def test_chinese_required_in_new_region_not_old_prefix(tmp_path):
    path=tmp_path/"report.md";old="\u65e7\u6587\n".encode("utf8")
    path.write_bytes(old+b"## Empty translation\n")
    with pytest.raises(ValueError,match="no CJK"):check(path,len(old),expect_cjk=True)


def test_replacement_character_detected(tmp_path):
    path=tmp_path/"report.md";path.write_bytes("text \ufffd".encode("utf8"))
    with pytest.raises(ValueError,match="replacement"):check(path)


def test_two_question_marks_not_corruption(tmp_path):
    path=tmp_path/"report.md";path.write_bytes(b"Two ?? are allowed")
    assert check(path)["passed"]


def test_empty_append_requires_cjk_only_when_declared(tmp_path):
    path=tmp_path/"report.md";path.write_bytes(b"old")
    assert check(path,3)["checked_bytes"] == 0
    with pytest.raises(ValueError):check(path,3,expect_cjk=True)


def test_cli_multiple_paths_and_nonzero_exit(tmp_path,capsys):
    good=tmp_path/"a.md";bad=tmp_path/"b.md"
    good.write_bytes("## \u901a\u8fc7\n".encode("utf8"));bad.write_bytes(b"????")
    assert main(["--expect-cjk",str(good),str(bad)]) == 1
    records=[json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["passed"] for r in records] == [True,False]
    assert main([str(tmp_path/"missing.md")]) == 1


def test_cli_append_byte_offset(tmp_path,capsys):
    path=tmp_path/"a.md";path.write_bytes(b"????\n"+"## \u901a\u8fc7\n".encode("utf8"))
    assert main(["--expect-cjk",str(path)+":5"]) == 0


def test_windows_drive_and_suffix_parsing():
    assert parse_target(r"C:\work\a.md") == (r"C:\work\a.md",None)
    assert parse_target(r"C:\work\a.md:23") == (r"C:\work\a.md",23)
    assert parse_target("a.md:-1") == ("a.md",-1)


def test_doc_checker_is_not_training_runtime():
    assert "doc_check.py" not in RUNTIME_MODULES
