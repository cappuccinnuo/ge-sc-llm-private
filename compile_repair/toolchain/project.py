"""PROMPTS 3.2 step 2: read-only Solidity projects, source wrappers and local remappings."""
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
    additional_entries: tuple = ()

    def manifest(self):
        """Return provenance and path metadata without copying source contents."""
        result = {"root": self.root, "entry": self.entry, "remappings": self.remappings,
                "files": [{"path": f.path, "sha256": f.sha256, "bytes": len(f.content)}
                          for f in self.files], "source_units": self.source_units,
                "imports": self.imports, "issues": self.issues}
        if self.additional_entries:
            result["additional_entries"] = self.additional_entries
        return result


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



def _unique_json_pairs(items):
    result = {}
    for key,value in items:
        if key in result:
            raise ValueError("Duplicate key in Solidity input JSON")
        result[key] = value
    return result


def _relative_unit_name(name):
    if (not isinstance(name,str) or not name or name.startswith("/") or "\\" in name or
            "\x00" in name or re.match(r"^[A-Za-z][\w+.-]*:",name)):
        raise ValueError("Expected a relative source unit name")
    normalized = posixpath.normpath(name)
    if normalized in (".","..") or normalized.startswith("../"):
        raise ValueError("Source unit outside project")
    return normalized


def contained_remappings(root, values):
    """Validate literal VFS remappings against a local project and refuse escaping or symlink targets."""
    if not isinstance(values,(list,tuple)):
        raise ValueError("Expected a sequence of remappings")
    checked=[]
    for value in values:
        _,_,target=parse_remapping(value)
        if target and target not in (".","./"):
            _relative_unit_name(target)
        if target:
            _,problem=_local_path(Path(root).resolve(),target)
            if problem:raise ValueError("Unsafe remapping target: "+problem)
        checked.append(value)
    return tuple(checked)


def unpack_sources(raw, store, prefix):
    """Decode a Solidity source wrapper into an exclusive working directory and preserve source-unit identities."""
    data=raw.strip()
    if data.startswith(b"\xef\xbb\xbf"):data=data[3:].strip()
    if data.startswith(b"{{") and data.endswith(b"}}"):data=data[1:-1]
    obj=json.loads(data,object_pairs_hook=_unique_json_pairs,parse_constant=_reject_json_constant)
    meta=_source_wrapper(obj)
    if not meta or not meta["source_count"] or meta.get("content_missing"):
        raise ValueError("No complete inline Solidity source set")
    wrapped=isinstance(obj.get("sources"),dict) and set(obj["sources"])==set(meta["source_names"])
    entries=obj["sources"] if wrapped else obj
    settings=obj.get("settings",{}) if wrapped else {}
    if not isinstance(settings,dict):raise ValueError("Invalid compiler settings object")
    contents={};manifest=[]
    for source_name,fields in entries.items():
        name=_relative_unit_name(source_name)
        if name in contents:raise ValueError("Duplicate normalized source unit: "+name)
        content=fields["content"].encode("utf8")
        if "keccak256" in fields:
            from Crypto.Hash import keccak
            expected=fields["keccak256"]
            if not isinstance(expected,str) or not re.fullmatch(r"0[xX][0-9A-Fa-f]{64}",expected):
                raise ValueError("Invalid source keccak256")
            if keccak.new(digest_bits=256,data=content).hexdigest()!=expected[2:].lower():
                raise ValueError("Source keccak256 mismatch: "+name)
        contents[name]=content
        manifest.append(dict(source_unit=source_name,filename=name,sha256=hashlib.sha256(content).hexdigest()))
    if any(parent.as_posix() in contents for name in contents for parent in Path(name).parents):
        raise ValueError("Source file also used as a directory")
    root=store.path/prefix
    remappings=contained_remappings(root,settings.get("remappings",[]))
    flags,unused=wrapper_settings(settings)
    names=sorted(contents)
    paths=[store.write_bytes(prefix+"/"+n,contents[n]) for n in names]
    index=ProjectIndex(root,paths)
    assembled=resolve_project(root,names[0],remappings,index,additional_entries=names[1:])
    return assembled,flags,dict(wrapper_sha256=hashlib.sha256(raw).hexdigest(),sources=manifest,
                                remappings=remappings,settings=flags,unused_settings=unused)



