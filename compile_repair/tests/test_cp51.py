"""CP5.1 wrapper settings, constrained candidates and benchmark observations."""
import hashlib
import io
import json
from pathlib import Path

import pytest

from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.tests.test_production import production_required, trusted_compilers
from compile_repair.toolchain.project import wrapper_settings


def test_wrapper_settings_preserve_details_and_disabled_optimizer():
    flags, other = wrapper_settings({"optimizer":{"enabled":False, "runs":0, "details":{"yul":True}},
                                    "evmVersion":"cancun", "viaIR":True})
    assert flags == ("--optimize-runs", "0", "--evm-version", "cancun", "--via-ir")
    assert other == {"optimizer":{"details":{"yul":True}}}
    assert wrapper_settings({}) == ((), {})
    for invalid in (True, -1, 2**32, "200"):
        with pytest.raises(ValueError, match="optimizer.runs"):
            wrapper_settings({"optimizer":{"runs":invalid}})


def test_declared_optimizer_goes_to_real_solc_and_slither(tmp_path):
    production_required()
    source = "pragma solidity 0.8.38; contract C { function f(uint x) public pure returns(uint) { return x+1; } }"
    raw = json.dumps({"language":"Solidity","sources":{"src/C.sol":{"content":source}},
                      "settings":{"optimizer":{"enabled":True,"runs":200},"viaIR":True}}).encode()
    path = tmp_path/"wrapped.sol"
    path.write_bytes(raw)
    unit = CompilationUnit("wrapped",(SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw),))
    store = ArtifactStore(tmp_path/"store")
    stream = io.StringIO()
    result = repair_unit(unit, {"0.8.38":trusted_compilers()["0.8.38"]}, store, stream)
    assert result.status == "success" and result.settings == ("--optimize","--optimize-runs","200","--via-ir")
    tool = result.attempts[-1]
    assert tool["solc"]["command"][-4:] == list(result.settings) and tool["solc"]["returncode"] == 0
    assert tool["slither"]["d3"] and tool["slither"]["graph_usable"]
    assert "compiler_settings_retry" not in result.flags and path.read_bytes() == raw


def test_masked_identity_retains_alias_and_does_not_open_lock(tmp_path):
    from compile_repair.rules.dependencies import manifest_identities
    (tmp_path / "package.json").write_text('{"dependencies":{"alias":"npm:real-name@^1.2"}}')
    (tmp_path / "package-lock.json").write_text("this file must not be read by the masked experiment")
    masked = manifest_identities(tmp_path, "A.sol", "alias", mask_versions=True)
    assert (masked["tier"], masked["package"], masked["spec"]) == ("T3", "real-name", None)
    assert [s["path"] for s in masked["manifests"]] == ["package.json"]


@pytest.mark.parametrize("limit,all_fail,ordinals,success,truncated", [
    (None, False, [1, 2], True, False), (1, False, [1], False, True),
    (2, True, [1, 2], False, False)])
def test_package_limit_counts_actual_compilations(tmp_path, limit, all_fail, ordinals, success, truncated):
    from compile_repair.rules.dependencies import _indexed_source
    from compile_repair.tests.test_cp5 import CLIENT, LIB, VERSION, put
    from compile_repair.toolchain.project import resolve_project
    production_required()
    bad = LIB.replace(b"value()", b"different()")
    releases = {"2.0.0": bad, "1.0.0": bad if all_fail else LIB}

    class Index:
        packages = {"math-kit": {v: dict(files={"util/Math.sol": _indexed_source(raw)},
                    integrity="fixture", archive_sha256=hashlib.sha256(raw).hexdigest())
                    for v, raw in releases.items()}}

        def content(self, package, version, path):
            assert (package, path) == ("math-kit", "util/Math.sol")
            return releases[version]

    project = resolve_project(tmp_path, put(tmp_path, "Main.sol", CLIENT))
    store = ArtifactStore(tmp_path / "results")
    result = repair_unit(CompilationUnit("probe", project.files), {VERSION: trusted_compilers()[VERSION]},
                         store, io.StringIO(), project=project, offline_index=Index(),
                         dependency_policy="latest", dependency_limit=limit)
    steps = json.loads((store.path / "units/probe/repair_steps.json").read_bytes())
    checks = [row for row in steps if row.get("operation") == "candidate_checks"][-1]
    compiled = [row for row in steps if "combination_ordinal" in row]
    assert [row["combination_ordinal"] for row in compiled] == ordinals
    assert [row["releases"]["math-kit"]["version"] for row in compiled] == list(releases)[:len(ordinals)]
    assert checks["compiled_combinations"] == len(ordinals)
    assert checks["first_d3_combination"] == (2 if success else None)
    assert checks["truncated"] is truncated
    assert ("dependency_search_truncated" in result.flags) is truncated
    assert (result.status == "success") is success


