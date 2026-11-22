"""PROMPTS 4.5/3.2 step 2: read-only import closures and matching CLI/API calls.

No package installation, basename repair, framework execution or source rewrite.
A project records unresolved imports explicitly; compilers still decide syntax.
"""
import json
import hashlib
import posixpath
import re
import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path

from compile_repair.core.model import Compilation, SourceFile
from compile_repair.toolchain.solc import (
    error_first_line, lexical_tokens, validate_settings, verify_binary)


@dataclass(frozen=True)
class Project:
    """One entry and its closed local sources, or explicit resolution issues."""
    root: str
    entry: str
    remappings: tuple
    files: tuple
    source_units: tuple
    imports: tuple
    issues: tuple

    def manifest(self):
        """Return provenance and path metadata without copying source contents."""
        return {"root": self.root, "entry": self.entry, "remappings": self.remappings,
                "files": [{"path": f.path, "sha256": f.sha256, "bytes": len(f.content)}
                          for f in self.files], "source_units": self.source_units,
                "imports": self.imports, "issues": self.issues}


def solidity_snippet_evidence(source):
    """Classify input language lexically; retain malformed Solidity for solc.

    Comments and string literals cannot claim a language. Recognizable pragma,
    contract/interface/library or function declarations admit snippets, including
    truncated declarations. Other text is reported separately, never repaired.
    This conservative evidence rule is independent of compilation success.
    """
    from compile_repair.toolchain.solc import lexical_tokens
    tokens = [(kind, raw) for _, _, kind, raw in lexical_tokens(source)]
    for index, (kind, raw) in enumerate(tokens):
        if kind != "word":
            continue
        rest = tokens[index + 1:index + 4]
        if raw == b"pragma" and rest and rest[0][1] == b"solidity":
            return {"is_solidity": True, "basis": "solidity_pragma", "token_index": index}
        if raw in (b"contract", b"interface", b"library") and rest and rest[0][0] == "word":
            if len(rest) == 1 or rest[1][1] in (b"{", b"is"):
                return {"is_solidity": True, "basis": "solidity_declaration", "token_index": index}
        if raw == b"function" and rest:
            if rest[0][1] == b"(" or rest[0][0] == "word" and (
                    len(rest) == 1 or rest[1][1] == b"("):
                return {"is_solidity": True, "basis": "function_fragment", "token_index": index}
    return {"is_solidity": False, "basis": "no_solidity_declaration_evidence",
            "empty_or_comments_only": not tokens}


_NOT_JSON = object()


def _reject_json_constant(value):
    raise ValueError("Invalid JSON constant: " + value)


def _input_json(raw):
    raw = raw.strip()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:].strip()
    if not raw or raw[:1] not in b'{["-0123456789tfn':
        return _NOT_JSON
    if raw.startswith(b"{{") and raw.endswith(b"}}"):
        raw = raw[1:-1]
    try:
        return json.loads(raw, parse_constant=_reject_json_constant)
    except (ValueError, RecursionError):
        return _NOT_JSON


def _source_wrapper(obj):
    if not isinstance(obj, dict) or obj.get("language", "Solidity") != "Solidity":
        return None

    def missing_count(entries):
        return sum(not isinstance(item, dict) or not isinstance(item.get("content"), str)
                   for item in entries.values())

    sources = obj.get("sources")
    missing = 0
    if isinstance(sources, dict):
        missing = missing_count(sources)
    if not isinstance(sources, dict) or (missing and "language" not in obj):
        if "language" in obj or missing_count(obj):
            return None
        sources, missing = obj, 0
    settings = obj.get("settings")
    metadata = {"source_count": len(sources), "source_names": sorted(sources),
                "settings_keys": sorted(settings) if isinstance(settings, dict) else []}
    if missing:
        metadata.update(content_missing=True, missing_source_count=missing)
    return metadata


def standard_json_input(raw):
    """Describe a Solidity source wrapper, counting entries CP5 cannot unpack."""
    return _source_wrapper(_input_json(raw))


