"""Steps 7–8 (CP6.2: step 8): additive structure completion, never guessing behaviour.

- closing braces: a file whose only unmatched brackets are opening braces gets the
  missing `}` appended at the end; any unmatched closer, or an unclosed `(` or `[`,
  leaves the file alone (the intended structure is ambiguous);
- fragment wrapper: contract members written at file level (functions, modifiers,
  state variables, events, ...) are enclosed in a new contract, but only for runs
  that contain a compiler diagnostic, so valid free functions and file-level
  declarations of newer Solidity versions are never moved.
Both only insert text. The pipeline accepts a proposal under PROMPTS 3.1 and D27.
"""
import re

from compile_repair.core.model import Patch
from compile_repair.rules.normalize import TokenLayout, compose_patches, diagnostic_offset

STEP = "structure"
_OPENERS = {b"{": b"}", b"(": b")", b"[": b"]"}
_CLOSERS = {b"}", b")", b"]"}
_DIRECTIVES = (b"pragma", b"import")
_UNITS = (b"contract", b"library", b"interface", b"abstract")
_MEMBERS = (b"function", b"modifier", b"constructor", b"fallback", b"receive", b"event", b"mapping",
            b"struct", b"enum", b"using", b"error")
_ELEMENTARY = re.compile(rb"^(u?int\d*|address|bool|string|bytes\d*|byte|u?fixed[0-9x]*|var)$")
_STATEMENTS = (b"return", b"emit", b"require", b"assert", b"revert", b"if", b"for", b"while", b"do", b"delete",
               b"throw", b"let", b"const", b"else", b"new", b"this", b"msg")
_PARSER = {"parser_error_other", "unbalanced_structure", "file_level_member"}


def _unmatched(layout):
    """Return (unclosed openers in order, whether any closer is unmatched)."""
    stack = []
    for word in layout.words:
        if word in _OPENERS:
            stack.append(word)
        elif word in _CLOSERS:
            if not stack or _OPENERS[stack[-1]] != word:
                return stack, True
            stack.pop()
    return stack, False


def _kind(layout, i):
    word = layout.words[i]
    following = layout.words[i + 1] if i + 1 < len(layout.words) else None
    if word in _DIRECTIVES:
        return "directive"
    if word in _UNITS:
        return "unit"
    if word in _MEMBERS or _ELEMENTARY.match(word):
        return "member"
    # A user-defined type followed by a name or modifier keyword declares a state variable.
    if word not in _STATEMENTS and layout.tokens[i][2] == "word" and following is not None and layout.tokens[i + 1][2] == "word":
        return "member"
    return "other"


def _items(layout):
    """Split the file into top-level items: (kind, first token, last token)."""
    items, i, n = [], 0, len(layout.words)
    while i < n:
        k = i
        while k < n:
            word = layout.words[k]
            if word == b";":
                break
            if word in _OPENERS:
                close = layout.matches.get(k)
                if close is None:
                    k = n - 1
                    break
                if word == b"{":
                    k = close
                    break
                k = close
            k += 1
        last = min(k, n - 1)
        items.append((_kind(layout, i), i, last))
        i = last + 1
    return items


def structure_completion(raw, diagnostics):
    """Propose closing braces and fragment wrappers for one file; return (patches, evidence)."""
    if not any(r.get("category") in _PARSER for r in diagnostics):
        return [], []
    layout = TokenLayout(raw)
    if not layout.words:
        return [], []
    stack, stray = _unmatched(layout)
    if stray or any(o != b"{" for o in stack):
        return [], [dict(reason="ambiguous_brackets", unclosed=[o.decode() for o in stack], stray_closer=stray)]
    closers = b"}" * len(stack)
    items = _items(layout)
    offsets = [diagnostic_offset(raw, r) for r in diagnostics if r.get("category") in _PARSER]
    diagnosed = set()
    for offset in (o for o in offsets if o is not None):
        for index, (kind, first, last) in enumerate(items):
            # A diagnostic inside an item, or between items, belongs to the next item.
            if offset <= layout.tokens[last][1]:
                diagnosed.add(index)
                break
    runs, current = [], []
    for index, item in enumerate(items):
        if item[0] == "member":
            current.append(index)
            continue
        if current:
            runs.append(current)
        current = []
    if current:
        runs.append(current)
    wrapped = [run for run in runs if diagnosed.intersection(run)]
    names = set(layout.words)
    name, number = b"Fragment", 0
    while name in names:
        number += 1
        name = b"Fragment%d" % number
    patches, evidence, end_used = [], [], False
    for run in wrapped:
        start = layout.tokens[items[run[0]][1]][0]
        patches.append(Patch(start, start, b"", b"contract " + name + b" { ", STEP, reason="fragment wrapper start"))
        if run[-1] == len(items) - 1:
            end, suffix, end_used = len(raw), closers + b"\n}\n", True
        else:
            end, suffix = layout.tokens[items[run[-1]][2]][1], b"\n}"
        patches.append(Patch(end, end, b"", suffix, STEP, reason="fragment wrapper end"))
        evidence.append(dict(rule="fragment_wrapper", contract=name.decode(), members=len(run),
                             kinds=sorted({layout.words[items[i][1]].decode(errors="replace") for i in run})))
    if closers and not end_used:
        patches.append(Patch(len(raw), len(raw), b"", b"\n" + closers + b"\n", STEP, reason="closing braces"))
    if closers:
        evidence.append(dict(rule="closing_braces", added=len(stack)))
    if not patches:
        evidence.append(dict(reason="no_diagnosed_fragment" if runs else "no_fragment"))
    return patches, evidence


def structure_repairs(contents, diagnostics, round_number=1):
    """Propose step-8 patches; same contract as rules.normalize.normalization_repairs."""
    edits, patches, evidence = {}, {}, []
    for name in sorted(contents):
        raw, rows = contents[name], list(diagnostics.get(name, ()))
        proposed, info = structure_completion(raw, rows)
        evidence += [dict(row, file=name) for row in info]
        composed = compose_patches(name, raw, proposed, round_number, evidence)
        if composed:
            edits[name], patches[name] = composed
    return edits, patches, evidence
