"""CP0 compiler inventory and CP0.1 C continuation settings (PROMPTS 4.2c).

Reuse frozen inventory/trust checks and crytic-compile 0.2.4 output options.
No installation, PATH modification, global solc selection or source writes.
"""
import hashlib
import json
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



def load_additions(base, manifests):
    """Extend sealed 6c trust with separately authorized official releases.

    This reads local evidence only. Both binary digests are recomputed; neither
    existing identities nor the frozen 6c manifest can be replaced by additions.
    """
    from Crypto.Hash import keccak

    def linked_json(ref):
        raw = Path(ref["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError("Linked evidence SHA256 mismatch: " + ref["path"])
        return json.loads(raw.decode("utf8"))

    trusted, references, release_index = dict(base), [], None
    for path in manifests:
        path = Path(path).resolve()
        raw = path.read_bytes()
        addition = json.loads(raw.decode("utf8"))
        if addition.get("schema") != "compile-repair-trusted-addition-v1":
            raise ValueError("Unsupported compiler addition schema")
        auth = linked_json(addition["authorization"])
        if auth.get("status") != "approved" or set(auth.get("versions", [])) != set(addition["compilers"]):
            raise ValueError("Compiler additions differ from approved exact versions")
        index = linked_json(addition["official_release_index"])
        if release_index is not None and release_index != index:
            raise ValueError("Compiler additions use different release snapshots")
        builds = {b["path"]: b for b in index["builds"]}
        for version, ref in addition["compilers"].items():
            version_tuple(version)
            if version in trusted:
                raise ValueError("Cannot replace an existing trusted compiler: " + version)
            build = builds[index["releases"][version]]
            expected_path = Path.home() / ".solc-select/artifacts" / ("solc-" + version) / ("solc-" + version)
            if (ref["version"] != version or build["version"] != version or
                    Path(ref["path"]) != expected_path or ref["sha256"] != build["sha256"][2:] or
                    ref["keccak256"] != build["keccak256"][2:] or
                    ref["url"] != "https://binaries.soliditylang.org/linux-amd64/" + build["path"]):
                raise ValueError("Compiler addition disagrees with official release: " + version)
            verify_binary(Compiler(version, ref["path"], ref["sha256"]))
            binary = expected_path.read_bytes()
            if len(binary) != ref["bytes"] or keccak.new(digest_bits=256, data=binary).hexdigest() != ref["keccak256"]:
                raise ValueError("Compiler Keccak256/size mismatch: " + version)
            trusted[version] = ref
        release_index = index
        references.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                           "authorization": addition["authorization"],
                           "official_release_index": addition["official_release_index"]})
    return trusted, references, release_index


def release_coverage(index, installed):
    """Report observed official releases, without extrapolating missing patches."""
    if index is None:
        return {"status": "not_obtained", "series": {}, "all_patch_versions_verified": False}
    series = {}
    for minor in range(4, 9):
        releases = sorted([v for v in index["releases"] if
            (0, 4, 12) <= version_tuple(v) < (0, 9, 0) and version_tuple(v)[:2] == (0, minor)],
            key=version_tuple)
        series["0." + str(minor)] = {"published": releases,
            "installed": [v for v in releases if v in installed],
            "not_installed": [v for v in releases if v not in installed]}
    return {"status": "official_snapshot", "source": "https://binaries.soliditylang.org/linux-amd64/list.json",
            "latest_release_in_snapshot": index["latestRelease"], "series": series,
            "all_patch_versions_verified": False}


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


