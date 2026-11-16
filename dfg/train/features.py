"""Anonymized node features (N-anon-s): identifier spellings replaced before tokenizing.

SolidiFI-injected code names its bugs (``bug_txorigin20``, ``withdraw_re_ent1``), so
raw identifier spellings leak node labels. Each file gets a bijection from its user
identifier spellings to ``v<n>``; builtins, globals and type keywords are kept. Only
tree-sitter ``identifier`` nodes are rewritten; the AST shape, every other byte and
the counts of ``tx.origin``/``msg.sender``/... are checked unchanged. Each HCG node's
code is then re-read from the rewritten source at its own AST span and tokenized
with the HCG tokenizer. Graph structure and auxiliary ``env_source`` features are
unchanged. A file the grammar cannot parse keeps its original features (recorded).
"""
import copy
import hashlib
import random
import re

import numpy as np

from dfg.analysis.frontend import parse, walk
from dfg.graph.projection import ANCHOR, Projector, ProjectionView, code_equal, decoded
from dfg.schema import AUX_NODE_TYPES
from hcg.cfg.author_schema import quote

VERSION = "prompt8g-spelling-bijection-v1"
FIXED_TYPE = r"(?:u?fixed)[0-9]+x[0-9]+"
KEYWORD_STRINGS = ("tx.origin", "msg.sender", ".call.value(", ".send(", ".transfer(")
RESERVED = frozenset("""
abi addmod address after alias anonymous apply as assembly assert auto balance
block blockhash bool break byte bytes call callcode calldata caller callvalue
case catch chainid coinbase constant constructor continue contract copyof days
default define delegatecall delete do ecrecover else emit enum ether event
external fallback false final finney fixed for from function gas gasleft gwei
hours if immutable implements import in indexed inline int interface internal
is keccak256 length let library log0 log1 log2 log3 log4 mapping match memory
minutes modifier msg mulmod new now of origin override payable pop pragma
private promise public pure push receive reference relocatable require return
returns revert ripemd160 seconds selfdestruct send sender sha256 sha3 static
staticcall storage string struct suicide super supports switch szabo this
throw timestamp transfer transient true try tx type typeof ufixed uint unchecked using
value var view virtual weeks wei while years
""".split()) | frozenset(
    ["uint%d" % i for i in range(8, 257, 8)] +
    ["int%d" % i for i in range(8, 257, 8)] +
    ["bytes%d" % i for i in range(1, 33)] +
    ["difficulty", "prevrandao", "basefee", "blobbasefee", "blobhash",
     "number", "gaslimit", "data", "sig", "code", "codehash",
     "encode", "encodePacked", "encodeWithSelector", "encodeWithSignature",
     "encodeCall", "decode", "selector", "creationCode", "runtimeCode",
     "interfaceId", "min", "max"]) | frozenset(("gasprice", "solidity", "_"))


def reserved(name):
    return name in RESERVED or bool(re.fullmatch(FIXED_TYPE, name))


def shape(tree):
    return [(n.type, len(n.children), n.is_named, n.is_missing) for n in walk(tree.root_node)]


def replace_spans(source, edits):
    raw = source.encode("utf8")
    out, end = [], 0
    for e in sorted(edits, key=lambda x: x["start"]):
        a, b = e["start"], e["end"]
        if a < end or raw[a:b].decode("utf8") != e["old"]:
            raise ValueError("Overlapping/stale identifier edit")
        out.extend((raw[end:a], e["new"].encode("utf8")))
        end = b
    out.append(raw[end:])
    return b"".join(out).decode("utf8")


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
    if any(not re.fullmatch(r"v[0-9]+", v) or v in existing or reserved(v) for v in mapping.values()):
        raise ValueError("Anonymous spelling collision or invalid prefix")
    expected = [dict(start=r["start"], end=r["end"], old=r["old"], new=mapping[r["old"]]) for r in selected]
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
    return dict(identifier_occurrences=len(rows), edited_occurrences=len(expected),
                distinct_renamed_spellings=len(mapping))


