"""CP3.2 input-format and attribution checks without a compiler installation."""
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path

import pytest

from compile_repair.core.model import Compilation, CompilationUnit, Compiler, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.report import aggregate_attributions, parseable_version_blockers, primary_causes
from compile_repair.evaluation.survey import solidity_snippet_evidence
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.project import input_format_evidence, standard_json_input


NO_PRAGMA = b"event Ping:\n    n: uint256\n@external\ndef ping(n: uint256):\n    pass\n"


def run_entry(raw, tmp_path, **kwargs):
    path = tmp_path / "source.sol"
    path.write_bytes(raw)
    src = SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw)
    compiler = Compiler("0.8.24", "/example/solc", "not-executed")
    journal = io.StringIO()
    record = repair_unit(CompilationUnit("entry", (src,)), {compiler.version: compiler},
                         ArtifactStore(tmp_path/"run"), journal, **kwargs)
    assert path.read_bytes() == raw
    return record, journal.getvalue()


@pytest.mark.parametrize("raw,basis,language", [
    (b"# @version ^0.3.10\n", "vyper_version_directive", "Vyper"),
    (b"#pragma version 0.4.0\r\n", "vyper_version_directive", "Vyper"),
    (NO_PRAGMA, "vyper_decorated_function_and_declaration", "Vyper"),
    (b'{{"language":"Vyper","sources":{"a":{"content":"..."}}}}', "json_language", "Vyper"),
    (b'{"language":"Yul","sources":{"a":{"content":"..."}}}', "json_language", "Yul"),
])
def test_foreign_language_stops_before_tools(tmp_path, raw, basis, language):
    def forbidden(*args, **kwargs):
        pytest.fail("An excluded input reached a tool")
    r, log = run_entry(raw, tmp_path, compile_fn=forbidden, project_compile_fn=forbidden, slither_fn=forbidden)
    assert (r.status, r.reason, r.plan, log) == ("unrepaired", "non_solidity_input", None, "")
    assert r.attempts == [dict(stage="input_format", status="non_solidity", basis=basis, language=language)]
    assert primary_causes(asdict(r))["categories"] == ["non_solidity_input"]


@pytest.mark.parametrize("raw", [b"", b"// comment only", b"struct P { uint a; }", b"enum Color { Red }",
                                  b"error BadValue(uint256 n);", b'import "./types.sol";'])
def test_unknown_is_recorded_and_reaches_compilation(tmp_path, raw):
    assert not solidity_snippet_evidence(raw)["is_solidity"]
    def compile_fn(path, compiler, settings=()):
        return Compilation(str(path), hashlib.sha256(raw).hexdigest(), compiler, [], str(tmp_path),
                           1, "Error: sample", "Error: sample", "", 0, False, settings=settings)
    r, log = run_entry(raw, tmp_path, compile_fn=compile_fn)
    assert r.inputs[0]["language_evidence"]["status"] == "unknown"
    assert r.attempts[0]["solc"]["returncode"] == 1
    assert r.plan is not None and log


@pytest.mark.parametrize("raw,status", [
    (b"/*\n# @version 0.3.10\n*/\ncontract A {}", "solidity"),
    (b'contract A { string s = "\n# pragma version 0.4.0\n"; }', "solidity"),
    (b"/*\n" + NO_PRAGMA + b"*/", "unknown"),
    (b"@external\ndef f():\n  pass\n", "unknown"),
    (b"# general comment\n", "unknown"),
    (b'{"language":null}', "unknown"), (b'[{"type":"function","name":"f"}]', "unknown"),
    (b'{"language":"Solidity","sources":2}', "solidity"),
])
def test_language_needs_positive_evidence(raw, status):
    assert input_format_evidence(raw)[0]["status"] == status


