"""PROMPTS 3.3/4.3: the single version/settings policy, independent of paths.

CP2.3 copies frozen interval expression semantics, without whole-file parsing. Feature rules cite the official
versioned documents already referenced by PROMPTS/CP0; no online lookup occurs.
CP0 adapters retain its frozen no-pragma inventory window only for that survey.
"""
import hashlib
import re
from collections import defaultdict

from compile_repair.core.model import EnvironmentPlan, Patch
from compile_repair.toolchain.solc import version_tuple
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_f.versioning import recorded_version

FLOOR, CEILING = (0, 4, 12), (0, 9, 0)
# Official v0.5.0: throw and var are disallowed. v0.8.0: unchecked blocks
# explicitly restore wrapping arithmetic. These are syntax constraints only;
# absence of a token is NOT evidence for a version or arithmetic semantics.
FEATURE_RULES = (
    {"name": "throw_removed", "pattern": r"\bthrow\s*;", "lo": FLOOR, "hi": (0, 5, 0),
     "source": "https://docs.soliditylang.org/en/v0.5.0/050-breaking-changes.html#syntax",
     "entry": "v0.5.0: throw is disallowed; use revert/require/assert"},
    {"name": "var_removed", "pattern": r"\bvar\s+(?:[A-Za-z_$]|\()", "lo": FLOOR, "hi": (0, 5, 0),
     "source": "https://docs.soliditylang.org/en/v0.5.0/050-breaking-changes.html#syntax",
     "entry": "v0.5.0: var keyword is disallowed"},
    {"name": "unchecked_introduced", "pattern": r"\bunchecked\s*\{", "lo": (0, 8, 0), "hi": CEILING,
     "source": "https://docs.soliditylang.org/en/v0.8.0/080-breaking-changes.html#silent-changes-of-the-semantics",
     "entry": "v0.8.0: overflow/underflow reverts; unchecked blocks use wrapping arithmetic"},
)
SETTINGS_TABLE = (
    {"name": "cancun_builtins", "lo": (0, 8, 24), "hi": (0, 8, 25),
     "error_type": "DeclarationError or TypeError (combined-json prints Error)",
     "message": 'Function "{tload,tstore,mcopy,blobhash,blobbasefee}" not found; '
                'Undeclared identifier at blobhash; Member "blobbasefee" not found in block',
     "settings": ("--evm-version", "cancun"),
     "source": "https://www.soliditylang.org/blog/2024/03/14/solidity-0.8.25-release-announcement/",
     "entry": "0.8.25 switches the default EVM version to Cancun; 0.8.24 requires explicit Cancun"},
    {"name": "require_custom_error_via_ir", "lo": (0, 8, 26), "hi": (0, 8, 27),
     "error_type": "UnimplementedFeatureError; read std::exception::what",
     "message": "Require with a custom error is only available using the via-ir pipeline.",
     "settings": ("--via-ir",),
     "source": "https://www.soliditylang.org/blog/2024/05/21/solidity-0.8.26-release-announcement/",
     "entry": "0.8.26 require(bool, Error) only in IR pipeline; 0.8.27 adds legacy pipeline support"},
)
_MASK = re.compile(rb'//[^\r\n]*|/\*[\s\S]*?(?:\*/|$)|"(?:\\[\s\S]|[^"\\])*"|\x27(?:\\[\s\S]|[^\x27\\])*\x27')


def code_only(source):
    """Mask comments/string literals with equal byte spaces, preserving newlines."""
    return _MASK.sub(lambda m: re.sub(rb'[^\r\n]', b' ', m.group()), source)


def _pragma_spans(source):
    """Return top-level Solidity directive byte spans after lexical masking.

    Braces in comments and strings do not affect depth. A recognized top-level
    directive without a terminating semicolon before a brace/end is unsupported;
    unrelated Solidity syntax is left to the compiler.
    """
    code = code_only(source)
    tokens = rb"[{}]|(?<![A-Za-z0-9_$])pragma\s+solidity(?![A-Za-z0-9_$])"
    depth, spans = 0, []
    for match in re.finditer(tokens, code):
        token = match.group()
        if token == b"{":
            depth += 1
        elif token == b"}":
            depth = max(0, depth - 1)
        elif depth == 0:
            end = re.search(rb"[;{}]", code[match.end():])
            if end is None or end.group() != b";":
                raise Unsupported("F: unterminated pragma directive")
            spans.append((match.start(), match.end() + end.end()))
    return tuple(spans)


