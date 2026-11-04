"""Prompt 8G: identifier-AST spelling bijection, not declaration resolution.

Only exact frozen-grammar identifier nodes are selected. String/comment and
other grammar tokens are untouched. No label, graph, version or type evidence
selects a name. The original graph remains the model's semantic structure.
"""
import hashlib
import random
import re
from collections import Counter

from scripts.DFG.frontend import parse, walk
from .anon_binding import RESERVED, KEYWORD_STRINGS, shape, replace_spans

VERSION = "prompt8g-spelling-bijection-v1"
FIXED_TYPE = r"(?:u?fixed)[0-9]+x[0-9]+"


def reserved(name):
    return name in RESERVED or bool(re.fullmatch(FIXED_TYPE, name))


def identifier_rows(source):
    tree = parse(source)
    nodes = list(walk(tree.root_node))
    if any(n.type == "ERROR" or n.is_missing for n in nodes):
        raise ValueError("grammar_error_or_missing")
    rows = [dict(start=n.start_byte, end=n.end_byte, old=n.text.decode("utf8"),
                 node_type=n.type, parent_type=n.parent.type if n.parent else None)
            for n in nodes if n.type == "identifier"]
    return tree, sorted(rows, key=lambda r: r["start"])


def validate(source, result):
    """Recheck exact AST selection, bijection and bytes without trusting flags."""
    digest = hashlib.sha256(source.encode("utf8")).hexdigest()
    if digest != result["source_sha256"] or result["version"] != VERSION:
        raise ValueError("Source/version identity differs")
    if result["status"] != "renamed":
        raise ValueError("Fallback is not a complete spelling view")
    tree, rows = identifier_rows(source)
    selected = [r for r in rows if not reserved(r["old"])]
    names = {r["old"] for r in selected}
    mapping = result["mapping"]
    existing = {r["old"] for r in rows}
    if set(mapping) != names or len(set(mapping.values())) != len(mapping):
        raise ValueError("Mapping is not a bijection of selected spellings")
    if any(not re.fullmatch(r"v[0-9]+", v) or v in existing or reserved(v)
           for v in mapping.values()):
        raise ValueError("Anonymous spelling collision or invalid prefix")
    expected = [dict(start=r["start"], end=r["end"], old=r["old"],
                     new=mapping[r["old"]]) for r in selected]
    if result["edits"] != expected:
        raise ValueError("Edits do not exactly select identifier AST nodes")
    rewritten = replace_spans(source, expected)
    if rewritten != result["rewritten"]:
        raise ValueError("Rewritten source does not match exact byte edits")
    other, new_rows = identifier_rows(rewritten)
    if shape(tree) != shape(other):
        raise ValueError("AST node types/topology differ")
    if len(rows) != len(new_rows):
        raise ValueError("Identifier population differs")
    for old, new in zip(rows, new_rows):
        if new["old"] != mapping.get(old["old"], old["old"]):
            raise ValueError("Identifier spelling equality structure differs")
    counts = {s: source.count(s) for s in KEYWORD_STRINGS}
    if counts != {s: rewritten.count(s) for s in KEYWORD_STRINGS}:
        raise ValueError("Preserved keyword substring counts differ")
    return dict(grammar_errors=0, grammar_missing=0, topology_equal=True,
                exact_identifier_selection=True, bijective=True,
                identifier_occurrences=len(rows), edited_occurrences=len(expected),
                distinct_renamed_spellings=len(mapping), keyword_counts=counts,
                preserved_counts=dict(Counter(r["old"] for r in rows if reserved(r["old"]))))


def anonymize(source):
    source_sha = hashlib.sha256(source.encode("utf8")).hexdigest()
    result = dict(version=VERSION, source_sha256=source_sha, status="fallback",
                  mapping={}, edits=[], rewritten=source, issues=[],
                  binding_resolution_claimed=False, compilation_verified=False)
    try:
        _, rows = identifier_rows(source)
        names = sorted({r["old"] for r in rows if not reserved(r["old"])})
        occupied = {r["old"] for r in rows}
        numbers, number = [], 1
        while len(numbers) < len(names):
            if "v" + str(number) not in occupied:
                numbers.append(number)
            number += 1
        seed = int(hashlib.sha256((VERSION + ":" + source_sha).encode("ascii")).hexdigest(), 16)
        random.Random(seed).shuffle(numbers)
        mapping = {old: "v" + str(n) for old, n in zip(names, numbers)}
        edits = [dict(start=r["start"], end=r["end"], old=r["old"], new=mapping[r["old"]])
                 for r in rows if r["old"] in mapping]
        candidate = dict(result, status="renamed", mapping=mapping, edits=edits,
                         rewritten=replace_spans(source, edits),
                         numbering_seed_sha256=format(seed, "064x"),
                         sorted_spelling_order=names)
        candidate["verification"] = validate(source, candidate)
        return candidate
    except ValueError as exc:
        result["issues"] = [dict(reason=str(exc))]
        return result
