"""CP0 preflight boundaries and frozen metadata/pragma semantics."""
import hashlib
import json
from pathlib import Path

import pytest

from compile_repair.evaluation.survey import candidate_versions, checked_json, write_json, survey, ROOT
from dfg.analysis.frontend import parse
from dfg.analysis.ir import Unsupported
from dfg.analysis.frontend import interval, recorded_version


@pytest.mark.parametrize("pragma,expected", [
    ("pragma solidity ^0.4.11;", ((0,4,11),(0,5,0))),
    ("pragma solidity ~0.4.17;", ((0,4,17),(0,5,0))),
    ("pragma solidity 0.4.17;", ((0,4,17),(0,4,18))),
    ("pragma solidity >=0.4.17 <0.5.0; pragma solidity ^0.4.24;", ((0,4,24),(0,5,0))),
    ("", None)])
def test_frozen_intervals(pragma, expected):
    source = pragma + " contract C {}"
    assert interval(source, parse(source).root_node) == expected


@pytest.mark.parametrize("pragma", ["pragma solidity ^0.4.0 || ^0.5.0;",
    "pragma solidity 0.4.17; pragma solidity 0.5.1;"])
def test_reject_unsupported_constraints(pragma):
    with pytest.raises(Unsupported):
        source = pragma + " contract C {}"
        interval(source, parse(source).root_node)


def test_candidates_preserve_exact_constraint_and_floor():
    versions = ["0.4.11", "0.4.13", "0.4.25", "0.5.1"]
    assert candidate_versions(((0,4,17),(0,4,18)), versions)["primary"] == []
    assert candidate_versions(None, versions) == {
        "primary": ["0.4.13", "0.4.25"], "later_series_only_after_primary_failure": []}
    candidates = candidate_versions(((0,4,0),(999,0,0)), versions)
    assert candidates["primary"] == ["0.4.13", "0.4.25"]
    assert candidates["later_series_only_after_primary_failure"] == ["0.5.1"]


def test_metadata_hashes_and_unique_csv_row(tmp_path):
    source = "pragma solidity ^0.4.11; contract C {}"
    origin = tmp_path / "C.sol"
    origin.write_text(source)
    csv = tmp_path / "versions.csv"
    csv.write_text("file,compiled version\nC.sol,0.4.17\n")
    metadata = {"source_path": str(origin), "source_sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
                "csv_path": str(csv), "csv_sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
                "row_file": "C.sol", "version": "0.4.17"}
    assert recorded_version(source, metadata) == (0,4,17)
    with pytest.raises(Unsupported, match="hash mismatch"):
        recorded_version(source + " ", metadata)
    csv.write_text("file,compiled version\nC.sol,0.4.17\nC.sol,0.4.17\n")
    metadata["csv_sha256"] = hashlib.sha256(csv.read_bytes()).hexdigest()
    with pytest.raises(Unsupported, match="ambiguous"):
        recorded_version(source, metadata)


def test_evidence_binding_and_no_overwrite(tmp_path):
    path = tmp_path / "proof.json"
    write_json(path, {"status": "original"})
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert checked_json(path, digest)["status"] == "original"
    with pytest.raises(ValueError, match="SHA256"):
        checked_json(path, "0" * 64)
    with pytest.raises(FileExistsError):
        write_json(path, {"status": "overwritten"})
    with pytest.raises(ValueError, match="subdirectory"):
        survey(ROOT.parent / "outside_cp0_artifacts", path)
    with pytest.raises(FileExistsError):
        survey(ROOT / "compile_repair/artifacts/cr_pre_v1", path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("known,expected", [
    ("0.4.17", "0.4.17"), ("0.4.11", None), ("0.5.17", None), (None, None)])
def test_regression_known_version_priority_is_bounded(known, expected):
    from compile_repair.evaluation.survey import selection_priority
    row = {"interval": ((0, 4, 12), (0, 5, 0)),
           "metadata": {"version": known} if known else None}
    assert selection_priority(row, ["0.4.11", "0.4.17", "0.5.17"]) == expected
    assert selection_priority(dict(row, metadata=None, interval=None), ["0.4.17", "0.4.25"]) == "0.4.25"
    assert selection_priority(dict(row, metadata={"version": "0.4.18"}), ["0.4.17"]) is None


def test_endpoints_continue_after_mapping_failure_and_keep_order():
    from compile_repair.evaluation.survey import d3_endpoints
    seen = []
    def probe(v):
        seen.append(v)
        return {"d3": v in {"0.4.13", "0.4.24"}}
    assert d3_endpoints(["0.4.12", "0.4.13", "0.4.24", "0.4.26"], probe) == ("0.4.13", "0.4.24")
    assert seen == ["0.4.12", "0.4.13", "0.4.26", "0.4.24"]
    assert d3_endpoints(["0.4.12"], probe) == (None, None)


def test_candidates_accept_json_interval_roundtrip():
    original = ((0, 4, 17), (0, 4, 18))
    versions = ["0.4.12", "0.4.17", "0.4.26"]
    assert candidate_versions(json.loads(json.dumps(original)), versions) == candidate_versions(original, versions)