def _expression_interval(expressions):
    """Evaluate constraints with frozen stage_f interval() semantics.

    Copied evaluation only from scripts/DFG/state/stage_f/versioning.py:10-23,
    SHA256 130251d6a9e46ec176ba183a0a66fa5a30210b43c1ab8faa2bfcf5a676d2ed18.
    Directive location is independent; frozen parsing is used only in tests.
    """
    if not expressions:
        return None
    lo, hi = (0, 0, 0), (999, 0, 0)
    pattern = r"(\^|~|>=|<=|>|<|=)?\s*(\d+)\.(\d+)\.(\d+)"
    for expr in expressions:
        if "||" in expr or not re.search(pattern, expr) or re.sub(pattern, "", expr).strip():
            raise Unsupported("F: unsupported pragma expression")
        for match in re.finditer(pattern, expr):
            op = match.group(1) or "="
            version = tuple(int(match.group(i)) for i in (2, 3, 4))
            patch = (version[0], version[1], version[2] + 1)
            if op in ("=", "^", "~"):
                upper = (patch if op == "=" else (version[0], version[1] + 1, 0) if op == "~"
                         else (version[0] + 1, 0, 0) if version[0]
                         else (0, version[1] + 1, 0) if version[1] else patch)
                lo, hi = max(lo, version), min(hi, upper)
            elif op in (">", ">="):
                lo = max(lo, patch if op == ">" else version)
            else:
                hi = min(hi, patch if op == "<=" else version)
    if lo >= hi:
        raise Unsupported("F: empty pragma intersection")
    return lo, hi


def pragma_interval(sources):
    """Intersect byte sources' top-level pragmas; raise Unsupported if invalid.

    CP2.4 masks comments inside expressions before frozen constraint evaluation.
    Latin-1 preserves byte positions without requiring the source to be UTF-8.
    """
    found = []
    for raw in sources:
        code = code_only(raw)
        expressions = [re.sub(r"^pragma\s+solidity\s*|;\s*$", "",
                             code[start:end].decode("latin1")).strip()
                       for start, end in _pragma_spans(raw)]
        value = _expression_interval(expressions)
        if value is not None:
            found.append(value)
    if not found:
        return None
    lo, hi = max(x[0] for x in found), min(x[1] for x in found)
    if lo >= hi:
        raise Unsupported("F: empty pragma intersection across compilation unit")
    return lo, hi

def infer_interval(sources):
    """Infer only documented positive syntax evidence; return bounds and rules."""
    code = b"\n".join(code_only(raw) for raw in sources).decode("latin1")
    matched = tuple(dict(rule) for rule in FEATURE_RULES if re.search(rule["pattern"], code))
    lo = max([FLOOR] + [r["lo"] for r in matched])
    hi = min([CEILING] + [r["hi"] for r in matched])
    if lo >= hi:
        raise Unsupported("Conflicting documented version features")
    return (lo, hi), matched


def candidate_versions(interval, versions, no_pragma_interval=None):
    """Partition trusted supported versions into the first and later series.

    This only lists candidates. The caller must exhaust a series before moving
    to the next. CP0 supplies its original no-pragma inventory window explicitly.
    """
    lo, hi = interval or no_pragma_interval or (FLOOR, CEILING)
    lo, hi = tuple(lo), tuple(hi)
    primary, fallback = [], []
    for value in sorted(set(versions), key=version_tuple):
        version = version_tuple(value)
        if FLOOR <= version < CEILING and lo <= version < hi:
            (primary if version[:2] == lo[:2] else fallback).append(value)
    return {"primary": primary, "later_series_only_after_primary_failure": fallback}


def candidate_groups(candidates, order="ascending"):
    """Keep series in ascending order, and order patches within each series."""
    if order not in ("ascending", "descending"):
        raise ValueError("order must be ascending or descending")
    later = defaultdict(list)
    for version in candidates["later_series_only_after_primary_failure"]:
        later[version_tuple(version)[:2]].append(version)
    groups = [candidates["primary"]] + [later[k] for k in sorted(later)]
    return tuple(tuple(sorted(g, key=version_tuple, reverse=order == "descending")) for g in groups)


def priority_version(interval, available, known=None, regression=None):
    """Return eligible known version, else MANDO's explicit no-pragma priority."""
    if known is not None:
        v = version_tuple(known)
        if known in available and FLOOR <= v < CEILING and (
                interval is None or tuple(interval[0]) <= v < tuple(interval[1])):
            return known
    if interval is None and regression == "mando" and "0.4.25" in available:
        return "0.4.25"
    return None


