"""The single repair template and its context (PROMPTS 3.5 items 1-3, D10).

The LLM never sees a real file name or a comment (D10):
- every project file is shown as F1, F2, ... (sorted project-relative names; the entry
  is always F1); import strings that name a project file show its F number, other
  relative imports that resolve to nothing show missing1, missing2, ...; package
  imports stay as written;
- comments are blanked with spaces of the same length, newlines kept, so a line of the
  view and the same line of the file cover the same bytes outside import strings;
- file names and paths in compiler messages are replaced by the F numbers.

Context per error: the lines `window` before and after the error line (merged per
file, each with its 1-based line number) and the declaration lines of identifiers the
message names. Knowledge: the top k hits of K1-K3 (rag/retrieve.py), shortened.
"""
import posixpath
import re
from dataclasses import dataclass

from compile_repair.rag.retrieve import Query, retrieve
from compile_repair.toolchain.solc import lexical_tokens

SYSTEM = ("You repair Solidity source code so that it compiles. You answer only with patches in the "
          "required format. You never add comments and never change code that the errors do not require.")
LANGUAGE_SYSTEM = "You identify the programming language of a source text. Answer with one word."
_COMMENT_OR_STRING = re.compile(rb'(?P<comment>//[^\r\n]*|/\*[\s\S]*?(?:\*/|$))'
                                rb'|(?P<string>"(?:\\[\s\S]|[^"\\])*"|\'(?:\\[\s\S]|[^\'\\])*\')')
_IMPORT_STRING = re.compile(rb'(?<![A-Za-z0-9_$])import\b[^;]*?(?P<q>["\'])(?P<path>[^"\'\r\n]*)(?P=q)')
_DECLARATION = re.compile(rb"^(?:contract|interface|library|struct|event|function|modifier|enum|error|abstract)$")
_QUOTED = re.compile(r'"([A-Za-z_$][\w$]*)"')
TRUNCATE = dict(K1=1200, K2=600, K3=800)

FORMAT = """Patch format. Use one block per change; nothing outside blocks is read.
To rewrite lines (only lines that carry an error):
@@ REPLACE <file> <first line>-<last line>
<line number>| <original line, copied exactly>
...
@@ WITH
<new code lines>
@@ END
To insert new lines before a line (use the last line number + 1 to append):
@@ INSERT <file> BEFORE <line number>
<new code lines>
@@ END
Constraints: copy original lines exactly as shown; rewrite only lines listed under Errors;
insert anything that is missing; do not add comments; keep the code's behaviour."""


def blank_comments(raw):
    """Replace comment bytes by spaces (newlines kept); strings are left alone."""
    return _COMMENT_OR_STRING.sub(
        lambda m: re.sub(rb"[^\r\n]", b" ", m.group()) if m.lastgroup == "comment" else m.group(), raw)


@dataclass
class View:
    """The anonymized, comment-blanked text the model sees, and how to map it back."""
    ids: dict            # real project-relative name -> F number
    names: dict          # F number -> real name
    lines: dict          # F number -> list of view lines (str, without newline)
    real_lines: dict     # F number -> list of (start, end) byte spans of the real lines (newline excluded)
    import_targets: dict  # F number -> {line number: {shown import string: real import string}}

    def file_id(self, name):
        return self.ids[name]


def _resolve(importer, path, names):
    if path.startswith("./") or path.startswith("../"):
        target = posixpath.normpath(posixpath.join(posixpath.dirname(importer), path))
        return target if target in names else None
    return path if path in names else None


def build_view(contents, entry):
    """Anonymize and blank one project's current contents ({real name: bytes})."""
    order = [entry] + sorted(n for n in contents if n != entry)
    ids = {name: "F%d" % (i + 1) for i, name in enumerate(order)}
    lines, spans, imports, missing = {}, {}, {}, {}
    for name in order:
        raw = contents[name]
        masked = blank_comments(raw)
        file_id = ids[name]
        shown, targets = bytearray(), {}
        position = 0
        for found in _IMPORT_STRING.finditer(masked):
            path = found.group("path").decode("utf8", "replace")
            target = _resolve(name, path, ids)
            if target is not None:
                label = ids[target]
            elif path.startswith("."):
                label = missing.setdefault((name, path), "missing%d" % (len(missing) + 1))
            else:
                continue
            line_no = masked.count(b"\n", 0, found.start("path")) + 1
            targets.setdefault(line_no, {})[label] = path
            shown += masked[position:found.start("path")] + label.encode()
            position = found.end("path")
        shown += masked[position:]
        lines[file_id] = bytes(shown).decode("utf8", "replace").split("\n")
        offsets, start = [], 0
        for part in raw.split(b"\n"):
            offsets.append((start, start + len(part)))
            start += len(part) + 1
        spans[file_id], imports[file_id] = offsets, targets
    return View(ids, {v: k for k, v in ids.items()}, lines, spans, imports)


def anonymize_message(message, view):
    """Replace real file names and paths in a compiler message by F numbers."""
    for name in sorted(view.ids, key=len, reverse=True):
        message = message.replace(name, view.ids[name])
        base = posixpath.basename(name)
        if base != name:
            message = re.sub(r"(?<![\w./-])%s(?![\w])" % re.escape(base), view.ids[name], message)
    return re.sub(r"(?:/[^\s:\"']+)+/(F\d+)", r"\1", message)


def _numbered(lines, first, last):
    return "\n".join("%5d| %s" % (n, lines[n - 1]) for n in range(first, last + 1))


def error_lines(diagnostics, view):
    """{F number: sorted error line numbers} (the only lines a patch may rewrite, D7)."""
    found = {}
    for name, rows in diagnostics.items():
        if name in view.ids:
            found.setdefault(view.ids[name], set()).update(r["line"] for r in rows if r.get("line"))
    return {k: sorted(v) for k, v in found.items()}


