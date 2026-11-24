"""Step 5 (CP6.1): deterministic, mechanically checked source normalizations.

Every rule proposes byte patches for one file and never guesses behaviour:
- identical duplicates: a definition rejected as already declared is blanked only
  when an earlier definition in the same scope has exactly the same bytes;
- duplicate SPDX identifiers and repeated pragmas: later copies naming the same
  license or directive are blanked; different licenses or conflicting ABI coder
  selections are never merged or chosen between;
- pragma terminator: a Solidity pragma that runs into the next directive or
  declaration, or into the end of the file, gets the single missing semicolon;
- ABI coder: a file rejected for needing ABI coder v2 gets the documented
  `pragma experimental ABIEncoderV2;` when it selects no coder itself.
Blanking replaces bytes with spaces and keeps line breaks, so offsets and line
numbers of all other code are unchanged. The pipeline accepts a proposal only
under the PROMPTS 3.1 rule and records it through core.provenance.
"""
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches, verify_provenance
from compile_repair.toolchain.solc import lexical_tokens

STEP = "normalize"
_DECLARATIONS = (b"contract", b"interface", b"library", b"struct", b"enum", b"event", b"error",
                 b"function", b"modifier")
_FOLLOWERS = (b"pragma", b"import", b"contract", b"interface", b"library", b"abstract", b"function",
              b"struct", b"enum", b"event", b"error", b"using", b"type", b"uint", b"int", b"address")
_VERSION_CHARS = set(b"0123456789.^~<>=*|-")
_ABI_CODER = b"pragma experimental ABIEncoderV2;"


class _Layout:
    """Lexical tokens with matched brackets; comments are excluded by lexical_tokens."""

    def __init__(self, raw):
        self.raw = raw
        self.tokens = list(lexical_tokens(raw))
        self.words = [t[3] for t in self.tokens]
        self.matches, self.parent = {}, []
        stack = []
        for i, word in enumerate(self.words):
            self.parent.append(next((j for j in reversed(stack) if self.words[j] == b"{"), None))
            if word in (b"{", b"(", b"["):
                stack.append(i)
            elif word in (b"}", b")", b"]") and stack:
                self.matches[stack.pop()] = i

    def index_at(self, offset):
        """Return the first token starting at or after a byte offset."""
        return next((i for i, t in enumerate(self.tokens) if t[0] >= offset), None)

    def declaration(self, i):
        """Return (kind, name, first, last) for a declaration starting at token i, else None."""
        first = i
        if self.words[i] == b"abstract":
            i += 1
        if i + 1 >= len(self.words) or self.words[i] not in _DECLARATIONS or self.tokens[i + 1][2] != "word":
            return None
        k = i + 2
        while k < len(self.words) and self.words[k] not in (b"{", b";", b"}"):
            k = self.matches.get(k, k) + 1 if self.words[k] in (b"(", b"[") else k + 1
        if k >= len(self.words) or self.words[k] == b"}":
            return None
        last = self.matches.get(k) if self.words[k] == b"{" else k
        if last is None:
            return None
        return self.words[i], self.words[i + 1], first, last

    def span(self, first, last):
        return self.tokens[first][0], self.tokens[last][1]


def _blank(raw):
    """Spaces for every byte except line breaks, so lines and offsets are kept."""
    return bytes(b if b in (10, 13) else 32 for b in raw)


def _diagnostic_offset(raw, row):
    line, column = row.get("line"), row.get("column")
    lines = raw.splitlines(keepends=True)
    if line is None or column is None or not 1 <= line <= len(lines):
        return None
    return sum(len(x) for x in lines[:line - 1]) + column - 1


