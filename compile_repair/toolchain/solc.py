"""CP0 compiler inventory and invocation (PROMPTS 4.2.3-4).

Reuse frozen inventory/trust checks and crytic-compile 0.2.4 output options.
No installation, PATH modification, global solc selection or source writes.
"""
import hashlib
import os
import re
import subprocess
import time
from pathlib import Path

from compile_repair.core.model import Compilation, Compiler


def version_tuple(version):
    """Parse an exact release number; reject ambiguous or nonnumeric versions."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Expected exact compiler version: " + version)
    return tuple(map(int, version.split(".")))


def verify_binary(compiler):
    """Return the explicit executable path after SHA256 and executable checks."""
    path = Path(compiler.path)
    if not path.is_absolute() or not path.is_file():
        raise ValueError("Compiler must be an existing absolute file")
    if hashlib.sha256(path.read_bytes()).hexdigest() != compiler.sha256:
        raise ValueError("Compiler SHA256 mismatch: " + compiler.version)
    if not os.access(str(path), os.X_OK):
        raise ValueError("Compiler is not executable: " + str(path))
    return str(path)


def inventory(trusted):
    """Inventory existing binaries; return verified compilers and missing refs.

    A wrong hash or incompatible environment raises, while absent binaries are
    reported to the survey. Trusted records are supplied by a sealed manifest.
    """
    from scripts.DFG.dfg_v2.validate_slither import (
        inspect_environment, compiler_for_selection)
    environment = inspect_environment()
    if environment["skip_reasons"]:
        raise ValueError(";".join(environment["skip_reasons"]))
    if environment["packages"]["crytic-compile"] != "0.2.4":
        raise ValueError("CP0 requires crytic-compile 0.2.4")
    compilers, missing = {}, []
    for version in sorted(trusted, key=version_tuple):
        ref = trusted[version]
        if not Path(ref["path"]).is_file():
            missing.append(version)
            continue
        path, reason = compiler_for_selection(
            {"version": version}, environment, trusted)
        if reason:
            raise ValueError(reason)
        compilers[version] = Compiler(version, path, ref["sha256"])
    paths = {c.path for c in compilers.values()}
    environment["installed_without_trusted_match"] = [
        r for r in environment["installed_compilers"] if r["path"] not in paths]
    return compilers, environment, missing


def command(source, compiler, cwd=None):
    """Build crytic-compile 0.2.4's default single-file solc argv.

    Uses its original _build_options; matches _run_solc's allow-paths handling.
    No optimizer, remappings, legacy override or project/package manager.
    """
    from crytic_compile.platform.solc import _build_options, CompilerVersion
    source = str(Path(source).resolve())
    cwd = str(Path(cwd or Path.cwd()).resolve())
    options = _build_options(CompilerVersion("solc", compiler.version, False), False)
    argv = [compiler.path, source, "--combined-json", options]
    if version_tuple(compiler.version) not in [(0, 4, i) for i in range(11)]:
        relative = source[len(cwd) + 1:] if source.startswith(cwd) else source
        argv += ["--allow-paths", ".", relative]
    return argv


def error_first_line(stderr):
    """Prefer the first diagnostic Error line over banners and warnings."""
    lines = [s.strip() for s in stderr.splitlines() if s.strip()]
    return next((s for s in lines if re.search(r"\b(?:[A-Za-z]*Error|error):", s)),
                lines[0] if lines else None)


def compile_file(source, compiler, timeout=120):
    """Compile one unchanged file and capture its actual process exit code.

    Timeout is a recorded result, never retried; trust or IO failures raise.
    The command emits JSON to memory and writes no compiler output files.
    """
    source = Path(source).resolve()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    verify_binary(compiler)
    argv, cwd = command(source, compiler), str(Path.cwd())
    start = time.monotonic()
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, cwd=cwd)
        stdout, stderr = result.stdout, result.stderr
        rc, timed_out = result.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        rc, timed_out = None, True
    elapsed = time.monotonic() - start
    if hashlib.sha256(source.read_bytes()).hexdigest() != before:
        raise ValueError("Source changed during compilation")
    diagnostic = stderr.decode("utf8", errors="replace")
    first = "timeout" if timed_out else error_first_line(diagnostic) if rc != 0 else None
    return Compilation(str(source), before, compiler, argv, cwd, rc, first,
                       diagnostic, hashlib.sha256(stdout).hexdigest(), elapsed, timed_out)
