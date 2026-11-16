"""Installed Slither/solc identities and trusted compiler selection (no installs, no network).

Moved unchanged from scripts/DFG/dfg_v2/validate_slither.py (archive branch), which the DFG
restructure removed; compile_repair is its only user.
"""
import hashlib
import importlib.util
import os
import shutil
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _checked(ref):
    path = Path(ref["path"]).resolve()
    if _sha(path) != ref["sha256"]:
        raise ValueError("SHA mismatch: " + str(path))
    return path


def inspect_environment():
    """Read installed module/package/compiler identities without subprocesses."""
    def found(name):
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        return str(spec.origin) if spec else None

    packages = {}
    try:
        import importlib_metadata
        for name in ("slither-analyzer", "solc-select", "crytic-compile"):
            try:
                packages[name] = importlib_metadata.version(name)
            except importlib_metadata.PackageNotFoundError:
                packages[name] = None
    except ImportError:
        packages["metadata_unavailable"] = True
    modules = {name: found(name) for name in ("slither", "solc_select", "crytic_compile")}
    commands = {name: shutil.which(name) for name in ("slither", "solc-select", "solc")}
    artifacts = Path.home() / ".solc-select/artifacts"
    installed = []
    if artifacts.is_dir():
        for path in sorted(artifacts.glob("solc-*/solc-*")):
            if path.is_file():
                installed.append(dict(path=str(path.resolve()), sha256=_sha(path),
                                      bytes=path.stat().st_size))
    reasons = []
    if not modules["slither"]:
        reasons.append("slither_analyzer_unavailable")
    if not modules["crytic_compile"]:
        reasons.append("crytic_compile_unavailable")
    if packages.get("slither-analyzer") != "0.8.0":
        reasons.append("unsupported_or_unverified_slither_version")
    if not modules["solc_select"] or not commands["solc-select"]:
        reasons.append("solc_select_unavailable")
    if not installed:
        reasons.append("no_local_solc_select_artifacts")
    return dict(modules=modules, commands=commands, packages=packages,
                installed_compilers=installed, skip_reasons=reasons,
                compiler_executed=False, installation_attempted=False,
                network_requested=False)


def _compile(path, compiler):
    # Only reached for an existing, hash-inventoried, explicitly trusted binary.
    # A .sol file plus an absolute compiler path avoids package-manager builds.
    from slither.slither import Slither
    return Slither(str(path), solc=str(compiler), solc_disable_warnings=True)


def compiler_for_selection(selection, environment, trusted=None):
    """Require explicit trusted SHA and inventoried binary; never install."""
    if environment["skip_reasons"]:
        return None, ";".join(environment["skip_reasons"])
    version = selection["version"]
    if not trusted or version not in trusted:
        return None, "local_compiler_not_explicitly_authorized"
    ref = trusted[version]
    path = _checked(ref)
    inventory = {entry["path"]: entry["sha256"]
                 for entry in environment["installed_compilers"]}
    if inventory.get(str(path)) != ref["sha256"]:
        raise ValueError("Trusted compiler is not an inventoried local solc-select artifact")
    if not os.access(str(path), os.X_OK):
        return None, "local_compiler_not_executable"
    return str(path), None
