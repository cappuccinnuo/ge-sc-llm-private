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

    Environment retries use --via-ir or --evm-version. D24 additionally
    permits optimizer flags supplied by the source wrapper. Keep argument
    tokens intact for both solc and Slither.
    """
    if not isinstance(settings, (tuple, list)) or not all(isinstance(s, str) for s in settings):
        raise ValueError("settings must be an ordered sequence of string tokens")
    settings = tuple(settings)
    seen, index = set(), 0
    while index < len(settings):
        option = settings[index]
        if option not in ("--evm-version", "--via-ir", "--optimize", "--optimize-runs") or option in seen:
            raise ValueError("Unsupported or repeated compiler setting: " + option)
        seen.add(option)
        index += 1
        if option == "--evm-version":
            if index == len(settings) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", settings[index]):
                raise ValueError("--evm-version requires one name token")
            index += 1
        elif option == "--optimize-runs":
            if index == len(settings) or not re.fullmatch(r"[0-9]+", settings[index]):
                raise ValueError("--optimize-runs requires an unsigned decimal uint32")
            digits = settings[index].lstrip("0") or "0"
            if len(digits) > 10 or (len(digits) == 10 and digits > "4294967295"):
                raise ValueError("--optimize-runs exceeds uint32")
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


# CP3 diagnostics: CLI stderr is authoritative. Standard JSON types/error codes
# are supplementary probe evidence, never the compilation route (PROMPTS 4.5).
_LEXICAL = re.compile(
    rb'(?P<comment>//[^\r\n]*|/\*[\s\S]*?(?:\*/|$))'
    rb'|(?P<string>"(?:\\[\s\S]|[^"\\])*"|\'(?:\\[\s\S]|[^\'\\])*\')'
    rb'|(?P<word>[A-Za-z_$][A-Za-z0-9_$]*)|(?P<symbol>[^\s])')
_DIAGNOSTIC = re.compile(
    r'^(?:(?P<file>.*):(?P<line>\d+):(?P<column>\d+):\s*)?'
    r'(?P<kind>[A-Za-z]+Error|Error|Warning|Compiler error|Internal compiler error|'
    r'Unimplemented feature|Fatal error|Exception)'
    r'(?:\s+\([^)]*\))?:\s*(?P<message>.*)$')
_LOCATION = re.compile(r'^\s*-->[ \t]+(?P<file>.*?):(?P<line>\d+):(?P<column>\d+):?\s*$')


def lexical_tokens(source):
    """Yield byte-positioned words, literals and punctuation, excluding comments.

    This is lexical evidence only, not a Solidity parser or version evaluator.
    Byte offsets survive invalid UTF-8 and comments containing fake directives.
    """
    for match in _LEXICAL.finditer(source):
        if match.lastgroup != "comment":
            yield match.start(), match.end(), match.lastgroup, match.group()


def diagnostic_template(message):
    """Normalize variable values for statistics while preserving token wording."""
    text = re.sub(r'"[^"\n]*"', '"<value>"', message)
    text = re.sub(r'\b0x[0-9a-fA-F]+\b', '<hex>', text)
    text = re.sub(r'\b\d+\.\d+\.\d+(?:\+[A-Za-z0-9.+-]+)?', '<version>', text)
    text = re.sub(r'\b(int_const|rational_const) [0-9]+', r'\1 <number>', text)
    return " ".join(text.split())


def parse_diagnostics(stderr):
    """Parse old/new CLI diagnostics, retaining absent locations and all errors.

    Error types are not invented: Error remains Error. Source excerpts and
    secondary Note locations cannot replace the primary diagnostic location.
    """
    records, current, primary_location = [], None, False
    for line in stderr.splitlines():
        found = _DIAGNOSTIC.match(line)
        if found:
            data = found.groupdict()
            current = {"kind": data["kind"], "message": data["message"],
                       "filename": data["file"],
                       "line": int(data["line"]) if data["line"] else None,
                       "column": int(data["column"]) if data["column"] else None,
                       "location_format": "legacy" if data["line"] else "absent",
                       "error_code": None}
            records.append(current)
            primary_location = False
        elif current is not None:
            location = _LOCATION.match(line)
            if location and not primary_location and current["line"] is None:
                data = location.groupdict()
                current.update(filename=data["file"], line=int(data["line"]),
                               column=int(data["column"]), location_format="modern")
                primary_location = True
            elif line.lstrip().startswith("Note:"):
                primary_location = True
            elif line.startswith("std::exception::what:"):
                current["message"] += " " + line
    if not records and stderr.strip():
        records.append({"kind": "unknown", "message": error_first_line(stderr),
                        "filename": None, "line": None, "column": None,
                        "location_format": "absent", "error_code": None})
    for row in records:
        row["template"] = diagnostic_template(row["message"] or "")
    return records


def _diagnostic_offset(diagnostic, source):
    lines = source.splitlines(keepends=True)
    row, column = diagnostic.get("line"), diagnostic.get("column")
    if row is None or column is None or not 1 <= row <= len(lines):
        return None
    return sum(len(line) for line in lines[:row - 1]) + column - 1


def _in_base_list(diagnostic, source):
    offset = _diagnostic_offset(diagnostic, source)
    if offset is None:
        return False
    header, start, depth = [], None, 0
    for lo, _, kind, token in lexical_tokens(source):
        if depth == 0 and token in (b"contract", b"interface"):
            start, header = lo, []
        if start is not None:
            header.append(token)
        if token == b"{":
            if start is not None and start <= offset < lo:
                return b"is" in header
            start = None
            depth += 1
        elif token == b"}":
            depth = max(0, depth - 1)
    return False


def _unbalanced(source):
    stack = []
    pairs = {b"}": b"{", b")": b"(", b"]": b"["}
    for _, _, kind, token in lexical_tokens(source):
        if kind == "string":
            continue
        if token in pairs.values():
            stack.append(token)
        elif token in pairs:
            if not stack or stack.pop() != pairs[token]:
                return True
    return bool(stack)


def _import_at(diagnostic, source):
    offset = _diagnostic_offset(diagnostic, source)
    start, literals = None, []
    for lo, hi, kind, token in lexical_tokens(source):
        if token == b"import":
            start, literals = lo, []
        elif start is not None and kind == "string":
            literals.append(token[1:-1].decode("latin1"))
        elif start is not None and token == b";":
            if offset is not None and start <= offset < hi and len(literals) == 1:
                return literals[0]
            start = None
    return None


# Standard-JSON types for untyped CLI messages (see tests/fixtures/cp4_1).
# Quoted identifiers and compiler versions have already been normalized.
_CLI_DIAGNOSTIC_TYPES = {
    'Declaration "<value>" not found in "<value>" (referenced as "<value>").': 'DeclarationError',
    'Identifier "<value>" not found.': 'DeclarationError',
    'More than one constructor defined.': 'DeclarationError',
    'Multiple matching identifiers. Resolving overloaded identifiers is not supported.': 'DeclarationError',
    'Non-abstract contracts cannot have internal constructors. Remove the "<value>" keyword and make the contract abstract to fix this.': 'DeclarationError',
    'Builtin function "<value>" must be called.': 'ParserError',
    'Function, variable, struct or modifier declaration expected.': 'ParserError',
    'Only state variables or file-level variables can have a docstring.': 'ParserError',
    'The state mutability modifier "<value>" was removed in version <version>. Use "<value>" or "<value>" instead.': 'ParserError',
    'True and false are not valid literals.': 'ParserError',
    'Defining empty structs is disallowed.': 'SyntaxError',
    'Functions are not allowed to have the same name as the contract. If you intend this to be a constructor, use "<value>" to define it.': 'SyntaxError',
    'Unknown pragma "<value>"': 'SyntaxError',
    '"<value>" and "<value>" are only available for objects of type "<value>", not "<value>".': 'TypeError',
    '"<value>" has been deprecated. Use "<value>" instead.': 'TypeError',
    'Cannot call function via contract type name.': 'TypeError',
    'Contract "<value>" should be marked as abstract.': 'TypeError',
    'Contract with internal constructor cannot be created directly.': 'TypeError',
    'Definition of base has to precede definition of derived contract': 'TypeError',
    'Dynamically-sized keys for public mappings are not supported.': 'TypeError',
    'Event invocations have to be prefixed by "<value>".': 'TypeError',
    'Explicit type conversion not allowed from "<value>" to "<value>".': 'TypeError',
    'Function overload clash during conversion to external types for arguments.': 'TypeError',
    'Functions in interfaces must be declared external.': 'TypeError',
    'Immutable variables cannot be read during contract creation time, which means they cannot be read in the constructor or any function or modifier called from it.': 'TypeError',
    'Interfaces cannot inherit.': 'TypeError',
    'Internal type is not allowed for public or external functions.': 'TypeError',
    'Invalid array length, expected integer literal or constant expression.': 'TypeError',
    'Library name expected.': 'TypeError',
    'Location has to be calldata for external functions (remove the "<value>" or "<value>" keyword).': 'TypeError',
    'Name has to refer to a struct, enum or contract.': 'TypeError',
    'No matching declaration found after argument-dependent lookup.': 'TypeError',
    'Overriding function changes state mutability from "<value>" to "<value>".': 'TypeError',
    'Overriding function return types differ.': 'TypeError',
    'Overriding function visibility differs.': 'TypeError',
    'Overriding public state variable return types differ.': 'TypeError',
    'Referenced declaration is neither modifier nor base class.': 'TypeError',
    'Storage location can only be given for array or struct types.': 'TypeError',
    'Structs cannot be defined in interfaces.': 'TypeError',
    'This type cannot be encoded.': 'TypeError',
    'Using "<value>" is deprecated. Use "<value>" instead.': 'TypeError',
    'Variables cannot be declared in interfaces.': 'TypeError',
}
_CLI_TYPE_FAMILIES = re.compile(
    r'^(?:(?:Built-in (?:binary|unary)|Unary|Binary) operator .+? cannot be applied to types? .+'
    r'|Decoding type struct [\w.$]+(?: [\w]+)* not supported\.'
    r'|Member "<value>" is not available in struct .+ outside of storage\.'
    r'|Member "<value>" not unique after argument-dependent lookup in .+\.'
    r'|The "<value>" instruction is only available for [\w-]+-compatible VMs .+)\Z'
)


def _cli_kind(kind, template):
    """Supply a witnessed type for the generic CLI prefix, preserving explicitly typed errors."""
    if kind != "Error":
        return kind
    if template in _CLI_DIAGNOSTIC_TYPES:
        return _CLI_DIAGNOSTIC_TYPES[template]
    return "TypeError" if _CLI_TYPE_FAMILIES.fullmatch(template) else kind


def classify_diagnostic(diagnostic, source=b""):
    """Classify one actual CLI message using text and its located source bytes.

    Return an explicit category/template. Unmatched errors remain other; a
    structural heuristic only refines a parser diagnostic, never valid source.
    """
    message, kind = diagnostic.get("message") or "", diagnostic.get("kind")
    template = diagnostic_template(message)
    kind = _cli_kind(kind, template)
    low = message.lower()
    exact = {"JSONError": "json_error", "IOError": "io_error",
             "InternalCompilerError": "internal_compiler_error",
             "Exception": "compiler_exception", "FatalError": "fatal_error",
             "DocstringParsingError": "docstring_error"}
    if kind == "Warning":
        category = "warning"
    elif "stack too deep" in low:
        category = "codegen_only"
    elif kind in exact:
        category = exact[kind]
    elif (kind == "Internal compiler error" or "internalcompilererror" in low or
          low.startswith("internal compiler error during compilation:")):
        category = "internal_compiler_error"
    elif kind == "Fatal error":
        category = "fatal_error"
    elif (kind in ("Unimplemented feature", "UnimplementedFeatureError") or "not yet supported" in low or
          low.startswith("copying of type struct ") and
          "is not supported in legacy (only supported by the ir pipeline)" in low):
        category = "unimplemented_feature"
    elif re.search(r'\bsource ".+?" not found', message, re.I):
        name = _import_at(diagnostic, source)
        category = ("missing_relative_file" if name.startswith(("./", "../")) else
                    "io_error" if name.startswith(("/", "file:", "http:", "https:")) else
                    "unresolved_package_import") if name else "io_error"
    elif re.search(r"file.*(?:not found|outside of allowed|permission)|cannot (?:open|read)", low):
        category = "io_error"
    elif low.startswith("source file requires different compiler version"):
        category = "version_mismatch"
    elif (re.search(r"only supported in (?:abi coder v2|abiencoderv2|the new experimental abi encoder)\b", low)
          or re.search(r"does not use (?:abi coder v2|abiencoderv2) but wants to inherit", low)):
        category = "abi_coder_required"
    elif low.rstrip(".") in ("free functions cannot be payable", "free functions cannot have visibility",
                              "free functions must be implemented", "only constant variables are allowed at file level"):
        category = "file_level_member"
    elif "multiple spdx" in low or "already been selected" in low or "duplicate pragma" in low:
        category = "multiple_license_or_pragma"
    elif "already declared" in low or "defined twice" in low or "duplicate definition" in low:
        category = "duplicate_definition"
    elif "identifier not found or not unique" in low and _in_base_list(diagnostic, source):
        category = "missing_base_contract"
    elif "undeclared identifier" in low or "identifier not found" in low or "not found or not unique" in low:
        category = "undeclared_identifier"
    elif "documented parameter" in low or "documentation tag" in low or kind == "DocstringParsingError":
        category = "docstring_error"
    elif re.search(r"invalid (?:utf|character|escape)|unicode|invalid token", low):
        category = "encoding"
    elif re.search(r"^(?:expected |unexpected )|end of source", low) or kind == "ParserError":
        delimiter = "end of source" in low or "expected token semicolon" in low or "expected ';'" in low
        category = "unbalanced_structure" if delimiter or _unbalanced(source) else "parser_error_other"
    elif "has to be in a" in low or "visibility" in low and "specified" in low or kind == "SyntaxError":
        category = "syntax_error"
    elif re.search(r"not (?:implicitly )?convertible|wrong argument count|invalid type|"
                   r"member .+ not found|data location|type .* is not|operator .* not compatible|"
                   r"invalid implicit conversion|different number of components|"
                   r"trying to override|override|virtual", low) or kind == "TypeError":
        category = "type_error_other"
    elif kind == "DeclarationError":
        category = "declaration_error"
    else:
        category = "other"
    return dict(diagnostic, category=category,
                failure=category != "warning", template=template)


def pragma_evidence(source):
    """Locate original top-level Solidity expression bytes for rejected plans.

    Never evaluate or widen intervals here. Original spelling and hex bytes are
    retained because a missing semicolon can swallow the following directive.
    """
    tokens = list(lexical_tokens(source))
    depth, rows = 0, []
    for i, (start, end, kind, token) in enumerate(tokens):
        if token == b"{":
            depth += 1
        elif token == b"}":
            depth = max(0, depth - 1)
        elif depth == 0 and token == b"pragma" and i + 1 < len(tokens) and tokens[i + 1][3] == b"solidity":
            begin, stop, words, terminated = tokens[i + 1][1], len(source), [], False
            for lo, hi, k, t in tokens[i + 2:]:
                if t in (b";", b"{", b"}"):
                    stop, terminated = lo, t == b";"
                    break
                if k != "string":
                    words.append(t)
            raw = source[begin:stop]
            rows.append({"start": begin, "end": stop, "expression": raw.decode("latin1"),
                         "expression_hex": raw.hex(), "tokens": b" ".join(words).decode("latin1"),
                         "terminated": terminated})
    return rows


def classify_constraints(message, sources):
    """Subdivide unchanged Unsupported outcomes, retaining expression evidence."""
    evidence = [dict(row, source_index=i) for i, raw in enumerate(sources)
                for row in pragma_evidence(raw)]
    if "unterminated pragma" in message:
        category, subtype = "unterminated_pragma", "source_syntax"
    elif "empty pragma intersection" in message:
        category = "closure_version_conflict"
        subtype = "compilation_unit" if "across compilation unit" in message else "single_file"
    elif any(re.search(r"\b(import|pragma|contract|interface|library|abstract)\b", r["tokens"]) for r in evidence):
        category, subtype = "pragma_missing_semicolon_candidate", "source_syntax"
    elif any("| |" in r["tokens"] for r in evidence):
        category, subtype = "unsupported_disjunction", "tool_limitation"
    else:
        category, subtype = "unsupported_expression", "unparsed_constraint"
    return {"category": category, "subtype": subtype, "error_first_line": message,
            "pragma_evidence": evidence}


def classify_slither(analysis, sources=()):
    """Separate tool failures from source errors without rewriting legal code."""
    exception = analysis.get("exception_type")
    if analysis.get("d3_a") and analysis.get("d3_b") and analysis.get("d3_c") is False:
        # D25: the graph exists but Slither dropped IR; a source rewrite cannot be justified.
        return {"category": "slither_incomplete", "subtype": "slither_partial_ir",
                "error_template": diagnostic_template(analysis.get("error_first_line") or ""),
                "repair_route": "tool_limitation", "candidate_source_indexes": [],
                "equivalence_must_be_verified_before_rewrite": False,
                "partial_ir": analysis.get("partial_ir")}
    candidates = []
    if exception == "AssertionError" and analysis.get("version") in ("0.4.24", "0.4.25", "0.4.26"):
        for i, raw in enumerate(sources):
            code = b" ".join(t for _, _, kind, t in lexical_tokens(raw) if kind != "string")
            if re.search(rb"\( bool [A-Za-z_$][A-Za-z0-9_$]* , \) = .+?\. call \. value \(", code):
                candidates.append(i)
    return {"category": "slither_incomplete", "subtype": exception or "d3_incomplete",
            "error_template": diagnostic_template(analysis.get("error_first_line") or ""),
            "repair_route": "tuple_call_equivalence_candidate" if candidates else "tool_limitation",
            "candidate_source_indexes": candidates,
            "equivalence_must_be_verified_before_rewrite": bool(candidates)}