_VYPER_LINES = {
    "version": rb"^[ \t]*(#)[ \t]*(?:@version|pragma[ \t]+version)[ \t]+[~^<>=! \t]*[0-9]+\.[0-9]+(?:\.[0-9]+)?(?=[ \t\r\n]|$)",
    "decorator": rb"^[ \t]*(@)(?:external|internal|deploy)[ \t]*(?:#[^\r\n]*)?\r?$",
    "function": rb"^[ \t]*(def)[ \t]+[A-Za-z_]\w*[ \t]*\([^\r\n#]*\)[ \t]*(?:->[ \t]*[^:\r\n#]+)?[ \t]*:",
    "declaration": rb"^[ \t]*(event[ \t]+[A-Za-z_]\w*[ \t]*:|[A-Za-z_]\w*[ \t]*:[ \t]*public[ \t]*\()",
}


def _vyper_basis(raw):
    """Require a version directive or corroborating Vyper declarations outside literals/comments."""
    if b"#" not in raw and b"@" not in raw:
        return None
    positions = {m.start(1): name for name, pattern in _VYPER_LINES.items()
                 for m in re.finditer(pattern, raw, re.MULTILINE)}
    if positions:
        found = {positions[lo] for lo, _, kind, _ in lexical_tokens(raw)
                 if lo in positions and kind != "string"}
        if "version" in found:
            return "vyper_version_directive"
        if {"decorator", "function", "declaration"} <= found:
            return "vyper_decorated_function_and_declaration"
    return None


def input_format_evidence(raw):
    """Return entry language evidence and optional wrapper metadata, without running tools.

    Unknown inputs continue through the same pipeline as recognized Solidity.
    The original snippet rule supplies positive lexical evidence only.
    """
    obj = _input_json(raw)
    wrapper = _source_wrapper(obj)
    if wrapper is not None:
        return {"status": "solidity", "basis": "source_wrapper"}, wrapper
    if obj is not _NOT_JSON:
        language = obj.get("language") if isinstance(obj, dict) else None
        if isinstance(language, str) and language.strip():
            status = "solidity" if language == "Solidity" else "non_solidity"
            return {"status": status, "basis": "json_language", "language": language}, None
        return {"status": "unknown", "basis": "no_json_language"}, None
    vyper = _vyper_basis(raw)
    if vyper:
        return {"status": "non_solidity", "basis": vyper, "language": "Vyper"}, None
    evidence = solidity_snippet_evidence(raw)
    evidence["status"] = "solidity" if evidence.pop("is_solidity") else "unknown"
    return evidence, None


def import_directives(source):
    """Read all quoted top-level import forms, ignoring comments/literal fakes.

    Return literal spelling and positions. Incomplete/malformed declarations are
    left to solc; unsupported path escapes are explicit resolution issues.
    """
    depth, start, literals = 0, None, []
    for lo, hi, kind, token in lexical_tokens(source):
        if token == b"{":
            # Braces inside import {X as Y} are not contract/function bodies.
            if start is None:
                depth += 1
        elif token == b"}":
            if start is None:
                depth = max(0, depth - 1)
        elif token == b"import" and depth == 0:
            start, literals = lo, []
        elif start is not None and kind == "string":
            literals.append((lo, hi, token[1:-1]))
        elif start is not None and token == b";":
            if len(literals) == 1:
                a, b, raw = literals[0]
                # Solidity path literals share simple quote/backslash escapes.
                valid = not re.search(rb'\\(?![\\\'"])', raw)
                value = re.sub(rb'\\([\\\'"])', rb'\1', raw) if valid else raw
                try:
                    name = value.decode("utf8")
                except UnicodeDecodeError:
                    name, valid = value.decode("latin1"), False
                yield {"path": name, "literal_hex": raw.hex(),
                       "start": start, "end": hi, "literal_start": a, "literal_end": b,
                       "line": source[:start].count(b"\n") + 1,
                       "supported_literal": valid}
            start, literals = None, []


