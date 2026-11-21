"""CP3.1 primary attribution, standard JSON detection and release boundaries."""
import hashlib
import io
import json
from dataclasses import asdict
import pytest
from scripts.DFG.models import Unsupported
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.evaluation.report import primary_causes
from compile_repair.rules.environment import pragma_interval
from compile_repair.toolchain.project import standard_json_input


def attempt(version, rc, message=""):
    return {"version": version, "stage": "environment", "solc": {
        "returncode": rc, "timed_out": False, "stderr": message, "cwd": "."},
        "slither": {"d3": False, "exception_type": "SlitherException"} if rc == 0 else None}


def primary(*attempts):
    return primary_causes({"status": "unrepaired", "attempts": attempts, "inputs": [], "reason": "failed"})


def test_precompiler_evidence_has_priority():
    stages = [{"stage": "input_format", "source_count": 1},
              {"stage": "environment_plan", "error_first_line": "F: unterminated pragma directive"},
              {"stage": "project_assembly", "issues": [{"category": "unresolved_package_import"}]}]
    for stage, label in zip(stages, ["standard_json_input","unterminated_pragma","unresolved_package_import"]):
        assert primary(stage, attempt("0.5.0", 0))["categories"] == [label]


def test_solc_success_excludes_earlier_diagnostics_from_primary():
    result = primary(attempt("0.4.15", 1, "Error: Undeclared identifier."),
                     attempt("0.4.24", 0))
    assert result["categories"] == ["slither_incomplete"]


@pytest.mark.parametrize("other,expected", [
    ("Error: Undeclared identifier.", "undeclared_identifier"),
    ("Error: Stack too deep.", "version_dependent")])
def test_primary_requires_persistence_across_versions(other, expected):
    result = primary(attempt("0.5.0", 1, "Error: Undeclared identifier."),
                     attempt("0.6.0", 1, other))
    assert result["categories"] == [expected]
    assert set(result["by_version"]) == {"0.5.0","0.6.0"}


@pytest.mark.parametrize("mode", ["sources", "double", "bare", "source_named_sources"])
def test_wrapper_stops_before_compilation_and_keeps_only_metadata(tmp_path, mode):
    name = "sources" if mode == "source_named_sources" else "contracts/C.sol"
    sources = {name: {"content": "pragma solidity ^0.8.0; contract C {}"}}
    obj = sources if mode in ("bare", "source_named_sources") else {
        "language": "Solidity", "sources": sources, "settings": {"optimizer": {"enabled": True}}}
    raw = json.dumps(obj).encode()
    if mode == "double":
        raw = b" {" + raw + b"}\n"
    path = tmp_path / "input.sol"
    path.write_bytes(raw)
    source = SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw)
    def forbidden(*args, **kwargs):
        pytest.fail("Wrapper reached a compiler or Slither")
    journal = io.StringIO()
    result = repair_unit(CompilationUnit("wrap", (source,)), {}, ArtifactStore(tmp_path/"out"),
                         journal, compile_fn=forbidden, slither_fn=forbidden)
    assert result.status == "unrepaired" and result.reason == "standard_json_input"
    assert result.plan is None and journal.getvalue() == ""
    keys = [] if mode in ("bare", "source_named_sources") else ["optimizer"]
    assert result.attempts == [{"stage":"input_format", "source_count":1, "source_names":[name],
                                "settings_keys":keys}]
    assert primary_causes(asdict(result))["categories"] == ["standard_json_input"]


@pytest.mark.parametrize("raw", [
    b'contract C {}', b'{"language":"Yul","sources":{"a":{"content":"..."}}}',
    b'{"sources":{"a":{"urls":[]}}}', b'{"a":{"content":23}}', b'{"a":',
    b'{"sources":{"a":{"content":"x"}},"settings":NaN}'])
def test_not_solidity_source_wrapper(raw):
    assert standard_json_input(raw) is None


@pytest.mark.parametrize("expression,bounds", [
    ("0.4.X", ((0,4,0),(0,5,0))), ("^0.5 <0.6", ((0,5,0),(0,6,0))),
    (">0.5.*", ((0,6,0),(999,0,0))), ("0.x", ((0,5,0),(1,0,0))),
    ("^0", ((0,5,14),(1,0,0))), ("~0", ((0,0,0),(1,0,0)))])
def test_partial_release_boundaries(expression,bounds):
    assert pragma_interval([("pragma solidity "+expression+";").encode()]) == bounds


@pytest.mark.parametrize("expression", ["0.4 || 0.8", "0.4.xyz", "0.4.Xx", "0.4.5.1"])
def test_malformed_or_disjoint(expression):
    with pytest.raises(Unsupported):
        pragma_interval([("pragma solidity "+expression+";").encode()])