def wrapper_settings(settings):
    """Map settings expressible by the production CLI and retain the remaining keys for the record."""
    flags=[];unused={k:v for k,v in settings.items() if k not in ("remappings","optimizer","evmVersion","viaIR")}
    optimizer=settings.get("optimizer",{})
    if not isinstance(optimizer,dict):raise ValueError("Invalid optimizer settings")
    enabled=optimizer.get("enabled",False)
    if type(enabled) is not bool:raise ValueError("Invalid optimizer.enabled")
    if enabled:flags.append("--optimize")
    if "runs" in optimizer:
        runs=optimizer["runs"]
        if type(runs) is not int or not 0<=runs<=4294967295:raise ValueError("Invalid optimizer.runs")
        flags.extend(("--optimize-runs",str(runs)))
    unknown={k:v for k,v in optimizer.items() if k not in ("enabled","runs")}
    if unknown:unused["optimizer"]=unknown
    if "evmVersion" in settings:flags.extend(("--evm-version",settings["evmVersion"]))
    if "viaIR" in settings and type(settings["viaIR"]) is not bool:raise ValueError("Invalid viaIR")
    if settings.get("viaIR"):flags.append("--via-ir")
    return validate_settings(tuple(flags)),unused


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
    def __init__(self, root, entries=None):
        self.root = Path(root).resolve()
        self.entries = project_entries(self.root) if entries is None else tuple(entries)
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


def resolve_project(root, entry, remappings=(), index=None, additional_entries=(), contents=None):
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
    remappings = contained_remappings(root, remappings)
    overlays = {}
    for name, data in (contents or {}).items():
        path, problem = _local_path(root, _relative_unit_name(name))
        if problem or not isinstance(data, bytes) or path in overlays:
            raise ValueError("Invalid project source overlay")
        overlays[path] = data
    names = index.names
    entry_name = entry_path.relative_to(root).as_posix()
    extra = tuple(additional_entries)
    if any(root / name not in index.members or _local_path(root, name)[1] for name in extra):
        raise ValueError("Additional compiler input outside project inventory")
    queue = [(n, ()) for n in reversed((entry_name,) + extra)]
    visited, files, imports, issues = {}, {}, [], []
    while queue:
        unit_name, ancestry = queue.pop()
        if unit_name in visited:
            continue
        path, problem = _local_path(root, unit_name)
        if problem or path is None or (path not in overlays and not path.is_file()):
            raise ValueError("Internal closure queue contains an unresolved import")
        raw = overlays[path] if path in overlays else path.read_bytes()
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
            found = target is not None and (target in overlays or target.is_file())
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
                   tuple(sorted(visited.items())), tuple(imports), tuple(issues), extra)


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


def _project_prefix_arguments(project):
    # crytic-compile 0.4.2 forwards this list as separate argv tokens before the
    # main filename. This also compiles disconnected JSON sources in one invocation.
    return list(project.remappings) + ["./"+n if n.startswith("-") else n for n in project.additional_entries]


def project_command(project, compiler, settings=()):
    """Assemble the same combined-json argv as crytic-compile's solc platform."""
    from crytic_compile.platform.solc import _build_options, CompilerVersion
    settings = validate_settings(settings)
    options = _build_options(CompilerVersion("solc", compiler.version, False), False)
    return [compiler.path] + _project_prefix_arguments(project) + [
        _entry_argument(project), "--combined-json", options, "--allow-paths",
        str(Path(project.root).resolve())] + list(settings)


def slither_arguments(project, compiler, settings=()):
    """Return matching target/API kwargs for the production Slither invocation."""
    settings = validate_settings(settings)
    kwargs = {"solc": compiler.path, "solc_disable_warnings": True,
              "solc_working_dir": project.root, "solc_remaps": _project_prefix_arguments(project),
              "solc_args": " ".join(("--allow-paths", str(Path(project.root).resolve())) + settings)}
    if not project.entry.endswith(".sol"):
        kwargs["compile_force_framework"] = "solc"
    return _entry_argument(project), kwargs


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