def parse_remapping(value):
    """Parse [context:]prefix=target; reject empty prefixes and CLI-like tokens."""
    if not isinstance(value, str) or "=" not in value or "\x00" in value or "\n" in value:
        raise ValueError("Expected [context:]prefix=target remapping")
    left, target = value.split("=", 1)
    context, sep, prefix = left.rpartition(":")
    if not sep:
        context, prefix = "", left
    if not prefix or value.startswith("-"):
        raise ValueError("Empty or option-like remapping prefix")
    return context, prefix, target


def source_unit_name(importer, imported, remappings=()):
    """Resolve VFS-relative paths then the single longest matching remapping.

    Direct imports are not normalized. Remapping targets are literal; there is
    no automatic slash insertion or second remapping pass (official v0.8.38).
    """
    if imported.startswith(("./", "../")):
        parts = importer.split("/")[:-1]
        for part in imported.split("/"):
            if part in ("", "."):
                continue
            if part == ".." and parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append(part)
        name = "/".join(parts)
    else:
        name = imported
    matches = []
    for index, raw in enumerate(remappings):
        context, prefix, target = parse_remapping(raw)
        if importer.startswith(context) and name.startswith(prefix):
            matches.append((len(context), len(prefix), index, prefix, target))
    if matches:
        _, _, _, prefix, target = max(matches)
        name = target + name[len(prefix):]
    return name


def project_entries(root):
    """List project .sol entries deterministically; never traverse symlinks."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Project root must be a directory")
    return tuple(p for p in sorted(root.rglob("*.sol"))
                 if p.is_file() and not p.is_symlink()
                 and not any(q.is_symlink() for q in p.parents if q != root)
                 and ".git" not in p.relative_to(root).parts)


class ProjectIndex:
    """Reuse one deterministic project file inventory across entry closures."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.entries = project_entries(self.root)
        self.members = set(self.entries)
        self.names = {}
        for path in self.entries:
            self.names.setdefault(path.name, []).append(path)


def _local_path(root, name):
    if name.startswith(("/", "file:", "http:", "https:")):
        return None, "absolute_or_url_import_requires_external_resolution"
    candidate = root / name
    resolved = candidate.resolve()
    if root != resolved and root not in resolved.parents:
        return None, "import_outside_project"
    if any(p.is_symlink() for p in [candidate] + list(candidate.parents) if p != root):
        return None, "symlink_import_not_followed"
    return resolved, None


def resolve_project(root, entry, remappings=(), index=None):
    """Resolve a transitive closure within one supplied project, without repairs.

    Missing paths, unsupported external imports and alias cycles are recorded.
    Basename candidates are counted only; they never change resolution.
    """
    root = Path(root).resolve()
    index = index or ProjectIndex(root)
    if index.root != root:
        raise ValueError("Project index belongs to another root")
    entry_path = Path(entry)
    entry_path = (root / entry_path).resolve() if not entry_path.is_absolute() else entry_path.resolve()
    if entry_path not in index.members:
        raise ValueError("Project entry must be a local .sol file under root")
    remappings = tuple(remappings)
    for value in remappings:
        parse_remapping(value)
    names = index.names
    entry_name = entry_path.relative_to(root).as_posix()
    queue = [(entry_name, ())]; visited, files, imports, issues = {}, {}, [], []
    while queue:
        unit_name, ancestry = queue.pop()
        if unit_name in visited:
            continue
        path, problem = _local_path(root, unit_name)
        if problem or path is None or not path.is_file():
            raise ValueError("Internal closure queue contains an unresolved import")
        raw = path.read_bytes()
        visited[unit_name] = path.relative_to(root).as_posix()
        files[str(path)] = SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw, "project")
        if str(path) in ancestry:
            issues.append({"category": "io_error", "reason": "source_unit_alias_cycle",
                           "source_unit": unit_name, "path": str(path)})
            continue
        for directive in import_directives(raw):
            imported = directive["path"]
            target_name = source_unit_name(unit_name, imported, remappings)
            target, problem = _local_path(root, target_name)
            if not directive["supported_literal"]:
                target, problem = None, "unsupported_import_escape"
            found = target is not None and target.is_file()
            relative = imported.startswith(("./", "../"))
            row = dict(directive, importer=unit_name, source_path=str(path),
                       target_source_unit=target_name, resolved=found,
                       target_path=str(target) if found else None)
            if not found:
                category = "io_error" if problem else (
                    "missing_relative_file" if relative else "unresolved_package_import")
                row.update(category=category, reason=problem or "file_not_found")
                if relative:
                    candidates = names.get(posixpath.basename(imported), [])
                    row.update(basename_candidates=[str(p) for p in candidates],
                               candidate_count=len(candidates),
                               candidate_kind="none" if not candidates else "unique" if len(candidates) == 1 else "multiple")
                elif category == "unresolved_package_import":
                    row["package"] = "/".join(imported.split("/")[:2]) if imported.startswith("@") else imported.split("/")[0]
                issues.append(row)
            else:
                queue.append((target_name, ancestry + (str(path),)))
            imports.append(row)
    ordered = [files.pop(str(entry_path))] + [files[p] for p in sorted(files)]
    return Project(str(root), entry_name, remappings, tuple(ordered),
                   tuple(sorted(visited.items())), tuple(imports), tuple(issues))


