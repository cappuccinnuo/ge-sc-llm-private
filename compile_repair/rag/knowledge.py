"""K1-K3 construction and storage (PROMPTS 3.4, CP7).

K1  Solidity documentation: reStructuredText sections of `docs/` at each compiler tag,
    deduplicated across tags; every section keeps the versions whose docs contain it.
K2  library index: one entry per Solidity file of the sealed CP5 offline index, keyed by
    the declared symbols and the published import path.
K3  repair memory: repairs that passed every check (the pipeline's success records),
    keyed by the templates of the errors they removed. Entries carry their project group,
    so retrieval can leave the evaluated project out; they carry no dataset labels.

Messages are abstracted by `message_template`: a quoted value stays only when it is a
documented Solidity term (taken from the documentation itself), otherwise it becomes
<id>, so user identifiers never become keys. The store is a JSON-lines body sealed by
its SHA-256; loading verifies the seal.
"""
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from compile_repair.toolchain.solc import classify_diagnostic, parse_diagnostics, version_tuple

SCHEMA = "compile-repair-knowledge-v1"
SOURCES = ("K1", "K2", "K3")


@dataclass(frozen=True)
class Entry:
    source: str
    entry_id: str
    title: str
    text: str
    keys: tuple = ()
    versions: tuple = ()          # K1: versions whose docs contain the section; () = any
    group: str = None             # K3: project group of the repaired unit
    payload: dict = field(default_factory=dict, hash=False, compare=False)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


# ---- message templates -------------------------------------------------------------------

_TYPE_NAME = re.compile(r"(?:u?int|u?fixed|bytes)[0-9x]*|address(?: payable)?|bool|string|byte|mapping"
                        r"|(?:u?int|bytes)[0-9]*\[\]")
_FIRST_LINE = re.compile(r"^(?:.*?:\d+:\d+:\s*)?(?P<kind>(?:[A-Z][A-Za-z]*)?(?:Error|Exception)|Compiler error|F|Warning)"
                         r":\s*(?P<message>.*)$")
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")


def split_first_line(line):
    """(kind, message) of a recorded first error line; a bare pipeline category has kind None."""
    found = _FIRST_LINE.match(line.strip())
    return (found["kind"], found["message"]) if found else (None, line.strip())


def message_template(message, vocabulary):
    """Abstract user identifiers and values; keep documented terms and type names."""
    def quoted(match):
        inner = match.group(1)
        head = _IDENT.match(inner)
        keep = inner in vocabulary or _TYPE_NAME.fullmatch(inner) or (head and head.group() in vocabulary
                                                                     and head.end() < len(inner))
        return '"' + inner + '"' if keep else '"<id>"'
    text = re.sub(r'"([^"\n]*)"', quoted, message)
    text = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", text)
    text = re.sub(r"\b\d+\.\d+\.\d+(?:\+[A-Za-z0-9.+-]+)?", "<version>", text)
    text = re.sub(r"\b(int_const|rational_const) -?[0-9]+(?:/[0-9]+)?", r"\1 <number>", text)
    return " ".join(text.split())


def template_terms(template):
    """Documented terms kept in a template (the K1 exact keys of a query)."""
    terms = set()
    for inner in re.findall(r'"([^"\n]*)"', template):
        if inner != "<id>":
            head = _IDENT.match(inner)
            terms.add(head.group() if head else inner)
    return sorted(terms)


# ---- K1: documentation -------------------------------------------------------------------

_UNDERLINE = re.compile(r"^([=\-`:'\"~^_*+#<>])\1{2,}\s*$")
_LITERAL = re.compile(r"``([^`\n]+)``")
# Files whose literals define the vocabulary of documented terms: global names, built-ins
# and every deprecated or renamed spelling. Files with code examples (types, contracts)
# are excluded because their literals include example identifiers; type names are kept
# by _TYPE_NAME instead.
TERM_FILES = re.compile(r"(?:^|/)(?:cheatsheet|units-and-global-variables|\d{3}-breaking-changes)\.rst$")


