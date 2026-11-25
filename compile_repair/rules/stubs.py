"""Steps 7–8: additive declaration stubs (CP6.3) and structure completion (CP6.2), never guessing behaviour.

Step 7 declares names the compiler reports as undeclared, only from what their uses prove:
- base contract (`is X`): `contract X {}`, with a constructor when it is called with arguments;
- modifier (`m` or `m(...)` in a function header): `modifier m(...) { _; }` in the using contract;
- event (`emit E(...)`): `event E(...);` in the using contract;
- contract type used in a cast, a declaration or `new`: an interface listing exactly the
  functions called on it (a contract when created with `new`).
Parameter and return types come only from literals, `msg.sender`-like values, names
declared once with an elementary value type, and the call's context; any unknown type,
disagreeing call sites, member access without a call, or a mixed use drops that stub.
Plain variables are never declared, nor are keywords of newer Solidity versions.
Contracts and interfaces are inserted before the first top-level definition (a base must
precede its derived contract); modifiers and events right after the using contract's `{`.

Step 8:

- closing braces: a file whose only unmatched brackets are opening braces gets the
  missing `}` right after its last token; any unmatched closer, or an unclosed `(` or `[`,
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
from compile_repair.toolchain.solc import lexical_tokens

STEP = "structure"
STUB_STEP = "stub"
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
    # Insert at the end of the last token, so trailing whitespace and comments stay after the
    # completion and the added bytes sit next to the unclosed definition.
    tail = layout.tokens[-1][1]
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
            end, suffix, end_used = tail, closers + b"\n}", True
        else:
            end, suffix = layout.tokens[items[run[-1]][2]][1], b"\n}"
        patches.append(Patch(end, end, b"", suffix, STEP, reason="fragment wrapper end"))
        evidence.append(dict(rule="fragment_wrapper", contract=name.decode(), members=len(run),
                             kinds=sorted({layout.words[items[i][1]].decode(errors="replace") for i in run})))
    if closers and not end_used:
        patches.append(Patch(tail, tail, b"", closers, STEP, reason="closing braces"))
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


# ---- Step 7: declaration stubs -------------------------------------------------------------

_UNDECLARED = {"undeclared_identifier", "missing_base_contract"}
_DECLARING = (b"contract", b"interface", b"library", b"struct", b"enum", b"event", b"modifier", b"function", b"error")
# Reported as undeclared by older compilers, but keywords of newer ones: never declared.
_KEYWORDS = {b"virtual", b"override", b"immutable", b"unchecked", b"receive", b"fallback", b"abstract",
             b"payable", b"calldata", b"error", b"revert", b"emit", b"constructor", b"type", b"try", b"catch",
             b"this", b"super", b"now", b"msg", b"block", b"tx", b"abi", b"_"}
# Words that may sit in a function header or after a type without being a modifier or a name.
_HEADER_WORDS = {b"public", b"private", b"internal", b"external", b"view", b"pure", b"payable", b"constant",
                 b"returns", b"virtual", b"override", b"nonpayable", b"memory", b"storage", b"calldata", b"indexed"}
_VALUE_TYPE = re.compile(rb"^(u?int(8|16|24|32|40|48|56|64|72|80|88|96|104|112|120|128|136|144|152|160|168|176|184|192|200"
                         rb"|208|216|224|232|240|248|256)?|address|bool|bytes([1-9]|[12][0-9]|3[0-2])|byte)$")
_DECLARATION_WORDS = {b"public", b"private", b"internal", b"external", b"constant", b"immutable", b"payable",
                      b"indexed", b"memory", b"storage", b"calldata"}
_LITERALS = ((re.compile(rb"^(0x[0-9a-fA-F_]+|[0-9][0-9_]*(\.[0-9]+)?([eE][0-9]+)?)"
                         rb"(\s*(wei|gwei|szabo|finney|ether|seconds|minutes|hours|days|weeks))?$"), b"uint256"),
             (re.compile(rb"^(true|false)$"), b"bool"),
             (re.compile(rb"^(msg\.sender|tx\.origin|address\s*\(.*\)|payable\s*\(.*\))$", re.S), b"address"),
             (re.compile(rb"^(msg\.value|block\.(timestamp|number)|now|.*\.length)$", re.S), b"uint256"))


def _normal_type(word):
    if word == b"uint":
        return b"uint256"
    if word == b"int":
        return b"int256"
    if word == b"byte":
        return b"bytes1"
    return word


def _value_types(layout):
    """Names declared with an elementary value type; a name declared with two types is unknown."""
    found = {}
    for i, word in enumerate(layout.words[:-1]):
        if not _VALUE_TYPE.match(word) or (i and layout.words[i - 1] in (b".", b"(") and word == b"address"
                                           and layout.words[i + 1] == b"("):
            continue
        k = i + 1
        if layout.words[k] == b"(":  # a conversion such as uint(x), not a declaration
            continue
        while k < len(layout.words) and layout.words[k] in _DECLARATION_WORDS:
            k += 1
        if k < len(layout.words) and layout.tokens[k][2] == "word" and not _VALUE_TYPE.match(layout.words[k]):
            name = layout.words[k]
            found[name] = None if name in found and found[name] != _normal_type(word) else _normal_type(word)
    return {n: t for n, t in found.items() if t}


def _arguments(layout, open_index):
    """Token ranges [a, b) of the comma-separated arguments inside the brackets at open_index."""
    close = layout.matches.get(open_index)
    if close is None:
        return None
    ranges, a, k = [], open_index + 1, open_index + 1
    while k < close:
        word = layout.words[k]
        if word in _OPENERS:
            k = layout.matches.get(k, close)
        elif word == b",":
            ranges.append((a, k))
            a = k + 1
        k += 1
    if a < close or ranges:
        ranges.append((a, close))
    return [r for r in ranges if r[0] < r[1]] if not (len(ranges) == 1 and ranges[0][0] == close) else []


def _expression_type(layout, a, b, types):
    text = layout.raw[layout.tokens[a][0]:layout.tokens[b - 1][1]].strip()
    for pattern, value in _LITERALS:
        if pattern.match(text):
            return value
    if b - a == 1 and layout.tokens[a][2] == "word":
        return types.get(layout.words[a])
    return None


def _argument_types(layout, open_index, types):
    ranges = _arguments(layout, open_index)
    if ranges is None:
        return None
    result = [_expression_type(layout, a, b, types) for a, b in ranges]
    return None if None in result else result


def _return_type(layout, start, close, types):
    """Return (known, type or None) of a call expression from its context."""
    before = layout.words[start - 1] if start else b";"
    after = layout.words[close + 1] if close + 1 < len(layout.words) else b";"
    if after == b";" and before in (b";", b"{", b"}"):
        return True, None
    if before == b"=" and start >= 2 and layout.words[start - 2] != b"=" and after == b";":
        name = layout.words[start - 2]
        declared = layout.words[start - 3] if start >= 3 else None
        if declared is not None and _VALUE_TYPE.match(declared):
            return True, _normal_type(declared)
        if name in types:
            return True, types[name]
    if before == b"(" and start >= 2 and layout.words[start - 2] in (b"require", b"assert") and after in (b")", b","):
        return True, b"bool"
    return False, None


def _unit_body(layout, i):
    """The `{` of the top-level definition enclosing token i, or None."""
    j = layout.parent[i]
    while j is not None and layout.parent[j] is not None:
        j = layout.parent[j]
    return j


def _in_header(layout, i):
    """Whether token i is a modifier position: in a function header, outside any parentheses."""
    k = i - 1
    while k >= 0 and layout.words[k] not in (b";", b"{", b"}"):
        if layout.words[k] in (b"function", b"constructor", b"modifier"):
            depth = 0
            for word in layout.words[k:i]:
                depth += (word == b"(") - (word == b")")
            return depth == 0 and b"(" in layout.words[k:i]
        k -= 1
    return False


def _bases(layout, body):
    """Names listed after `is` in the header of the definition whose body starts at token body."""
    k = body - 1
    names = set()
    while k >= 0 and layout.words[k] not in (b"contract", b"interface", b"library"):
        if layout.tokens[k][2] == "word" and layout.words[k - 1] in (b"is", b",") and layout.parent[k] is None:
            names.add(layout.words[k])
        k -= 1
    return names


def _use_kind(layout, i, name):
    """How token i uses an undeclared name: base, event, new, modifier, type or other."""
    words = layout.words
    before = words[i - 1] if i else b""
    after = words[i + 1] if i + 1 < len(words) else b""
    body = _unit_body(layout, i)
    if before in (b"is", b",") and layout.parent[i] is None:
        return "base"
    if before == b"emit":
        return "event"
    if before == b"new":
        return "new"
    if body is not None and _in_header(layout, i):
        return "base" if name in _bases(layout, body) else "modifier"
    if after == b"(" and i + 2 < len(words) and words[i + 2] == b"{":
        return "struct"  # construction with named fields: S({a: x, b: y})
    if after in (b"memory", b"storage", b"calldata"):
        return "struct_variable"
    if after == b"(":
        close = layout.matches.get(i + 1)
        # A conversion X(a) counts only when a member of the result is used: X(a).f(...).
        return "type" if close is not None and close + 1 < len(words) and words[close + 1] == b"." else "other"
    if after in _DECLARATION_WORDS or (i + 1 < len(words) and layout.tokens[i + 1][2] == "word"):
        return "type"
    return "other"


def _struct_fields(layout, name, uses, types):
    """Fields {name: type} proven by named constructions S({k: v}) and member reads; else None."""
    fields, variables = None, set()
    for i in uses:
        kind = _use_kind(layout, i, name)
        if kind == "struct_variable":
            k = i + 2
            if k < len(layout.words) and layout.tokens[k][2] == "word":
                variables.add(layout.words[k])
            continue
        if kind != "struct":
            return None
        brace, close = i + 2, layout.matches.get(i + 2)
        if close is None:
            return None
        found, k = {}, brace + 1
        while k < close:
            if layout.tokens[k][2] != "word" or layout.words[k + 1] != b":":
                return None
            a = k + 2
            b = a
            while b < close and layout.words[b] != b",":
                b = layout.matches.get(b, b) + 1 if layout.words[b] in _OPENERS else b + 1
            value = _expression_type(layout, a, b, types)
            if value is None:
                return None
            found[layout.words[k]] = value
            k = b + 1
        if fields is None:
            fields = found
        elif fields != found:
            return None
    if not fields:
        return None
    for i, word in enumerate(layout.words[:-2]):
        if word in variables and layout.words[i + 1] == b"." and layout.words[i + 2] not in fields:
            return None  # a field no construction names
    return fields


def _parameters(types, prefix=b"_s"):
    return b", ".join(t + b" " + prefix + str(n).encode() for n, t in enumerate(types))


def _uses(layout, name):
    return [i for i, w in enumerate(layout.words) if w == name and (i == 0 or layout.words[i - 1] != b".")]


def _interface_members(layout, name, types):
    """Functions called on a contract type: {function: (argument types, return type)}, or None."""
    variables = set()
    for i in _uses(layout, name):
        k = i + 1
        while k < len(layout.words) and layout.words[k] in _DECLARATION_WORDS:
            k += 1
        if k < len(layout.words) and layout.tokens[k][2] == "word" and layout.words[i + 1] != b"(":
            variables.add(layout.words[k])
    sites = []
    for i, word in enumerate(layout.words):
        if word == name and i + 1 < len(layout.words) and layout.words[i + 1] == b"(" and (i == 0 or layout.words[i - 1] != b"new"):
            close = layout.matches.get(i + 1)
            if close is None:
                return None
            if close + 1 < len(layout.words) and layout.words[close + 1] == b".":
                sites.append((i, close + 2))
        elif word in variables and i + 1 < len(layout.words) and layout.words[i + 1] == b"." and \
                (i == 0 or layout.words[i - 1] != b"."):
            sites.append((i, i + 2))
    members = {}
    for start, member in sites:
        if member + 1 >= len(layout.words) or layout.words[member + 1] != b"(" or layout.tokens[member][2] != "word":
            return None
        arguments = _argument_types(layout, member + 1, types)
        close = layout.matches.get(member + 1)
        known, returned = _return_type(layout, start, close, types) if close is not None else (False, None)
        if arguments is None or not known:
            return None
        signature = (tuple(arguments), returned)
        if members.setdefault(layout.words[member], signature) != signature:
            return None
    return members


def declaration_stubs(raw, diagnostics, declared_elsewhere=frozenset()):
    """Propose step-7 stubs for one file; return (patches, evidence).

    solc reports one undeclared name per scope at a time, so besides the diagnosed names,
    names in unambiguous positions (a base list, `emit`, a header modifier slot) that no
    project file declares are stubbed in the same proposal. declared_elsewhere: names
    declared in the other files of the project.
    """
    rows = [r for r in diagnostics if r.get("category") in _UNDECLARED]
    if not rows:
        return [], []
    layout = TokenLayout(raw)
    if not layout.words or _unmatched(layout) != ([], False):
        return [], [dict(reason="unbalanced")] if layout.words else []
    types = _value_types(layout)
    declared = set(declared_elsewhere)
    for i, word in enumerate(layout.words[:-1]):
        if word in _DECLARING:
            declared.add(layout.words[i + 1])
    names = {}
    for row in rows:
        offset = diagnostic_offset(raw, row)
        i = None if offset is None else layout.index_at(offset)
        if i is None or layout.tokens[i][0] != offset or layout.tokens[i][2] != "word":
            continue
        name = layout.words[i]
        if name in _KEYWORDS or name in _HEADER_WORDS or name in declared or _ELEMENTARY.match(name):
            continue
        names.setdefault(name, i)
    if not names:
        return [], []
    for i, word in enumerate(layout.words):
        if (word in names or layout.tokens[i][2] != "word" or word in _KEYWORDS or word in _HEADER_WORDS
                or word in declared or _ELEMENTARY.match(word) or (i and layout.words[i - 1] == b".")):
            continue
        if _use_kind(layout, i, word) in ("base", "event", "modifier"):
            names.setdefault(word, i)
    top, inner, evidence = {}, {}, []
    for name, first in sorted(names.items()):
        uses = _uses(layout, name)
        kinds = {_use_kind(layout, i, name) for i in uses}
        info = dict(name=name.decode(errors="replace"), uses=sorted(kinds))
        evidence.append(info)
        if kinds <= {"struct", "struct_variable"} and "struct" in kinds:
            kinds = {"struct"}
        if len(kinds) != 1 or kinds == {"other"}:
            info["reason"] = "mixed_or_unknown_use"
            continue
        kind = kinds.pop()
        if kind in ("struct", "struct_variable"):
            fields = _struct_fields(layout, name, uses, types)
            bodies = {_unit_body(layout, i) for i in uses}
            if fields is None or len(bodies) != 1 or None in bodies:
                info["reason"] = "unknown_struct_fields"
                continue
            text = b" struct " + name + b" {" + b"".join(b" " + t + b" " + f + b";" for f, t in fields.items()) + b" }"
            inner.setdefault(bodies.pop(), []).append(text)
            info["stub"] = text.strip().decode(errors="replace")
            continue
        if kind in ("event", "modifier"):
            signatures = set()
            bodies = set()
            for i in uses:
                after = layout.words[i + 1] if i + 1 < len(layout.words) else b""
                signatures.add(tuple(_argument_types(layout, i + 1, types) or [None]) if after == b"(" else ())
                bodies.add(_unit_body(layout, i))
            if len(signatures) != 1 or None in next(iter(signatures)) or None in bodies:
                info["reason"] = "unknown_or_disagreeing_types"
                continue
            arguments = list(next(iter(signatures)))
            text = (b" event " + name + b"(" + b", ".join(arguments) + b");" if kind == "event" else
                    b" modifier " + name + b"(" + _parameters(arguments) + b") { _; }")
            for body in bodies:
                inner.setdefault(body, []).append(text)
            info["stub"] = text.strip().decode(errors="replace")
            continue
        if kind == "base":
            calls = set()
            for i in uses:
                if i + 1 < len(layout.words) and layout.words[i + 1] == b"(":
                    calls.add(tuple(_argument_types(layout, i + 1, types) or [None]))
            if len(calls) > 1 or (calls and None in next(iter(calls))):
                info["reason"] = "unknown_or_disagreeing_types"
                continue
            arguments = list(next(iter(calls))) if calls else []
            text = b"contract " + name + b" { " + (b"constructor(" + _parameters(arguments) + b") public {} " if arguments else b"") + b"}"
        elif kind == "new":
            text = b"contract " + name + b" {}"
        else:
            members = _interface_members(layout, name, types)
            if members is None:
                info["reason"] = "unknown_member_signature"
                continue
            functions = b"".join(b" function " + f + b"(" + _parameters(list(a)) + b") external" +
                                 (b" returns (" + r + b")" if r else b"") + b";" for f, (a, r) in sorted(members.items()))
            text = b"interface " + name + b" {" + functions + b" }"
        top[name] = text
        info["stub"] = text.decode(errors="replace")
    patches = []
    if top:
        first_unit = next((layout.tokens[i][0] for i, w in enumerate(layout.words)
                           if layout.parent[i] is None and w not in _DIRECTIVES
                           and (i == 0 or layout.words[i - 1] in (b";", b"}"))), layout.tokens[-1][1])
        text = b"".join(top[n] + b"\n" for n in sorted(top))
        patches.append(Patch(first_unit, first_unit, b"", text, STUB_STEP, reason="declaration stubs"))
    for body, texts in sorted(inner.items()):
        at = layout.tokens[body][1]
        patches.append(Patch(at, at, b"", b"".join(sorted(set(texts))), STUB_STEP, reason="member stubs"))
    return patches, evidence


def stub_repairs(contents, diagnostics, round_number=1):
    """Propose step-7 patches; same contract as rules.normalize.normalization_repairs."""
    edits, patches, evidence = {}, {}, []
    for name in sorted(contents):
        elsewhere = set()
        for other, raw in contents.items():
            if other != name:
                words = [t[3] for t in lexical_tokens(raw)]
                elsewhere.update(words[i + 1] for i, w in enumerate(words[:-1]) if w in _DECLARING)
        proposed, info = declaration_stubs(contents[name], list(diagnostics.get(name, ())), frozenset(elsewhere))
        evidence += [dict(row, file=name) for row in info]
        composed = compose_patches(name, contents[name], proposed, round_number, evidence)
        if composed:
            edits[name], patches[name] = composed
    return edits, patches, evidence