def anonymize(source):
    """Per-file identifier bijection; deterministic in the source bytes."""
    source_sha = hashlib.sha256(source.encode("utf8")).hexdigest()
    result = dict(version=VERSION, source_sha256=source_sha, status="fallback",
                  mapping={}, edits=[], rewritten=source, issues=[])
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
                         rewritten=replace_spans(source, edits))
        candidate["verification"] = validate(source, candidate)
        return candidate
    except ValueError as exc:
        result["issues"] = [dict(reason=str(exc))]
        return result


def node_code_view(graph, file, source, result):
    """Rewritten code of every node of one file, read at the node's own AST span."""
    if result["status"] != "renamed":
        raise ValueError("Fallback cannot be presented as a fully anonymous HCG view")
    if replace_spans(source, result["edits"]) != result["rewritten"]:
        raise ValueError("Renamed source/edit binding differs")
    before = ProjectionView(source, file)
    after = ProjectionView(result["rewritten"], file)
    projector = Projector(graph, before)
    old_ids = {v: k for k, v in before.compat_ids.items()}
    new_ids = {v: k for k, v in after.compat_ids.items()}
    if set(old_ids) != set(new_ids):
        raise ValueError("Compatibility AST identity population differs")
    for ident in old_ids:
        if old_ids[ident][2] != new_ids[ident][2]:
            raise ValueError("Compatibility AST role differs")
    changes = {}
    for nid, attrs in graph.nodes(data=True):
        if attrs["source_file"] != file:
            raise ValueError("File subgraph contains foreign source")
        label = ANCHOR.search(decoded(attrs.get("label", "")))
        if label:
            ids = [int(label.group(1))]
            if projector.by_ast.get(ids[0]) != nid:
                raise ValueError("Source anchor differs")
        elif attrs["node_type"] in ("end_if", "end_loop"):
            kinds = {"if_statement"} if attrs["node_type"] == "end_if" else {
                "for_statement", "while_statement", "do_while_statement", "if_statement"}
            ids = [ident for ident, k in old_ids.items() if k[2] in kinds
                   and code_equal(attrs["code"], before.compat[k[0]:k[1]].decode("utf8"))]
        else:
            raise ValueError("Node lacks an exact source anchor")
        rewritten = set()
        for ident in ids:
            old, new = old_ids[ident], new_ids[ident]
            a = before.compat[old[0]:old[1]].decode("utf8")
            b = after.compat[new[0]:new[1]].decode("utf8")
            if not code_equal(attrs["code"], a):
                raise ValueError("HCG code differs from exact original AST")
            rewritten.add(b if attrs["code"] == a else quote(b))
        if len(rewritten) != 1:
            raise ValueError("Synthetic code projection has missing/ambiguous declaration binding")
        changes[nid] = rewritten.pop()
    return changes


def anonymous_codes(graph, sources):
    """{node id: anonymized code} for original nodes, and the files that fell back."""
    by_file = {}
    for nid, data in graph.nodes(data=True):
        if data["node_type"] not in AUX_NODE_TYPES:
            by_file.setdefault(data["source_file"], []).append(nid)
    codes, fallbacks = {}, {}
    for file, ids in sorted(by_file.items()):
        result = anonymize(sources[file])
        try:
            codes.update(node_code_view(graph.subgraph(ids).copy(), file, sources[file], result))
        except ValueError as exc:
            fallbacks[file] = result["issues"][0]["reason"] if result["issues"] else str(exc)
            codes.update({nid: graph.nodes[nid]["code"] for nid in ids})
    return codes, fallbacks


def anonymize_features(graph, sources, encoder):
    """Copy of ``graph`` whose original nodes carry anonymized token features."""
    codes, fallbacks = anonymous_codes(graph, sources)
    cache, result = {}, copy.deepcopy(graph)
    for nid, code in codes.items():
        if code not in cache:
            cache[code] = encoder(code)
        result.nodes[nid]["token"] = np.array(cache[code], dtype=np.float32)
    summary = dict(version=VERSION, nodes=len(codes),
                   changed_nodes=sum(codes[n] != graph.nodes[n]["code"] for n in codes),
                   fallback_files=fallbacks)
    return result, summary


def code_sha(code):
    return hashlib.sha256(code.encode("utf8")).hexdigest()