def identical_duplicates(raw, diagnostics):
    """Blank later definitions that duplicate an earlier one byte for byte in the same scope."""
    layout, patches, evidence = _Layout(raw), {}, []
    starts = {}
    for i in range(len(layout.words)):
        found = layout.declaration(i)
        if found and (i == 0 or layout.words[i - 1] != b"abstract"):
            starts[i] = found
    for row in diagnostics:
        if row.get("category") != "duplicate_definition":
            continue
        offset = _diagnostic_offset(raw, row)
        i = None if offset is None else layout.index_at(offset)
        if i is None or i not in starts:
            evidence.append(dict(line=row.get("line"), reason="no_declaration_at_location"))
            continue
        kind, name, first, last = starts[i]
        text = raw[slice(*layout.span(first, last))]
        same = sorted(j for j, (k, n, f, l) in starts.items()
                      if (k, n) == (kind, name) and layout.parent[j] == layout.parent[i]
                      and raw[slice(*layout.span(f, l))] == text)
        info = dict(line=row.get("line"), kind=kind.decode(), name=name.decode(errors="replace"), copies=len(same))
        evidence.append(info)
        if len(same) < 2:
            info["reason"] = "not_byte_identical"
            continue
        for j in same[1:]:
            lo, hi = layout.span(starts[j][2], starts[j][3])
            patches[lo] = Patch(lo, hi, raw[lo:hi], _blank(raw[lo:hi]), STEP, reason="identical duplicate " + info["name"])
        info["blanked"] = len(same) - 1
    return list(patches.values()), evidence


def duplicate_licenses(raw, diagnostics):
    """Blank later SPDX comments when every identifier in the file names the same license."""
    if not any(r.get("category") == "multiple_license_or_pragma" and "spdx" in (r.get("message") or "").lower()
               for r in diagnostics):
        return [], []
    comments, pos = [], 0
    marker = b"SPDX-License-Identifier:"
    while True:
        at = raw.find(marker, pos)
        if at < 0:
            break
        start = raw.rfind(b"//", 0, at)
        line_start = raw.rfind(b"\n", 0, at) + 1
        end = raw.find(b"\n", at)
        end = len(raw) if end < 0 else end
        if start >= line_start and not raw[line_start:start].strip():
            value = raw[at + len(marker):end].strip().rstrip(b"\r")
            comments.append((start, end, value))
        pos = at + len(marker)
    licenses = {v for _, _, v in comments}
    if len(comments) < 2 or len(licenses) != 1:
        return [], [dict(reason="different_licenses" if len(licenses) > 1 else "single_identifier",
                         licenses=sorted(v.decode(errors="replace") for v in licenses))]
    patches = [Patch(a, b, raw[a:b], _blank(raw[a:b]), STEP, reason="repeated SPDX identifier")
               for a, b, _ in comments[1:]]
    return patches, [dict(license=next(iter(licenses)).decode(errors="replace"), blanked=len(patches))]


def duplicate_pragmas(raw, diagnostics):
    """Blank later non-Solidity pragmas that repeat an earlier one byte for byte; conflicts stay."""
    if not any(r.get("category") == "multiple_license_or_pragma" and "spdx" not in (r.get("message") or "").lower()
               for r in diagnostics):
        return [], []
    layout, seen, patches, kinds = _Layout(raw), {}, [], {}
    for i, word in enumerate(layout.words[:-1]):
        if word != b"pragma" or layout.words[i + 1] == b"solidity":
            continue
        k = i
        while k < len(layout.words) and layout.words[k] != b";":
            k += 1
        if k >= len(layout.words):
            continue
        lo, hi = layout.span(i, k)
        text = b" ".join(layout.words[i + 1:k])
        kinds.setdefault(layout.words[i + 1], set()).add(text)
        if text in seen:
            patches.append(Patch(lo, hi, raw[lo:hi], _blank(raw[lo:hi]), STEP, reason="repeated pragma " + text.decode(errors="replace")))
        seen.setdefault(text, lo)
    if len(kinds.get(b"abicoder", ())) > 1:
        return [], [dict(reason="conflicting_abicoder", values=sorted(t.decode() for t in kinds[b"abicoder"]))]
    return patches, [dict(blanked=len(patches))] if patches else [dict(reason="no_identical_repeat")]


