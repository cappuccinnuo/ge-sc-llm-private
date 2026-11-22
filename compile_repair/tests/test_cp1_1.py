"""CP1.1 path boundaries, per-input timeouts and git-independent sealing."""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

import pytest

from compile_repair.core.model import Compilation, Compiler
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair, repair_unit, _code_commit
from compile_repair.tests.test_pipeline import unit_for
from compile_repair.tests.test_production import production_required, trusted_compilers
from compile_repair.toolchain.solc import command, compile_file, version_tuple
from compile_repair.toolchain.slither import run_slither

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "compile_repair/tests/fixtures"


@contextmanager
def in_directory(path):
    previous = Path.cwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(str(previous))


def old_command(source, compiler, cwd, settings=()):
    """Test-only reference: command() at d4f4b48a before the boundary fix."""
    from crytic_compile.platform.solc import _build_options, CompilerVersion
    source, cwd = str(Path(source).resolve()), str(Path(cwd).resolve())
    options = _build_options(CompilerVersion("solc", compiler.version, False), False)
    argv = [compiler.path, source, "--combined-json", options]
    if version_tuple(compiler.version) not in [(0, 4, i) for i in range(11)]:
        relative = source[len(cwd) + 1:] if source.startswith(cwd) else source
        argv += ["--allow-paths", ".", relative]
    return argv + list(settings)


def test_frozen_argv_equivalence(tmp_path):
    artifacts = ROOT / "compile_repair/artifacts"
    cp0 = json.loads((artifacts / "cp0_v2/recon.json").read_text())
    plan = json.loads((artifacts / "cp0_1_compilers_v2/compatibility_plan.json").read_text())
    compilers = trusted_compilers()
    rows = []
    assert len(cp0["inputs"]) == 846 and len(plan["jobs"]) == 501
    jobs = [(r["path"], r["selection"]["ascending"], (), "MANDO") for r in cp0["inputs"]]
    jobs += [(r["fixture"], r["version"], tuple(r["settings"]), "compatibility") for r in plan["jobs"]]
    for path, version, settings, group in jobs:
        before = old_command(ROOT / path, compilers[version], ROOT, settings)
        after = command(ROOT / path, compilers[version], cwd=ROOT, settings=settings)
        rows.append(dict(path=path, version=version, settings=settings, group=group,
                         old_argv=before, new_argv=after, equal=before == after))
    (tmp_path / "argv_equivalence.json").write_text(json.dumps(rows, indent=2), encoding="utf8")
    assert all(r["equal"] for r in rows)


@pytest.mark.parametrize("mode", ["root", "prefix_sibling", "unrelated", "ancestor", "parent"])
def test_real_solc_path_boundaries(tmp_path, mode):
    source = tmp_path / "out2/input.sol"
    source.parent.mkdir()
    source.write_bytes((FIXTURES / "compat_05.sol").read_bytes())
    sibling, unrelated = tmp_path / "out", tmp_path / "other"
    sibling.mkdir()
    unrelated.mkdir()
    cwd = dict(root=Path("/"), prefix_sibling=sibling, unrelated=unrelated,
               ancestor=tmp_path, parent=source.parent)[mode]
    with in_directory(cwd):
        compiled = compile_file(source, trusted_compilers()["0.5.17"])
    (tmp_path / "path_invocation.json").write_text(json.dumps(asdict(compiled), indent=2), encoding="utf8")
    assert compiled.returncode == 0 and not compiled.timed_out
    expected = str(source) if mode in ("prefix_sibling", "unrelated") else str(source.relative_to(cwd))
    assert compiled.command[-1] == expected


@pytest.mark.parametrize("mode", ["root", "prefix_sibling"])
def test_regression_6c_rejects_unsafe_cwd_before_any_tool(tmp_path, mode):
    source = tmp_path / "out2/input.sol"
    cwd = Path("/") if mode == "root" else tmp_path / "out"
    if mode != "root":
        cwd.mkdir()
    # Neither source nor executable exists: a tool/integrity call would fail
    # differently, proving this guard runs before frozen _compile is invoked.
    compilation = Compilation(str(source), "unused", Compiler("0.5.17", "/absent", "unused"),
                              [], str(cwd), 0, None, "", "", 0, False)
    with in_directory(cwd), pytest.raises(ValueError, match="regression_6c refuses unsafe working directory"):
        run_slither(compilation, profile="regression_6c")


