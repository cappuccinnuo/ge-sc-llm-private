"""CP0.1 B/C continuation: exact profiles and reviewed setting controls."""
import hashlib
import json
import re
import sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import pytest

from compile_repair.core.model import Compiler
from compile_repair.toolchain.solc import compile_file, version_tuple
from compile_repair.toolchain.slither import check_profile, run_slither, node_facts, compare_nodes

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "tests/fixtures/features"

# PROMPTS r2.5 1.8/4.2c: default-setting negatives plus explicit positives.
FEATURE_CONTROLS = {
    ("h0824_blob.sol", "0.8.24"): (("--evm-version", "cancun"), 1,
        'Error: Undeclared identifier. Did you mean "blockhash"?'),
    ("y0824_blob_asm.sol", "0.8.24"): (("--evm-version", "cancun"), 1,
        'Error: Function "blobbasefee" not found.'),
    ("y0824_mcopy.sol", "0.8.24"): (("--evm-version", "cancun"), 1,
        'Error: Function "mcopy" not found.'),
    ("y0824_tstore_asm.sol", "0.8.24"): (("--evm-version", "cancun"), 1,
        'Error: Function "tload" not found.'),
    ("h0826_require_error.sol", "0.8.26"): (("--via-ir",), 2,
        'Require with a custom error is only available using the via-ir pipeline.'),
}


def production_required():
    try:
        check_profile("production")
    except ValueError:
        pytest.skip("Feature coverage requires the approved production environment")


@lru_cache(maxsize=1)
def trusted_compilers():
    """Use CP0 identities plus a separately approved C addition, never local TOFU."""
    path = ROOT / "artifacts/cp0_v2/recon.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6"
    refs = json.loads(path.read_text())["compilers"]
    addition = ROOT / "artifacts/cp0_1_compilers_v1/trusted_compilers_addition.json"
    if addition.exists():
        from compile_repair.toolchain.solc import load_additions
        refs, _, _ = load_additions(refs, [addition])
    return {v: Compiler(v, r["path"], r["sha256"]) for v, r in refs.items()
            if Path(r["path"]).is_file()}


def feature_pairs():
    """Keep syntax floors and add the five reviewed settings controls."""
    versions = trusted_compilers()
    pairs = []
    for path in sorted(FEATURES.glob("*.sol")):
        start = re.search(r"pragma solidity >=(\d+\.\d+\.\d+)", path.read_text()).group(1)
        for version in sorted(versions, key=version_tuple):
            if version_tuple(version)[:2] == (0, 8) and version_tuple(version) >= version_tuple(start):
                pairs.append((path.name, version, ()))
                if (path.name, version) in FEATURE_CONTROLS:
                    pairs.append((path.name, version, FEATURE_CONTROLS[(path.name, version)][0]))
    return pairs


@pytest.mark.skipif(sys.version_info < (3, 8), reason="stdlib metadata requires Python >=3.8")
def test_check_profile_standard_library_metadata():
    from importlib.metadata import version
    assert check_profile("production")["slither_version"] == version("slither-analyzer") == "0.11.6"


@pytest.mark.skipif(sys.version_info >= (3, 8), reason="backport path runs in Python 3.7 mando")
def test_check_profile_metadata_backport():
    from importlib_metadata import version
    assert check_profile("regression_6c")["slither_version"] == version("slither-analyzer") == "0.8.0"


def test_explicit_production_pair_and_unknown_profile():
    assert check_profile("production", ("0.11.6", "0.4.2"))["profile"] == "production"
    with pytest.raises(ValueError, match="Unconfigured"):
        check_profile("automatic", ("0.11.6", "0.4.2"))
    with pytest.raises(ValueError, match="requires"):
        check_profile("production", ("0.11.6", "0.3.11"))


def test_feature_fixtures_preserve_all_reviewed_bytes():
    reviewed = ROOT / "artifacts/cp0_1_review_v1/probes"
    assert len(list(FEATURES.glob("*.sol"))) == 19
    for source in reviewed.glob("*.sol"):
        assert (FEATURES / source.name).read_bytes() == source.read_bytes()


@pytest.mark.parametrize("fixture,version,settings", feature_pairs())
def test_production_feature_d3(fixture, version, settings, tmp_path):
    production_required()
    compiler = trusted_compilers()[version]
    compilation = compile_file(FEATURES / fixture, compiler, settings=settings)
    result = run_slither(compilation, profile="production") if compilation.returncode == 0 else None
    (tmp_path / "invocation.json").write_text(json.dumps(
        {"solc": asdict(compilation), "slither": result}, indent=2))
    assert compilation.settings == settings
    control = FEATURE_CONTROLS.get((fixture, version))
    if control and not settings:
        assert compilation.returncode == control[1]
        assert control[2] in compilation.error_first_line
        assert result is None and not compilation.timed_out
        return
    assert compilation.returncode == 0, compilation.error_first_line
    assert result["settings"] == settings
    if settings:
        assert compilation.command[-len(settings):] == list(settings)
        assert result["command"]["solc_args"] == " ".join(settings)
    else:
        assert "solc_args" not in result["command"]
    assert result["d3"], result.get("error_first_line")
    assert result["crytic_compile_platform"] == "solc"


def test_platform_observation_preserves_public_constructor_results(tmp_path):
    production_required()
    from compile_repair.toolchain.inventory import _compile
    compiler = trusted_compilers()["0.4.13"]
    path = ROOT / "tests/fixtures/ternary.sol"
    compilation = compile_file(path, compiler)
    result = run_slither(compilation, profile="production")
    direct = node_facts(_compile(path.resolve(), compiler.path), [path])
    comparison = compare_nodes(result["nodes"], direct["nodes"])
    (tmp_path / "constructor_equivalence.json").write_text(json.dumps(
        {"solc": asdict(compilation), "observed": result, "direct": direct,
         "comparison": comparison}, indent=2))
    assert result["d3"] and result["crytic_compile_platform"] == "solc"
    assert all(row["equal"] for row in comparison.values())