def test_json_benchmark_reports_recovery_on_all_rows():
    from compile_repair.evaluation.report import dependency_benchmark_summary
    rows = []
    for success, affected, lost, added in [(True, 4, 0, 0), (False, 7, 7, 3)]:
        score = dict(compiled=success, exact=success, affected_by_damage=affected, lost=lost, added=added,
                     removed_by_repair=0, counter_correspondence={"status": "identical" if success else "rejected"})
        rows.append(dict(split="test", operator="standard_json_input", score=score, change_level="none"))
    report = dependency_benchmark_summary(rows)["test"]["standard_json_input"]
    assert (report["units"], report["recovered_nodes"], report["lost"], report["added"]) == (2, 4, 7, 3)
    assert report["exact_ratio"] == 0.5 and report["names"]["rejected"] == 1
    assert "kept" not in json.dumps(report)


def test_moved_relative_file_in_normal_repair(tmp_path):
    from compile_repair.core.store import sha256
    from compile_repair.evaluation.benchmark import (
        assess_mutation, build_mutation, dependency_repair_observation, relative_move_site)
    from compile_repair.tests.test_cp5 import CLIENT, LIB, VERSION, put
    from compile_repair.toolchain.project import resolve_project
    production_required()
    inputs = tmp_path / "truth"
    main = put(inputs, "src/App.sol", CLIENT.replace(b"math-kit/util/Math.sol", b"../lib/Math.sol"))
    put(inputs, "lib/Math.sol", LIB)
    original = {"src/App.sol": main.read_bytes(), "lib/Math.sol": LIB}
    project = resolve_project(inputs, main)
    env = {VERSION: trusted_compilers()[VERSION]}
    truth = ArtifactStore(tmp_path / "truth-result")
    initial = repair_unit(CompilationUnit("fixture", project.files), env, truth, io.StringIO(),
                          project=project, environment_only=True)
    assert initial.status == "success"
    graph = truth.path / "units/fixture/graph.json"
    base = dict(unit_id="fixture", project_root=str(inputs), entry=str(main), group="fixture", split="dev",
                corpus="fixture", series="0.8", version=VERSION, settings=[], remappings=[],
                graph_path=str(graph), graph_sha256=sha256(graph))
    op = "missing_relative_file_moved"
    site = relative_move_site(base, original, project.imports)
    source, _, _, dest, _, _ = site
    assert (source, dest) == ("lib/Math.sol", ".cp5_moved/Math.sol")
    damaged, patch, _ = build_mutation(base, original, site, op)
    assert patch is None and damaged == {"src/App.sol": original["src/App.sol"], dest: LIB}
    folder = tmp_path / "damage"
    trigger = assess_mutation(base, op, 20261122, original, site, env, (), folder)
    assert trigger["outcome"] == "included" and "missing_relative_file" in trigger["environment_categories"]
    manifest = json.loads((folder / "mutation.json").read_bytes())
    assert manifest["move"]["sha256"] == hashlib.sha256(LIB).hexdigest()
    observed = dependency_repair_observation(base, manifest, original, damaged, {}, folder / "damaged",
                                             env, (), None, "latest", tmp_path / "repair")
    assert observed["accepted_steps"] == [4]
    assert observed["score"]["compiled"] and observed["score"]["kept"]["ratio"] == 1
    assert observed["score"]["removed_by_repair"] == 0
    put(inputs, dest, b"a colliding file outside the original closure")
    assert relative_move_site(base, original, project.imports) is None