def materialize_project(project, store, prefix, contents=None):
    """Write only closure files to a fresh work tree, preserving relative paths.

    contents maps original absolute paths to already-verified working bytes.
    The returned Project points to copies; the original Project remains intact.
    """
    root = Path(project.root)
    copies = []
    for source in project.files:
        raw = (contents or {}).get(source.path, source.content)
        relative = Path(source.path).relative_to(root).as_posix()
        path = store.write_bytes(prefix + "/" + relative, raw)
        copies.append(SourceFile(str(path), hashlib.sha256(raw).hexdigest(), raw, "project"))
    return replace(project, root=str(store.path / prefix), files=tuple(copies))


def verify_project(project):
    """Fail on missing or changed closure files, including non-entry inputs."""
    for source in project.files:
        if hashlib.sha256(Path(source.path).read_bytes()).hexdigest() != source.sha256:
            raise ValueError("Project source changed: " + source.path)


def _entry_argument(project):
    """Keep a relative entry beginning with '-' from becoming a compiler option."""
    return "./" + project.entry if project.entry.startswith("-") else project.entry


def project_command(project, compiler, settings=()):
    """Assemble the same combined-json argv as crytic-compile's solc platform."""
    from crytic_compile.platform.solc import _build_options, CompilerVersion
    settings = validate_settings(settings)
    options = _build_options(CompilerVersion("solc", compiler.version, False), False)
    return [compiler.path] + list(project.remappings) + [
        _entry_argument(project), "--combined-json", options, "--allow-paths",
        str(Path(project.root).resolve())] + list(settings)


def slither_arguments(project, compiler, settings=()):
    """Return matching target/API kwargs for the production Slither invocation."""
    settings = validate_settings(settings)
    return _entry_argument(project), {"solc": compiler.path, "solc_disable_warnings": True,
        "solc_working_dir": project.root, "solc_remaps": list(project.remappings),
        "solc_args": " ".join(("--allow-paths", str(Path(project.root).resolve())) + settings)}


def compile_project(project, compiler, timeout=120, settings=()):
    """Compile a closed working copy once; preserve all hashes and timeout data."""
    if project.issues:
        raise ValueError("Cannot compile an unresolved project closure")
    settings = validate_settings(settings)
    verify_project(project)
    verify_binary(compiler)
    argv, start = project_command(project, compiler, settings), time.monotonic()
    try:
        run = subprocess.run(argv, cwd=project.root, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=timeout)
        stdout, stderr, rc, timed_out = run.stdout, run.stderr, run.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, rc, timed_out = exc.stdout or b"", exc.stderr or b"", None, True
    verify_project(project)
    text = stderr.decode("utf8", errors="replace")
    source = next(f for f in project.files if Path(f.path) == Path(project.root) / project.entry)
    return Compilation(source.path, source.sha256, compiler, argv, project.root, rc,
        "timeout" if timed_out else error_first_line(text) if rc != 0 else None,
        text, hashlib.sha256(stdout).hexdigest(), time.monotonic() - start,
        timed_out, settings=settings)