@pytest.mark.parametrize("case,raw", [
    ("etherscan_double_brace", b'{{"language":"Solidity","sources":{"a":{"content":"x"}},"settings":{"optimizer":{}}}}'),
    ("standard_json", b'{"language":"Solidity","sources":{"a":{"content":"x"}}}'),
    ("etherscan_flat_map", b'{"a":{"content":"x"},"b":{"content":"y"}}'),
    ("leading_whitespace", b' \n {"language":"Solidity","sources":{"a":{"content":"x"}}}\n'),
    ("utf8_bom", b'\xef\xbb\xbf  {{"language":"Solidity","sources":{"a":{"content":"x"}}}}'),
    ("solidity_source", b"pragma solidity ^0.5.0; contract A {}"),
    ("abi_json", b'[{"type":"function","name":"f"}]'),
    ("yul_standard_json", b'{"language":"Yul","sources":{"a":{"content":"x"}}}'),
    ("sources_url_only", b'{"language":"Solidity","sources":{"a":{"urls":["example"]}}}'),
    ("empty_sources", b'{"language":"Solidity","sources":{}}'),
    ("truncated_json", b'{"language":"Solidity","sources":{"a":{"content":"x"'),
    ("nan_constant", b'{"a":{"content":"x"},"n":NaN}'),
])
def test_review_wrapper_cases(case, raw):
    frozen = Path(__file__).resolve().parents[1] / "artifacts/cp3_1_review_v1/probe_wrapper_detect.json"
    old = json.loads(frozen.read_bytes())[case]
    result = standard_json_input(raw)
    assert input_format_evidence(raw)[1] == result
    if case in ("utf8_bom", "sources_url_only"):
        assert old is None and result["source_count"] == 1
        assert result.get("content_missing", False) == (case == "sources_url_only")
    else:
        assert (None if result is None else {k: result[k] for k in ("source_count", "settings_keys")}) == old


def test_missing_content_count_reaches_manifest(tmp_path):
    raw = b'{"language":"Solidity","sources":{"a":{"content":""},"b":{"urls":[]},"c":{},"d":{"content":2}}}'
    def forbidden(*args, **kwargs):
        pytest.fail("A wrapper reached a compiler")
    r, log = run_entry(raw, tmp_path, compile_fn=forbidden, slither_fn=forbidden)
    assert r.reason == "standard_json_input" and not log
    assert r.attempts == [dict(stage="input_format", source_count=4, source_names=list("abcd"),
                               settings_keys=[], content_missing=True, missing_source_count=3)]


@pytest.mark.parametrize("versions,labels", [
    ({}, []), ({"a":["unbalanced_structure", "other"]}, []),
    ({"a":["parser_error_other"], "b":["undeclared_identifier","other"], "c":["other"]}, ["other"]),
    ({"a":["parser_error_other"], "b":["other"], "c":["undeclared_identifier"]}, []),
    ({"a":["other","type_error_other"], "b":["type_error_other","other"]}, ["other","type_error_other"]),
])
def test_parseable_blocker_intersection(versions, labels):
    assert parseable_version_blockers(versions) == labels


def test_excluded_and_unmeasured_have_separate_denominators():
    def obs(uid, status, causes, versions=None):
        return dict(unit_id=uid, corpus="A", entry_sha256=uid, status=status,
                    any_categories=causes, primary=dict(categories=causes, by_version=versions or {}))
    rows = [obs("a","success",[]), obs("b","unmeasured",[]), obs("c","unrepaired",["non_solidity_input"]),
            obs("d","unrepaired",["version_dependent"],{"0.6.0":["unbalanced_structure"],"0.8.0":["other"]})]
    out = aggregate_attributions(rows, ["other","non_solidity_input"])
    for name in ("primary", "any_candidate"):
        assert out[name]["total"] == {"A":2} and out[name]["remaining_failures"] == {"A":1}
    assert out["non_solidity_by_corpus"] == out["unmeasured_by_corpus"] == {"A":1}
    blockers = out["version_dependent_blockers"]
    row = next(r for r in blockers["category_unit_counts"] if r["category"] == "other")
    assert blockers["units"] == row["units"] == 1 and row["example_sha256"] == ["d"]