def make_plan(sources, versions, known=None, regression=None, order="ascending"):
    """Plan version attempts without compiling; accept bytes, never path clues.

    Override is available ONLY when no supported installed version satisfies a
    declared interval, and only within its lower-bound series, nearest first.
    """
    if regression not in (None, "mando"):
        raise ValueError("Unsupported regression configuration")
    declared = pragma_interval(sources)
    inferred, evidence = infer_interval(sources) if declared is None else (declared, ())
    flags = []
    origin = "pragma_intersection" if declared else "no_pragma_inferred" if evidence else "no_pragma_guess"
    if declared is None:
        flags.append(origin)
    if known is not None:
        v = version_tuple(known)
        if v < FLOOR:
            flags.append("known_version_below_slither_floor")
        elif declared and not declared[0] <= v < declared[1]:
            flags.append("known_version_outside_interval")
        elif known not in versions:
            flags.append("known_version_unavailable")
    candidate = candidate_versions(inferred, versions)
    groups = candidate_groups(candidate, order)
    priority = priority_version(declared, versions, known, regression)
    override = declared is not None and not any(groups)
    if override:
        lo = declared[0]
        nearest = [v for v in versions if FLOOR <= version_tuple(v) < CEILING and version_tuple(v)[:2] == lo[:2]]
        nearest.sort(key=lambda v: (abs(version_tuple(v)[2] - lo[2]), version_tuple(v)))
        groups = (tuple(nearest),)
        priority = None
    return EnvironmentPlan(declared, inferred, origin, groups, priority, tuple(flags), evidence, override)


def ordered_candidates(plan):
    """Yield each version once; only consumers continuing after failure advance."""
    seen = set()
    if plan.priority is not None:
        seen.add(plan.priority)
        yield plan.priority
    for group in plan.groups:
        for version in group:
            if version not in seen:
                seen.add(version)
                yield version


def select_version(plan, probe):
    """Return the first successful D3 version; injected probe supports frozen replay."""
    return next((v for v in ordered_candidates(plan) if probe(v)["d3"]), None)


def d3_endpoints(versions, probe):
    """Find within-series endpoints through the same ordered D3 selector."""
    plans = [EnvironmentPlan(None, (FLOOR, CEILING), "endpoint", (tuple(sorted(
        versions, key=version_tuple, reverse=reverse)),), None, ()) for reverse in (False, True)]
    low = select_version(plans[0], probe)
    return low, select_version(plans[1], probe) if low is not None else None


def pragma_patches(source):
    """Replace only Solidity pragma directive bytes with equal-length spaces.

    Preserve CR/LF and same-line code outside directives. Reverse positions keep
    current-copy coordinates valid. Caller must first establish override eligibility.
    """
    patches = []
    for start, end in _pragma_spans(source):
        raw = source[start:end]
        patches.append(Patch(start, end, raw, re.sub(rb"[^\r\n]", b" ", raw),
                             "pragma_override", 1, "No supported trusted compiler in declared interval"))
    return tuple(reversed(patches))


def settings_retry(compilation, source):
    """Return a documented matching setting row, or None; at most one retry.

    For unnamed identifier diagnostics, require the compiler's location to point
    to blobhash in code, not a filename, comment, warning, or unrelated occurrence.
    """
    if compilation.returncode == 0 or compilation.timed_out or compilation.settings:
        return None
    v, stderr = version_tuple(compilation.compiler.version), compilation.stderr
    if v == (0, 8, 24):
        named = re.search(r'^(?:Error|DeclarationError): Function "(?:tload|tstore|mcopy|blobhash|blobbasefee)" not found\.', stderr, re.M)
        member = re.search(r'^(?:Error|TypeError): Member "blobbasefee" not found or not visible after argument-dependent lookup in block\.', stderr, re.M)
        location = re.search(r'^(?:Error|DeclarationError): Undeclared identifier\.[^\n]*\n\s*--> [^\n]*:(\d+):(\d+):', stderr, re.M)
        token = b""
        if location:
            lines = code_only(source).splitlines()
            row, column = int(location.group(1)) - 1, int(location.group(2)) - 1
            if 0 <= row < len(lines) and 0 <= column < len(lines[row]):
                found = re.match(rb"[A-Za-z_$][A-Za-z0-9_$]*", lines[row][column:])
                token = found.group() if found else b""
        if named or member or token == b"blobhash":
            return dict(SETTINGS_TABLE[0], trigger_error=compilation.error_first_line)
    if v == (0, 8, 26) and ("UnimplementedFeatureError" in stderr or "Unimplemented feature:" in stderr) and re.search(
            r'^std::exception::what: Require with a custom error is only available using the via-ir pipeline\.$', stderr, re.M):
        return dict(SETTINGS_TABLE[1], trigger_error=compilation.error_first_line)
    return None


def mando_known_version(source, frozen_rows):
    """Validate approved SmartBugs metadata matched by SHA256, never by filename.

    Rows come from hash-checked cp0_v2. recorded_version rechecks the referenced
    original source, CSV bytes and unique row. Conflicting known versions raise.
    """
    digest = hashlib.sha256(source).hexdigest()
    refs = [r["metadata"] for r in frozen_rows if r["sha256"] == digest and r.get("metadata")]
    versions = {".".join(map(str, recorded_version(source.decode("utf8"), ref))) for ref in refs}
    if len(versions) > 1:
        raise ValueError("Conflicting validated metadata for identical source bytes")
    return next(iter(versions)) if versions else None, refs
