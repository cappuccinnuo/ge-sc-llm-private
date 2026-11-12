"""D3 negative cases, explicit compiler trust and installed-solc probes."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as Item

import pytest

from compile_repair.core.model import Compiler
from compile_repair.toolchain.solc import compile_file, command, error_first_line, verify_binary
from compile_repair.toolchain.slither import node_facts, compare_nodes, run_slither

FIXTURE = Path(__file__).parent / "fixtures/counter.sol"


def test_error_line_does_not_report_warning():
    assert error_first_line("Warning: first\nfile.sol:2: ParserError: bad\nmore") == "file.sol:2: ParserError: bad"
    assert error_first_line("") is None


def test_refuse_untrusted_binary(tmp_path):
    path = tmp_path / "solc"
    path.write_bytes(b"not a compiler")
    with pytest.raises(ValueError, match="SHA256"):
        verify_binary(Compiler("0.4.13", str(path), "0" * 64))


def test_command_matches_crytic_version_boundaries():
    old = command(FIXTURE, Compiler("0.4.0", "/explicit/solc", "unused"))
    modern = command(FIXTURE, Compiler("0.4.13", "/explicit/solc", "unused"))
    assert "--allow-paths" not in old
    assert "compact-format" not in old[3]
    assert "compact-format" in modern[3]
    assert modern[4:6] == ["--allow-paths", "."]
    assert modern[0] == "/explicit/solc"


@pytest.mark.parametrize("mapping,reason", [({}, "missing_filename"),
    ({"filename_absolute": "relative.sol", "start": 0}, "invalid_filename"),
    ({"filename_absolute": "/foreign.sol", "start": 0}, "foreign_filename"),
    ({"filename_absolute": str(FIXTURE.resolve())}, "missing_start")])
def test_d3_rejects_incomplete_mapping(mapping, reason):
    node = Item(source_mapping=mapping, type="EXPRESSION", irs=[])
    function = Item(full_name="f()", nodes=[node])
    slither = Item(contracts=[Item(name="C", functions_and_modifiers_declared=[function])])
    result = node_facts(slither, [FIXTURE])
    assert not result["mapping_complete"] and result["counts"][reason] == 1


def test_comparison_preserves_multiplicity_ir_order_and_ignores_length_in_identity():
    first = {"key4": ["C", "f()", "EXPRESSION", 0], "ir": ["read", "write"], "length": 2}
    other = dict(first, length=9)
    assert compare_nodes([first], [other])["key4"]["equal"]
    assert not compare_nodes([first], [other])["source_length"]["equal"]
    assert not compare_nodes([first, first], [first])["key4"]["equal"]
    assert not compare_nodes([first], [dict(first, ir=["write", "read"])])["slithir"]["equal"]


def test_real_compiler_success_is_not_d3_success(tmp_path):
    # Hashes are the frozen 6c trusted binary identities, not trust-on-first-use.
    hashes = {"0.4.11": "0a8d138ee245039e6f8312edc024ba3c4739cc3c013b47dc7fc9196a2e327fea",
              "0.4.13": "791ee3a20adf6c5ab76cc889f13cca102f76eb0b7cf0da4a0b5b11dc46edf349"}
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    results = []
    for version, digest in hashes.items():
        path = Path.home() / ".solc-select/artifacts" / ("solc-" + version) / ("solc-" + version)
        if not path.is_file():
            pytest.skip("Required existing compiler unavailable: " + version)
        compilation = compile_file(FIXTURE, Compiler(version, str(path), digest))
        result = run_slither(compilation)
        (tmp_path / (version + ".json")).write_text(json.dumps({"compile": asdict(compilation), "slither": result}, indent=2))
        assert compilation.returncode == 0 and result["constructed"]
        results.append(result)
    assert not results[0]["d3"] and results[0]["counts"]["missing_filename"] > 0
    assert results[1]["d3"] and results[1]["counts"]["missing_filename"] == 0
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("failure", ["authorization", "linked_hash", "override", "official_hash"])
def test_addition_trust_chain_rejects_unapproved_or_changed_refs(tmp_path, failure):
    from compile_repair.toolchain.solc import load_additions
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "artifacts/cp0_compiler_install_v1/trusted_compilers_addition.json").read_text())
    base = {}
    if failure == "authorization":
        auth = json.loads(Path(manifest["authorization"]["path"]).read_text())
        auth["versions"] = ["0.4.18"]
        auth_path = tmp_path / "authorization.json"
        auth_path.write_text(json.dumps(auth))
        manifest["authorization"] = {"path": str(auth_path), "sha256": hashlib.sha256(auth_path.read_bytes()).hexdigest()}
    elif failure == "linked_hash":
        manifest["official_release_index"]["sha256"] = "0" * 64
    elif failure == "override":
        base["0.4.17"] = manifest["compilers"]["0.4.17"]
    else:
        manifest["compilers"]["0.4.17"]["sha256"] = "0" * 64
    path = tmp_path / "addition.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_additions(base, [path])


def test_release_coverage_uses_observed_catalog_only():
    from compile_repair.toolchain.solc import release_coverage
    index = {"latestRelease": "0.8.4", "releases": {
        "0.4.11": "old", "0.4.12": "floor", "0.8.0": "early", "0.8.4": "late"}}
    report = release_coverage(index, ["0.4.12", "0.8.0"])
    assert report["series"]["0.4"]["published"] == ["0.4.12"]
    assert report["series"]["0.8"]["not_installed"] == ["0.8.4"]
    assert report["series"]["0.6"]["published"] == []
    assert not report["all_patch_versions_verified"]
    assert release_coverage(None, ["0.4.12"])["status"] == "not_obtained"
