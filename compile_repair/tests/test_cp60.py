"""CP6.0 / D25: Slither partial IR fails D3(c) and is reported as a tool limitation."""
from dataclasses import asdict
import hashlib
import io
import json
import logging

import pytest

from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.report import classify_record, primary_causes
from compile_repair.pipeline import repair_unit
from compile_repair.tests.test_production import production_required, trusted_compilers
from compile_repair.toolchain.solc import classify_slither, compile_file
from compile_repair.toolchain.slither import run_slither

SOURCE = b"pragma solidity ^0.8.0;\ncontract Good { function f(uint x) public pure returns (uint) { return x + 1; } }\n" \
         b"contract Bad { function g(uint y) public pure returns (uint) { return y * 2; } }\n"


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "A.sol"
    path.write_bytes(SOURCE)
    return path


def _flag_contract(monkeypatch, name):
    from slither.core.declarations.contract import Contract
    monkeypatch.setattr(Contract, "is_incorrectly_constructed", property(lambda self: self.name == name))


def _log_top_level_error(monkeypatch):
    import slither
    original = slither.Slither.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        logging.getLogger("SlitherSolcParsing").error("Impossible to generate IR for top level function free")
    monkeypatch.setattr(slither.Slither, "__init__", init)


def _analyse(source):
    compiled = compile_file(source, trusted_compilers()["0.8.38"])
    assert compiled.returncode == 0
    return run_slither(compiled, profile="production")


def test_clean_graph_passes_d3_c(source):
    production_required()
    result = _analyse(source)
    assert result["d3_a"] and result["d3_b"] and result["d3_c"] is True and result["d3"]
    assert "graph" in result


@pytest.mark.parametrize("cause", ["contract", "top_level"])
def test_partial_ir_fails_d3_c_without_graph(source, monkeypatch, cause):
    production_required()
    if cause == "contract":
        _flag_contract(monkeypatch, "Bad")
    else:
        _log_top_level_error(monkeypatch)
    result = _analyse(source)
    assert result["d3_a"] and result["d3_b"]
    assert result["d3_c"] is False and result["d3"] is False and "graph" not in result
    assert result["error_first_line"].startswith("D3(c): Slither partial IR")
    expected = (["Bad"], 0) if cause == "contract" else ([], 1)
    assert (result["partial_ir"]["incorrectly_constructed_contracts"],
            result["partial_ir"]["top_level_errors"]) == expected
    row = classify_slither(result)
    assert (row["category"], row["subtype"], row["repair_route"]) == (
        "slither_incomplete", "slither_partial_ir", "tool_limitation")


def test_classification_of_other_slither_failures_is_unchanged():
    assert classify_slither({"exception_type": "AssertionError", "d3_a": False, "d3_b": False})["subtype"] == "AssertionError"
    assert classify_slither({"d3_a": False, "d3_b": True, "d3_c": None})["subtype"] == "d3_incomplete"
    # Regression-profile results carry no D3(c) and keep their former classification.
    assert classify_slither({"d3_a": True, "d3_b": False})["subtype"] == "d3_incomplete"


def test_pipeline_reports_partial_ir_as_primary_tool_limitation(source, tmp_path, monkeypatch):
    production_required()
    _flag_contract(monkeypatch, "Bad")
    unit = CompilationUnit("partial", (SourceFile(str(source), hashlib.sha256(SOURCE).hexdigest(), SOURCE),))
    store = ArtifactStore(tmp_path / "run")
    compilers = {v: trusted_compilers()[v] for v in ("0.8.37", "0.8.38")}
    record = repair_unit(unit, compilers, store, io.StringIO())
    assert record.status != "success" and not (store.path / "units/partial/graph.json").exists()
    # Every candidate version is still tried; none yields a complete graph.
    assert {a["version"] for a in record.attempts if a.get("slither")} == set(compilers)
    record = asdict(record)
    rows = classify_record(record)
    assert {r.get("subtype") for r in rows if r.get("stage") == "slither"} == {"slither_partial_ir"}
    assert primary_causes(record, rows)["categories"] == ["slither_incomplete"]


def _put(root, name, raw):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


@pytest.mark.parametrize("flagged", [False, True])
def test_repair_that_only_leaves_partial_ir_is_attributed_to_slither(tmp_path, monkeypatch, flagged):
    """CP6.0.1: a step-4 path fix compiles, but D3(c) fails; report the Slither blocker."""
    from compile_repair.toolchain.project import resolve_project
    production_required()
    if flagged:
        _flag_contract(monkeypatch, "Leaf")
    root = tmp_path / "src"
    originals = {"App.sol": b'pragma solidity 0.8.38;\nimport {Leaf} from "./old/Leaf.sol";\ncontract App is Leaf {}\n',
                 "lib/Leaf.sol": b"pragma solidity 0.8.38;\ncontract Leaf { function f() public pure returns (uint) { return 1; } }\n"}
    for name, raw in originals.items():
        _put(root, name, raw)
    project = resolve_project(root, "App.sol")
    store = ArtifactStore(tmp_path / "run")
    record = repair_unit(CompilationUnit("chain", project.files), {"0.8.38": trusted_compilers()["0.8.38"]},
                         store, io.StringIO(), project=project)
    folder = store.path / "units/chain"
    steps = [s for s in json.loads((folder / "repair_steps.json").read_bytes())
             if s["step"] == 4 and "receipt" in s]
    assert [(root / n).read_bytes() for n in originals] == list(originals.values())
    if not flagged:
        assert record.status == "success" and steps[0]["accepted"] and "accepted_outcome" not in steps[0]
        return
    assert record.status != "success" and record.reason == "slither_side_failure"
    assert not (folder / "graph.json").exists()
    assert steps[0]["accepted"] and steps[0]["accepted_outcome"] == "compiled_slither_side_failure"
    rows = classify_record(asdict(record))
    assert {r.get("subtype") for r in rows if r.get("stage") == "slither"} == {"slither_partial_ir"}
    assert primary_causes(asdict(record), rows)["categories"] == ["slither_incomplete"]


def test_unrepaired_without_compile_clean_trial_keeps_its_compile_blocker(tmp_path):
    """No trial compiled: the final record and attribution are unchanged by CP6.0.1."""
    from compile_repair.toolchain.project import resolve_project
    production_required()
    root = tmp_path / "src"
    _put(root, "App.sol", b'pragma solidity 0.8.38;\nimport {Gone} from "./old/Gone.sol";\ncontract App is Gone {}\n')
    project = resolve_project(root, "App.sol")
    store = ArtifactStore(tmp_path / "run")
    record = repair_unit(CompilationUnit("gone", project.files), {"0.8.38": trusted_compilers()["0.8.38"]},
                         store, io.StringIO(), project=project)
    steps = json.loads((store.path / "units/gone/repair_steps.json").read_bytes())
    assert record.status != "success" and record.reason != "slither_side_failure"
    assert not any(s.get("accepted_outcome") for s in steps)
    assert primary_causes(asdict(record))["categories"] == ["missing_relative_file"]