def rst_sections(text):
    """Leaf sections of one reStructuredText file: (title chain, body)."""
    lines = text.splitlines()
    levels, chain, sections, body, i = [], [], [], [], 0
    def close():
        content = "\n".join(body).strip()
        if chain and content:
            sections.append((tuple(chain), content))
    while i < len(lines):
        line = lines[i]
        overline = _UNDERLINE.match(line) and i + 2 < len(lines) and _UNDERLINE.match(lines[i + 2]) \
            and lines[i + 2].strip() == line.strip() and lines[i + 1].strip()
        if overline or (line.strip() and i + 1 < len(lines) and _UNDERLINE.match(lines[i + 1])
                        and len(lines[i + 1].rstrip()) >= len(line.rstrip()) and not _UNDERLINE.match(line)):
            title = (lines[i + 1] if overline else line).strip()
            style = ("over" if overline else "") + (lines[i + 2] if overline else lines[i + 1]).strip()[0]
            close()
            body = []
            if style not in levels:
                levels.append(style)
            depth = levels.index(style)
            chain = chain[:depth] + [title]
            i += 3 if overline else 2
            continue
        body.append(line)
        i += 1
    close()
    return sections


def _plain(text):
    # Example boilerplate (the version pragma and SPDX line that open almost every code
    # example) would make "pragma" match most sections; directives are dropped too.
    text = re.sub(r"^\s+(?:pragma solidity [^;\n]*;|// SPDX-License-Identifier:.*)$", " ", text, flags=re.M)
    text = re.sub(r"^\.\. [\w:-]+::.*$", " ", text, flags=re.M)
    text = re.sub(r":[\w:]+:`([^`<]*)(?:<[^>]*>)?`", r"\1", text)
    return re.sub(r"[`*]", "", text)


def documentation_entries(root):
    """K1 entries from `root/<version>/docs/**/*.rst`; identical sections share one entry."""
    merged, order = {}, []
    for version_dir in sorted(Path(root).iterdir(), key=lambda p: version_tuple(p.name)):
        docs = version_dir / "docs"
        for path in sorted(docs.rglob("*.rst")):
            relative = path.relative_to(docs).as_posix()
            raw = path.read_bytes().decode("utf8", "replace")
            for chain, body in rst_sections(raw):
                digest = _sha(json.dumps([relative, chain, body]).encode())[:16]
                if digest not in merged:
                    terms = sorted({_IDENT.match(t).group() for t in _LITERAL.findall(body + " ".join(chain))
                                    if _IDENT.match(t)})
                    merged[digest] = dict(chain=chain, path=relative, body=body, terms=terms, versions=[])
                    order.append(digest)
                merged[digest]["versions"].append(version_dir.name)
    entries = []
    for digest in order:
        item = merged[digest]
        entries.append(Entry("K1", "K1:%s#%s" % (item["path"], digest), " > ".join(item["chain"]),
                             " ".join(item["chain"]) + "\n" + _plain(item["body"]),
                             tuple("term:" + t for t in item["terms"]), tuple(item["versions"]),
                             payload=dict(path=item["path"], titles=list(item["chain"]))))
    return entries


def documented_terms(entries):
    """The vocabulary that `message_template` keeps: literals of the term-defining files."""
    return frozenset(k[5:] for e in entries if e.source == "K1" and TERM_FILES.search(e.payload["path"])
                     for k in e.keys if k.startswith("term:") and len(k) > 6)


# ---- K2: library index -------------------------------------------------------------------

def library_entries(index_root):
    """K2 entries from a sealed CP5 offline index (rules/dependencies.py build_index)."""
    root = Path(index_root)
    seal = json.loads((root / "seal.json").read_bytes())
    raw = (root / "index.json").read_bytes()
    if seal.get("schema") != "compile-repair-dependencies-v1" or _sha(raw) != seal["index_sha256"]:
        raise ValueError("Dependency index seal mismatch")
    entries = []
    for package, releases in sorted(json.loads(raw)["packages"].items()):
        for version, release in sorted(releases.items()):
            for path, info in sorted(release["files"].items()):
                name = package + "/" + path
                interval = (info["pragma"] or {}).get("interval")
                words = " ".join(info["declarations"] + info["function_signatures"] + re.split(r"[/._-]", path))
                entries.append(Entry(
                    "K2", "K2:%s@%s/%s" % (package, version, path), "%s@%s %s" % (package, version, path), words,
                    tuple(["path:" + name] + ["symbol:" + d for d in info["declarations"]]),
                    payload=dict(package=package, release=version, path=path, sha256=info["sha256"],
                                 interval=interval, declarations=info["declarations"],
                                 function_signatures=info["function_signatures"])))
    return entries