@pytest.mark.parametrize("mode", ["initial", "after_slither", "settings_retry"])
def test_timeout_is_a_complete_unrepaired_record_without_retry(tmp_path, mode):
    settings_case = mode == "settings_retry"
    raw = (b"pragma solidity ^0.8.24; contract C { function f() public { assembly { pop(tload(0)) } } }"
           if settings_case else b"pragma solidity ^0.4.12; contract C {}")
    versions = ("0.8.24", "0.8.25") if settings_case else ("0.4.12", "0.4.17", "0.4.26")
    compilers = {v: Compiler(v, "/unused/" + v, "unused") for v in versions}
    calls, analyses = [], []
    def compile_fn(path, compiler, settings=()):
        calls.append((compiler.version, settings))
        timeout = mode == "initial" or len(calls) == 2
        rc = None if timeout else 1 if settings_case else 0
        diagnostic = 'Error: Function "tload" not found.' if settings_case and not timeout else "timeout" if timeout else None
        return Compilation(str(path), hashlib.sha256(path.read_bytes()).hexdigest(), compiler,
                           [compiler.path, str(path)] + list(settings), str(tmp_path),
                           rc, diagnostic, diagnostic or "", "", 0.1, timeout, settings=settings)
    def slither_fn(compilation, profile):
        analyses.append(compilation.compiler.version)
        return dict(d3=False, nodes=[], exception_type="FixtureFailure", error_first_line="D3 failure")
    store, journal = ArtifactStore(tmp_path / "run"), io.StringIO()
    record = repair_unit(unit_for(raw), compilers, store, journal, compile_fn=compile_fn, slither_fn=slither_fn)
    assert record.status == "unrepaired" and record.reason == "solc_timeout"
    assert record.selected_version is None
    assert len(calls) == (1 if mode == "initial" else 2)
    assert len(analyses) == (1 if mode == "after_slither" else 0)
    if settings_case:
        assert calls == [("0.8.24", ()), ("0.8.24", ("--evm-version", "cancun"))]
    persisted = json.loads((store.path / "units/test_input/result.json").read_text())
    assert persisted["reason"] == "solc_timeout"
    assert persisted["attempts"][-1]["solc"]["timed_out"]
    assert json.loads(journal.getvalue().splitlines()[-1])["timed_out"]
    assert not (store.path / "units/test_input/nodes.json").exists()
    assert (store.path / "units/test_input/input.sol").read_bytes() == raw


@pytest.mark.parametrize("failure", ["timeout", "trust"])
def test_batch_continues_only_after_timeout(tmp_path, failure):
    production_required()
    paths = [tmp_path / "first.sol", tmp_path / "second.sol"]
    raw = b"pragma solidity ^0.4.12; contract C { function f() public returns(uint) { return 1; } }"
    for path in paths:
        path.write_bytes(raw)
    calls = []
    def compile_fn(path, compiler, settings=()):
        calls.append((str(path), compiler.version))
        if len(calls) == 1:
            if failure == "trust":
                raise ValueError("Compiler SHA256 mismatch: injected trust failure")
            return Compilation(str(path), hashlib.sha256(path.read_bytes()).hexdigest(), compiler,
                               [compiler.path, str(path)], str(Path.cwd()), None, "timeout",
                               "", "", 0.1, True, settings=settings)
        return compile_file(path, compiler, settings=settings)
    output = tmp_path / "batch"
    summary = repair(paths, output, compile_fn=compile_fn)
    records = [json.loads(s) for s in (output / "manifest.jsonl").read_text().splitlines()]
    if failure == "timeout":
        assert summary["status"] == "unrepaired"
        assert [r["status"] for r in records] == ["unrepaired", "success"]
        assert records[0]["reason"] == "solc_timeout"
        assert len(records[0]["attempts"]) == 1
        assert len(calls) == 2 and "input_0002" in calls[1][0]
    else:
        assert summary["status"] == "stopped" and summary["exception_type"] == "ValueError"
        assert records == [] and len(calls) == 1
    assert all(p.read_bytes() == raw for p in paths)
    seal = json.loads((output / "seal.json").read_text())
    for name, digest in seal["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest


def test_commit_unavailable_outside_git(tmp_path):
    assert _code_commit(tmp_path) is None


@pytest.mark.parametrize("missing_git", [False, True])
def test_relocated_module_seals_without_git(tmp_path, missing_git):
    production_required()
    # Relocate the CP4 implementation and the two pinned manifests. Frozen modules
    # are imported read-only from ROOT.
    relocated = tmp_path / "distribution"
    module = ROOT / "compile_repair"
    files = list(module.glob("*.py")) + [p for folder in module.iterdir()
        if folder.is_dir() and folder.name not in ("tests", "docs", "artifacts")
        for p in folder.rglob("*.py")]
    assert len(files) == 17
    assert module / "evaluation" / "benchmark.py" in files
    for source in files + [module / "artifacts/cp0_v2/recon.json",
                           module / "artifacts/cp0_1_compilers_v1/trusted_compilers_addition.json"]:
        target = relocated / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(target))
    source = tmp_path / "input.sol"
    source.write_bytes(b"pragma solidity 0.4.12; contract C {}")
    output = tmp_path / "sealed"
    env = dict(os.environ, PYTHONPATH=str(relocated) + os.pathsep + str(ROOT),
               PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
        env.pop(key, None)
    if missing_git:
        env["PATH"] = str(tmp_path / "no-executables")
    argv = [sys.executable, "-B", "-m", "compile_repair.cli", "repair", str(source), "--output", str(output)]
    result = subprocess.run(argv, cwd=str(relocated), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (tmp_path / "relocated_cli.json").write_text(json.dumps(dict(
        command=argv, missing_git=missing_git, returncode=result.returncode,
        stdout=result.stdout.decode(), stderr=result.stderr.decode()), indent=2), encoding="utf8")
    assert result.returncode == 0, result.stderr.decode()
    summary = json.loads((output / "summary.json").read_text())
    seal = json.loads((output / "seal.json").read_text())
    assert summary["status"] == "complete" and summary["flags"] == ["code_commit_unavailable"]
    assert seal["code_commit"] is None
    assert set(seal["implementation_sha256"]) == {str(p.relative_to(ROOT)) for p in files}
    for name, digest in seal["implementation_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    for name, digest in seal["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