def _literal_config_remappings(path):
    """Read literal configuration lists without importing or executing the project."""
    raw = path.read_bytes()
    if path.name == "remappings.txt":
        return [line.strip() for line in raw.decode("utf-8-sig").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    if path.name == "foundry.toml":
        import tomli
        config = tomli.loads(raw.decode("utf-8-sig"))
        profiles = config.get("profile", {})
        default = profiles.get("default", {}) if isinstance(profiles, dict) else {}
        if not isinstance(default, dict):
            raise ValueError("Invalid Foundry default profile")
        return default.get("remappings", config.get("remappings", []))
    if path.name == "package.json":
        config = json.loads(raw)
        return config.get("remappings", []) if isinstance(config, dict) else []
    # Accept complete literal JS/TS arrays. Comments and quoted text containing
    # a configuration example do not declare a remapping.
    tokens = [value for _, _, _, value in lexical_tokens(raw)]
    values = []
    for i, token in enumerate(tokens[:-2]):
        if token.strip(b"'\"") != b"remappings" or tokens[i+1:i+3] != [b":", b"["]:
            continue
        literal, expect_value = [], True
        for part in tokens[i+3:]:
            if part == b"]":
                values.extend(literal)
                break
            if expect_value and len(part) >= 2 and part[0] in b"'\"" and part[0] == part[-1] and b"\\" not in part:
                literal.append(part[1:-1].decode("utf8"))
            elif expect_value or part != b",":
                break
            expect_value = not expect_value
    return values


def assembly_remappings(project, index):
    """Propose local remappings with evidence for every suffix and ambiguous target."""
    root = Path(project.root)
    files = set(index.entries)
    scopes = {root}
    for issue in project.issues:
        for parent in Path(issue["source_path"]).parents if "source_path" in issue else ():
            if parent == root or root in parent.parents:
                scopes.add(parent)
    proposed, evidence, declared = [], [], {}
    for folder in sorted(scopes):
        configs = [folder / name for name in ("remappings.txt", "foundry.toml", "package.json")]
        for stem in ("hardhat.config.", "truffle-config."):
            configs.extend(folder / (stem + suffix) for suffix in ("js", "cjs", "mjs", "ts"))
        for config in configs:
            if not config.is_file() or config.resolve() != config:
                continue
            location = config.relative_to(root).as_posix()
            try:
                entries = _literal_config_remappings(config)
                if not isinstance(entries, list):
                    raise ValueError("Expected literal remapping array")
                for value in entries:
                    context, prefix, target = parse_remapping(value)
                    if target and target not in (".", "./"):
                        _relative_unit_name(target)
                    base = "" if folder == root else folder.relative_to(root).as_posix() + "/"
                    resolved = base + target
                    token = (base + context + ":" if base or context else "") + prefix + "=" + resolved
                    contained_remappings(root, (token,))
                    declared.setdefault((base + context, prefix), set()).add(token)
            except (ValueError, UnicodeError) as exc:
                evidence.append(dict(config=location, reason=str(exc)))
    for (context, prefix), values in sorted(declared.items()):
        covered = [row for row in project.issues if row.get("importer", "").startswith(context)
                   and "importer" in row and source_unit_name(row["importer"], row["path"]).startswith(prefix)]
        if not covered:
            continue
        candidates = []
        for value in sorted(values):
            hits = [_local_path(root, source_unit_name(r["importer"], r["path"], (value,)))[0]
                    for r in covered]
            if all(p in files for p in hits):
                candidates.append(value)
        evidence.append(dict(origin="configuration", context=context, prefix=prefix,
                             declared=sorted(values), candidates=candidates))
        if len(candidates) == 1:
            proposed.append(candidates[0])
    unresolved = {row["package"] for row in project.issues if row.get("category") == "unresolved_package_import"}
    for name in sorted(unresolved):
        prefix = name + "/"
        relevant = [r for r in project.imports if r["path"].startswith(prefix)]
        roots = None
        for row in relevant:
            tail = row["path"][len(prefix):]
            suffix = tuple(tail.split("/"))
            candidates = set()
            if suffix and all(s not in ("", ".", "..") for s in suffix):
                for path in index.names.get(suffix[-1], ()):
                    if row["resolved"] and path != Path(row["target_path"]):
                        continue
                    parts = path.relative_to(root).parts
                    if tuple(parts[-len(suffix):]) == suffix:
                        candidates.add("/".join(parts[:-len(suffix)]))
            roots = candidates if roots is None else roots & candidates
        roots = sorted(roots or ())
        evidence.append(dict(origin="project_files", prefix=prefix, candidates=roots,
                             imports=sorted({r["path"] for r in relevant})))
        covered_by_config = all(not r.get("category") or any(
            source_unit_name(r["importer"], r["path"], (m,)) != r["path"] for m in proposed)
            for r in relevant)
        if len(roots) == 1 and not covered_by_config:
            proposed.append(prefix + "=" + (roots[0] + "/" if roots[0] else ""))
    return tuple(v for v in dict.fromkeys(proposed) if v not in project.remappings), evidence