# ---- K3: repair memory -------------------------------------------------------------------

def _decoded(value):
    data = bytes.fromhex(value["data"]) if isinstance(value, dict) else (value or b"")
    return data.decode("utf8", "replace")


def removed_errors(environment, vocabulary):
    """Templates of the solc errors at the versions the original unit failed on."""
    rows = []
    for attempt in environment.get("attempts", []):
        compiled = attempt.get("solc")
        if compiled and compiled.get("returncode") not in (0, None) and not compiled.get("timed_out"):
            for d in parse_diagnostics(compiled.get("stderr") or ""):
                if d["kind"] != "Warning":
                    category = classify_diagnostic(d).get("category", "other")
                    rows.append((category, d["kind"] + ": " + message_template(d["message"] or "", vocabulary)))
        analysis = attempt.get("slither")
        if analysis and not analysis.get("d3") and compiled and compiled.get("returncode") == 0:
            rows.append(("slither_incomplete", "Slither: " + message_template(
                (analysis.get("error_first_line") or analysis.get("exception_type") or "D3"), vocabulary)))
    return sorted(set(rows))


def repair_entries(records, vocabulary):
    """K3 entries from (group, environment record, final record) of successful repairs."""
    entries = []
    for group, environment, final in records:
        if final.get("status") != "success" or group is None:
            continue
        changes = [dict(step=c["step"], reason=c.get("reason"), old=_decoded(c.get("old")), new=_decoded(c.get("new")))
                   for p in (final.get("provenance") or {}).values() for c in p.get("changes", [])]
        errors = removed_errors(environment, vocabulary)
        if not changes or not errors:
            continue
        text = "\n".join(t for _, t in errors) + "\n" + "\n".join(
            "%s %s %s" % (c["step"], c["reason"] or "", c["new"]) for c in changes)
        digest = _sha(json.dumps([group, final.get("unit_id"), changes], sort_keys=True).encode())[:16]
        entries.append(Entry("K3", "K3:" + digest, "%s repair (%s)" % (
            "+".join(sorted({c["step"] for c in changes})), final.get("selected_version")), text,
            tuple(sorted({"template:" + t for _, t in errors} | {"category:" + c for c, _ in errors})),
            group=group, payload=dict(unit_id=final.get("unit_id"), version=final.get("selected_version"),
                                      errors=[list(e) for e in errors], changes=changes)))
    return entries


# ---- storage -----------------------------------------------------------------------------

class KnowledgeBase:
    """K1-K3 entries plus the documented-term vocabulary; sealed JSON-lines storage."""

    def __init__(self, entries, vocabulary=None, provenance=None):
        self.entries = list(entries)
        self.vocabulary = frozenset(vocabulary if vocabulary is not None else documented_terms(self.entries))
        self.provenance = dict(provenance or {})
        ids = [e.entry_id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate knowledge entry id")
        self.by_source = {s: [e for e in self.entries if e.source == s] for s in SOURCES}
        self.cache = {}

    def save(self, directory):
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=False)
        body = "".join(json.dumps(asdict(e), sort_keys=True, ensure_ascii=False) + "\n" for e in self.entries)
        (out / "entries.jsonl").write_bytes(body.encode("utf8"))
        seal = dict(schema=SCHEMA, entries_sha256=_sha(body.encode("utf8")), vocabulary=sorted(self.vocabulary),
                    counts={s: len(self.by_source[s]) for s in SOURCES}, provenance=self.provenance)
        (out / "seal.json").write_text(json.dumps(seal, indent=1, sort_keys=True) + "\n", encoding="utf8")
        return seal

    @classmethod
    def load(cls, directory):
        root = Path(directory)
        seal = json.loads((root / "seal.json").read_text(encoding="utf8"))
        raw = (root / "entries.jsonl").read_bytes()
        if seal.get("schema") != SCHEMA or _sha(raw) != seal["entries_sha256"]:
            raise ValueError("Knowledge base seal mismatch")
        entries = []
        for line in raw.decode("utf8").splitlines():
            item = json.loads(line)
            item["keys"], item["versions"] = tuple(item["keys"]), tuple(item["versions"])
            entries.append(Entry(**item))
        return cls(entries, seal["vocabulary"], seal.get("provenance"))