def pragma_terminators(raw):
    """Insert the one missing semicolon of a Solidity pragma followed by another directive."""
    layout, patches = _Layout(raw), []
    for i, word in enumerate(layout.words[:-2]):
        if word != b"pragma" or layout.words[i + 1] != b"solidity":
            continue
        k = i + 2
        while k < len(layout.words) and (set(layout.words[k]) <= _VERSION_CHARS or layout.words[k] in (b"x", b"X")):
            k += 1
        # The version run must end at a directive or declaration keyword, or at the end of the file.
        if k == i + 2 or (k < len(layout.words) and (layout.words[k] == b";" or layout.words[k] not in _FOLLOWERS)):
            continue
        end = layout.tokens[k - 1][1]
        follower = layout.words[k].decode() if k < len(layout.words) else "end of file"
        patches.append(Patch(end, end, b"", b";", STEP, reason="pragma terminator before " + follower))
    return patches


def abi_coder_pragma(raw, diagnostics):
    """Add the documented ABI coder v2 directive to a file that needs it and selects none."""
    if not any(r.get("category") == "abi_coder_required" for r in diagnostics):
        return []
    layout = _Layout(raw)
    for i, word in enumerate(layout.words[:-2]):
        if word == b"pragma" and (layout.words[i + 1] == b"abicoder" or
                                  layout.words[i + 1:i + 3] == [b"experimental", b"ABIEncoderV2"]):
            return []
    for i, word in enumerate(layout.words[:-1]):
        if word == b"pragma" and layout.words[i + 1] == b"solidity":
            k = i + 2
            while k < len(layout.words) and layout.words[k] != b";":
                k += 1
            if k < len(layout.words):
                end = layout.tokens[k][1]
                return [Patch(end, end, b"", b"\n" + _ABI_CODER, STEP, reason="ABI coder v2 required")]
    return [Patch(0, 0, b"", _ABI_CODER + b"\n", STEP, reason="ABI coder v2 required")]


def normalization_repairs(contents, diagnostics, round_number=1):
    """Propose step-5 patches. contents: {relative name: current bytes}; diagnostics: {name or None: rows}.

    Return (edits, patches, evidence): new bytes per changed file, the ordered
    patches against the current bytes, and per-rule evidence. Rules for
    different byte ranges compose; overlapping proposals are dropped together.
    """
    edits, patches, evidence = {}, {}, []
    unlocated = list(diagnostics.get(None, ()))
    for name in sorted(contents):
        raw, rows = contents[name], list(diagnostics.get(name, ()))
        proposed = pragma_terminators(raw) + abi_coder_pragma(raw, rows)
        found, info = identical_duplicates(raw, rows)
        proposed += found
        evidence += [dict(info_row, file=name, rule="identical_duplicates") for info_row in info]
        # File-level directive rules may use unlocated rows: they only act on identical repeats.
        found, info = duplicate_licenses(raw, rows + unlocated)
        proposed += found
        evidence += [dict(info_row, file=name, rule="duplicate_licenses") for info_row in info]
        found, info = duplicate_pragmas(raw, rows + unlocated)
        proposed += found
        evidence += [dict(info_row, file=name, rule="duplicate_pragmas") for info_row in info]
        if not proposed:
            continue
        proposed.sort(key=lambda p: (p.start, p.end))
        if any(a.end > b.start or (a.start == a.end == b.start == b.end) for a, b in zip(proposed, proposed[1:])):
            evidence.append(dict(file=name, rule="all", reason="overlapping_proposals"))
            continue
        ordered = tuple(Patch(p.start, p.end, p.expected, p.replacement, p.step, round_number, p.reason)
                        for p in reversed(proposed))
        after, trace = apply_patches(raw, ordered)
        verify_provenance(raw, after, trace)
        edits[name], patches[name] = after, ordered
        evidence.append(dict(file=name, rule="applied", patches=[p.reason for p in proposed]))
    return edits, patches, evidence