def validate_settings(settings):
    """Return ordered option tokens as a tuple; reject all non-whitelisted argv.

    Accept only --via-ir and --evm-version followed by one name token. The
    compiler validates EVM names for its release; whitespace, extra switches,
    repeated options and arbitrary command fragments are rejected here.
    """
    if not isinstance(settings, (tuple, list)) or not all(isinstance(s, str) for s in settings):
        raise ValueError("settings must be an ordered sequence of string tokens")
    settings = tuple(settings)
    seen, index = set(), 0
    while index < len(settings):
        option = settings[index]
        if option not in ("--evm-version", "--via-ir") or option in seen:
            raise ValueError("Unsupported or repeated compiler setting: " + option)
        seen.add(option)
        index += 1
        if option == "--evm-version":
            if index == len(settings) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", settings[index]):
                raise ValueError("--evm-version requires one name token")
            index += 1
    return settings


def command(source, compiler, cwd=None, settings=()):
    """Build crytic-compile 0.2.4's default single-file solc argv.

    Uses its original _build_options and allow-paths argument order. CP1.1
    makes the duplicate source argument relative only within cwd's path boundary;
    outside inputs stay absolute. Invalid settings raise before construction.
    Append only validated settings, preserving token order. No optimizer,
    remappings, legacy override or project/package manager.
    """
    settings = validate_settings(settings)
    from crytic_compile.platform.solc import _build_options, CompilerVersion
    source = str(Path(source).resolve())
    cwd = str(Path(cwd or Path.cwd()).resolve())
    options = _build_options(CompilerVersion("solc", compiler.version, False), False)
    argv = [compiler.path, source, "--combined-json", options]
    if version_tuple(compiler.version) not in [(0, 4, i) for i in range(11)]:
        try:
            relative = str(Path(source).relative_to(cwd))
        except ValueError:
            relative = source
        argv += ["--allow-paths", ".", relative]
    return argv + list(settings)


def error_first_line(stderr):
    """Prefer Error diagnostics; retain crash banners and their what() message.

    solc 0.8.26's via-IR requirement is in std::exception::what, not in the
    leading Unimplemented feature banner. Join both onto one diagnostic line;
    Compilation.stderr still preserves the complete original output.
    """
    lines = [s.strip() for s in stderr.splitlines() if s.strip()]
    first = next((s for s in lines if re.search(r"\b(?:[A-Za-z]*Error|error):", s)),
                 lines[0] if lines else None)
    what = next((s for s in lines if s.startswith("std::exception::what:")), None)
    return first + " " + what if what and first != what else first


def compile_file(source, compiler, timeout=120, settings=()):
    """Compile one unchanged file and capture its actual process exit code.

    Timeout is a recorded result, never retried; trust or IO failures raise.
    The command emits JSON to memory and writes no compiler output files.
    """
    settings = validate_settings(settings)
    source = Path(source).resolve()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    verify_binary(compiler)
    argv, cwd = command(source, compiler, settings=settings), str(Path.cwd())
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
                       diagnostic, hashlib.sha256(stdout).hexdigest(), elapsed, timed_out,
                       settings=settings)


# CP1 local trust snapshot; never discover or trust new binaries from PATH.
CP0_SHA256 = "bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6"
ADDITION_SHA256 = "e5fec62afd37874ee46b2d60466bad4e756d8514d0aab118af626e1008e3fdad"


def load_trusted_compilers():
    """Load approved CP0 identities plus C additions; verify every local binary.

    Return compiler records, frozen regression rows and evidence references.
    Missing/changed files raise; this function never installs or downloads.
    """
    from compile_repair.core.store import read_checked_json
    root = Path(__file__).resolve().parents[1] / "artifacts"
    base = root / "cp0_v2/recon.json"
    cp0 = read_checked_json(base, CP0_SHA256)
    addition = root / "cp0_1_compilers_v1/trusted_compilers_addition.json"
    read_checked_json(addition, ADDITION_SHA256)
    refs, additions, _ = load_additions(cp0["compilers"], [addition])
    compilers = {v: Compiler(v, r["path"], r["sha256"]) for v, r in refs.items()}
    for compiler in compilers.values():
        verify_binary(compiler)
    return compilers, cp0["inputs"], {"base": {"path": str(base), "sha256": CP0_SHA256},
                                   "additions": additions}