def _declarations(identifiers, view):
    hits = []
    for file_id, lines in sorted(view.lines.items()):
        raw = "\n".join(lines).encode("utf8")
        tokens = [t for t in lexical_tokens(raw) if t[2] in ("word", "symbol")]
        for (lo, _, _, word), (_, _, _, nxt) in zip(tokens, tokens[1:]):
            if _DECLARATION.match(word) and nxt.decode("utf8", "replace") in identifiers:
                hits.append((file_id, raw.count(b"\n", 0, lo) + 1, nxt.decode()))
    return hits


def context_block(view, diagnostics, window):
    """Numbered code around every error and around the declarations the errors name."""
    wanted = {}
    lines_by_error = error_lines(diagnostics, view)
    for file_id, numbers in lines_by_error.items():
        for n in numbers:
            wanted.setdefault(file_id, set()).update(range(max(1, n - window), min(len(view.lines[file_id]), n + window) + 1))
    names = {m for rows in diagnostics.values() for r in rows for m in _QUOTED.findall(r.get("message") or "")}
    declarations = _declarations(names, view)
    for file_id, n, _ in declarations:
        wanted.setdefault(file_id, set()).update(range(max(1, n - 2), min(len(view.lines[file_id]), n + 2) + 1))
    if not wanted:  # no located error: show the start of the entry file
        wanted["F1"] = set(range(1, min(len(view.lines["F1"]), 2 * window + 1) + 1))
    parts = []
    for file_id in sorted(wanted, key=lambda f: int(f[1:])):
        numbers, run = sorted(wanted[file_id]), []
        for n in numbers:
            if run and n != run[-1] + 1:
                parts.append("=== %s lines %d-%d ===\n%s" % (file_id, run[0], run[-1], _numbered(view.lines[file_id], run[0], run[-1])))
                run = []
            run.append(n)
        parts.append("=== %s lines %d-%d ===\n%s" % (file_id, run[0], run[-1], _numbered(view.lines[file_id], run[0], run[-1])))
    return "\n".join(parts), declarations


def knowledge_query(diagnostics, version, issues, group):
    errors, symbols, categories = [], set(), set()
    for rows in diagnostics.values():
        for r in rows:
            errors.append((r.get("kind"), r.get("message") or ""))
            categories.add(r.get("category") or "other")
            if r.get("category") in ("undeclared_identifier", "missing_base_contract"):
                symbols.update(_QUOTED.findall(r.get("message") or ""))
    paths = tuple(sorted({i["path"] for i in issues or () if i.get("path") and not i["path"].startswith(".")}))
    return Query(errors=tuple(errors), version=version, symbols=tuple(sorted(symbols)), import_paths=paths,
                 categories=tuple(sorted(categories)), group=group)


def knowledge_block(kb, query, k):
    """Top-k K1-K3 hits as short texts, with the ids for the record."""
    if kb is None:
        return "", []
    sources = ("K1", "K2", "K3") if query.group is not None else ("K1", "K2")
    found = retrieve(kb, query, k, sources)
    by_id = {e.entry_id: e for e in kb.entries}
    parts, ids = [], []
    for source in sources:
        for hit in found[source]:
            entry = by_id[hit.entry_id]
            if source == "K3":
                text = "\n".join("errors: " + e[1] for e in entry.payload["errors"][:3]) + "\n" + "\n".join(
                    "%s: %r -> %r" % (c["step"], blank_comments(c["old"].encode()).decode().strip(),
                                      blank_comments(c["new"].encode()).decode().strip())
                    for c in entry.payload["changes"][:4])
            else:
                text = entry.text
            parts.append("[%s] %s\n%s" % (source, entry.title, text[:TRUNCATE[source]].strip()))
            ids.append(hit.entry_id)
    return "\n\n".join(parts), ids


def repair_prompt(view, diagnostics, version, window, knowledge="", history=()):
    """The one repair template (PROMPTS 3.5 item 3)."""
    code, declarations = context_block(view, diagnostics, window)
    errors = []
    for name, rows in sorted(diagnostics.items(), key=lambda item: (item[0] is None, item[0] or "")):
        for r in rows:
            where = "%s:%s" % (view.ids.get(name, "?"), r.get("line") or "?") if name else "?"
            errors.append("%s: %s: %s" % (where, r.get("kind"), anonymize_message(r.get("message") or "", view)))
    files = ", ".join("%s%s (%d lines)" % (f, " entry" if f == "F1" else "", len(view.lines[f]))
                      for f in sorted(view.lines, key=lambda f: int(f[1:])))
    sections = ["Task: make this Solidity compilation unit compile with solc %s." % version, "Files: " + files,
                "Errors:\n" + "\n".join(errors), "Code:\n" + code]
    if declarations:
        sections.append("Declarations named by the errors: " + ", ".join(
            "%s at %s:%d" % (n, f, line) for f, line, n in declarations))
    if knowledge:
        sections.append("Reference knowledge:\n" + knowledge)
    for item in history:
        sections.append("A previous candidate was rejected (%s):\n%s\nResulting errors:\n%s" % (
            item["reason"], item["patch"].strip()[:1500], "\n".join(item["errors"][:5]) or "(none)"))
    sections.append(FORMAT)
    return "\n\n".join(sections)


def language_prompt(view):
    """Language check (r2.16): asked only for inputs of unknown language with parser errors only."""
    text = "\n".join(view.lines["F1"][:80])
    return "Is the following text Solidity source code? Answer SOLIDITY or OTHER.\n\n" + text
