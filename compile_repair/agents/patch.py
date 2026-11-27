"""Patch format parsing, original-text check, D7 check and byte patches (PROMPTS 3.5 item 4).

A candidate answer is a list of REPLACE and INSERT blocks over the view (agents/prompt.py).
It is rejected as a whole when any block is malformed, names an unknown file, quotes an
original line that differs from the view (RustAssistant), rewrites a line that carries no
error or a file that may not be edited (D7), overlaps another block, or adds a comment.
An accepted candidate becomes byte patches on the real files: a REPLACE covers the real
bytes of its lines (newline excluded); an INSERT adds bytes at the start of its line.
Import strings that show an F number are written back as the real relative path.
"""
import posixpath
import re

from compile_repair.core.model import Patch

STEP = "stage1"
_HEADER = re.compile(r"^@@ (REPLACE (?P<rfile>\S+) (?P<first>\d+)-(?P<last>\d+)|INSERT (?P<ifile>\S+) BEFORE (?P<before>\d+)"
                     r"|WITH|END)\s*$")
_ORIGINAL = re.compile(r"^\s*(?P<n>\d+)\| ?(?P<text>.*)$")
_COMMENT = re.compile(r'//|/\*')
_STRING = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_IMPORT_LABEL = re.compile(r'(?P<q>["\'])(?P<label>F\d+|missing\d+)(?P=q)')


class PatchRejected(ValueError):
    pass


def parse_blocks(text):
    """[(kind, file, first, last, original lines, new lines)]; text outside blocks is ignored."""
    blocks, current, part = [], None, None
    for line in text.replace("\r\n", "\n").split("\n"):
        header = _HEADER.match(line.strip()) if line.startswith("@@") else None
        if header:
            if header.group(1) == "WITH":
                if current is None or current[0] != "REPLACE" or part != "original":
                    raise PatchRejected("WITH outside a REPLACE block")
                part = "new"
            elif header.group(1) == "END":
                if current is None:
                    raise PatchRejected("END outside a block")
                if current[0] == "REPLACE" and part != "new":
                    raise PatchRejected("REPLACE block without WITH")
                blocks.append(tuple(current))
                current = part = None
            elif current is not None:
                raise PatchRejected("block not closed before the next one")
            elif header.group("rfile"):
                current = ["REPLACE", header.group("rfile"), int(header.group("first")), int(header.group("last")), [], []]
                part = "original"
            else:
                current = ["INSERT", header.group("ifile"), int(header.group("before")), None, [], []]
                part = "new"
        elif current is not None:
            current[4 if part == "original" else 5].append(line)
    if current is not None:
        raise PatchRejected("block not closed")
    if not blocks:
        raise PatchRejected("no patch block")
    return blocks


def _has_comment(lines):
    return any(_COMMENT.search(_STRING.sub('""', line)) for line in lines)


def _restore_imports(line, view, file_id, importer):
    """Write F numbers in import strings back as real paths relative to the importer."""
    if "import" not in line:
        return line
    def real(match):
        label = match.group("label")
        if label.startswith("missing"):
            for targets in view.import_targets[file_id].values():
                if label in targets:
                    return match.group("q") + targets[label] + match.group("q")
            raise PatchRejected("unknown import label " + label)
        if label not in view.names:
            raise PatchRejected("unknown file " + label)
        path = posixpath.relpath(view.names[label], posixpath.dirname(importer) or ".")
        return match.group("q") + (path if path.startswith("../") else "./" + path) + match.group("q")
    return _IMPORT_LABEL.sub(real, line)


def candidate_patches(text, view, contents, allowed_lines, editable, round_no, step=STEP):
    """Validate one answer; return ({real name: new bytes}, {real name: (Patch, ...)}, summary).

    `step` labels the patches in provenance: "stage1" or "stage2".
    """
    blocks = parse_blocks(text)
    per_file, claimed = {}, {}
    for kind, file_id, first, last, original, new in blocks:
        if file_id not in view.names:
            raise PatchRejected("unknown file " + file_id)
        name = view.names[file_id]
        if name not in editable:
            raise PatchRejected("file may not be edited: " + file_id)
        lines = view.lines[file_id]
        if _has_comment(new):
            raise PatchRejected("the patch adds a comment")
        restored = [_restore_imports(line, view, file_id, name) for line in new]
        spans = view.real_lines[file_id]
        if kind == "REPLACE":
            if not 1 <= first <= last <= len(lines):
                raise PatchRejected("line range outside %s" % file_id)
            numbered = [_ORIGINAL.match(line) for line in original if line.strip()]
            if len(numbered) != last - first + 1 or any(m is None for m in numbered):
                raise PatchRejected("original lines missing or unnumbered")
            for expected, match in zip(range(first, last + 1), numbered):
                if int(match.group("n")) != expected or match.group("text").rstrip() != lines[expected - 1].rstrip():
                    raise PatchRejected("original line %s:%d does not match the file" % (file_id, expected))
            outside = [n for n in range(first, last + 1) if n not in allowed_lines.get(file_id, ())]
            if outside:
                raise PatchRejected("rewrites lines without an error: %s:%s" % (file_id, outside))
            start, end = spans[first - 1][0], spans[last - 1][1]
            data = "\n".join(restored).encode("utf8")
        else:
            if not 1 <= first <= len(lines) + 1:
                raise PatchRejected("insertion point outside %s" % file_id)
            if not restored or all(not line.strip() for line in restored):
                raise PatchRejected("empty insertion")
            start = end = spans[first - 1][0] if first <= len(spans) else len(contents[name])
            data = ("\n".join(restored) + "\n").encode("utf8")
            if first > len(spans) and contents[name] and not contents[name].endswith(b"\n"):
                data = b"\n" + data[:-1]
        for a, b in claimed.get(name, ()):
            if start < b and a < end or (start == end and a < start < b) or (start == end == a == b):
                raise PatchRejected("blocks overlap in " + file_id)
        claimed.setdefault(name, []).append((start, end))
        per_file.setdefault(name, []).append(Patch(start, end, contents[name][start:end], data, step, round_no,
                                                    "%s %s:%d" % (kind.lower(), file_id, first)))
    edits, patches = {}, {}
    for name, items in per_file.items():
        ordered = sorted(items, key=lambda p: (-p.start, -p.end))
        current = contents[name]
        for p in ordered:
            current = current[:p.start] + p.replacement + current[p.end:]
        if current == contents[name]:
            continue
        edits[name], patches[name] = current, tuple(ordered)
    if not edits:
        raise PatchRejected("the patch changes nothing")
    changed = sum(max(len(p.replacement), p.end - p.start) for ps in patches.values() for p in ps)
    return edits, patches, dict(blocks=len(blocks), changed_bytes=changed)
