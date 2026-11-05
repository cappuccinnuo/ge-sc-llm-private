"""Prompt 8E deterministic real-name inventories; no labels or model access.

The intervention is filewise spelling substitution, NOT a Solidity binding
resolver. Ambiguous marker declaration roles fail closed. Candidates are
declaration-backed ordinary spellings with lexical occurrence weights.
"""
import hashlib
import random
import re
from collections import Counter, defaultdict

from scripts.DFG.frontend import parse, walk
from ..projection_view import ProjectionView
from ..diagnostics8c.inference import identifiers
from ..diagnostics8d.renaming import EXCLUDED_NAMES, is_marker, rewrite_node

VERSION = "prompt8e-real-names-v1"
ROLES = ("function", "modifier", "event", "state", "parameter", "local", "field")


def excluded(word):
    return (word in EXCLUDED_NAMES or is_marker(word)
            or re.fullmatch(r"id[0-9]+", word) is not None)


def role(node):
    parent = node.parent
    if node.type == "function_definition" and parent.type == "contract_body":
        return "function"
    if node.type == "modifier_definition":
        return "modifier"
    if node.type == "event_definition":
        return "event"
    if node.type == "state_variable_declaration":
        return "state"
    if node.type in ("parameter", "event_parameter", "event_paramater"):
        return "parameter"
    if node.type == "struct_member":
        return "field"
    if node.type == "variable_declaration":
        if parent.type in ("struct_body", "struct_declaration"):
            return "field"
        return "local"
    return None


def contains(spans, lo, hi):
    return any(a <= lo and hi <= b for a, b in spans)


def inspect_source(source, expected_scopes=None):
    tree = parse(source)
    errors = [{"type": n.type, "span": [n.start_byte, n.end_byte]}
              for n in walk(tree.root_node) if n.type == "ERROR" or n.is_missing]
    if errors:
        raise ValueError("Frozen grammar errors/missing nodes: " + str(errors[:3]))
    injected = []
    declarations = []
    counts = Counter()
    by_word = defaultdict(set)
    for node in walk(tree.root_node):
        if node.type in ("function_definition", "modifier_definition",
                         "state_variable_declaration"):
            counts[node.type] += 1
        r = role(node)
        name = node.child_by_field_name("name")
        if r is None or name is None or name.type != "identifier":
            continue
        word = name.text.decode("utf8")
        row = dict(word=word, role=r, span=[name.start_byte, name.end_byte],
                   declaration_span=[node.start_byte, node.end_byte])
        declarations.append(row)
        by_word[word].add(r)
        if r in ("function", "modifier") and is_marker(word):
            injected.append([node.start_byte, node.end_byte])
    # Verify archived A_v2 exact compatibility-coordinate scope identities.
    scope_proof = None
    if expected_scopes is not None:
        view = ProjectionView(source, "scope.sol")
        computed = set()
        for node in walk(view.compat_tree.root_node):
            name = node.child_by_field_name("name")
            if (node.type in ("function_definition", "modifier_definition")
                    and name is not None and is_marker(name.text.decode("utf8"))):
                computed.add((name.text.decode("utf8"), node.start_byte, node.end_byte))
        expected = {tuple(v) for v in expected_scopes}
        if not expected.issubset(computed):
            raise ValueError("Archived A_v2 function scope identity changed")
        # Any AST-only injection scope absent from the graph is excluded too;
        # it must not be mistaken for ordinary pool material.
        scope_proof = dict(archived_scopes=len(expected), ast_scopes=len(computed),
                           ast_only_scopes=sorted(computed - expected),
                           all_archived_scopes_exact=True)
    lexemes = []
    for word, lo, hi in identifiers(source):
        # lexer offsets are Python characters, tree-sitter offsets are bytes.
        a = len(source[:lo].encode("utf8"))
        b = len(source[:hi].encode("utf8"))
        lexemes.append(dict(word=word, span=[a, b],
                            injected=contains(injected, a, b) or is_marker(word)))
    marker_roles = {}
    for word in sorted({v["word"] for v in lexemes if is_marker(v["word"])}):
        if len(by_word[word]) != 1:
            raise ValueError("Missing/ambiguous marker declaration role: " + word)
        marker_roles[word] = next(iter(by_word[word]))
    for row in declarations:
        row["injected"] = contains(injected, *row["span"]) or is_marker(row["word"])
    return dict(declarations=declarations, lexemes=lexemes, marker_roles=marker_roles,
                counts=dict(counts), injected_raw_spans=injected,
                scope_proof=scope_proof, parser_errors=0,
                source_sha256=hashlib.sha256(source.encode("utf8")).hexdigest())


def build_pool(inventories):
    weights = {r: Counter() for r in ROLES}
    witnesses = {r: defaultdict(list) for r in ROLES}
    for identity, inv in sorted(inventories.items()):
        frequency = Counter(row["word"] for row in inv["lexemes"]
                            if not row["injected"] and not excluded(row["word"]))
        ordinary = {(d["role"], d["word"]) for d in inv["declarations"]
                    if not d["injected"] and not excluded(d["word"])}
        for r, word in sorted(ordinary):
            if frequency[word] == 0:
                raise AssertionError("Declaration without ordinary lexical witness")
            weights[r][word] += frequency[word]
            witnesses[r][word].append(dict(identity=identity,
                source_sha256=inv["source_sha256"], ordinary_occurrences=frequency[word]))
    return dict(version=VERSION, roles={r: dict(sorted(w.items())) for r, w in weights.items()},
                witnesses={r: dict(v) for r, v in witnesses.items()},
                frequency_unit="lexical occurrences outside injection scopes per declaration-backed role",
                cross_role_ambiguous_occurrences="counted for each evidenced role, not resolved bindings",
                corpus_scope="all frozen 128 node-task source identities; transductive vocabulary, no labels")


def make_mapping(inv, pool):
    seed = int(hashlib.sha256((VERSION + ":" + inv["source_sha256"]).encode()).hexdigest(), 16)
    rng = random.Random(seed)
    forbidden = {x["word"] for x in inv["lexemes"]}
    mapping, audit = {}, []
    for old, r in sorted(inv["marker_roles"].items()):
        candidates = [(w, n) for w, n in sorted(pool["roles"][r].items())
                      if w not in forbidden and not excluded(w)]
        if not candidates:
            raise ValueError("Insufficient collision-free real-name pool for role " + r)
        total = sum(n for _, n in candidates)
        draw = rng.randrange(total)
        chosen = None
        for word, weight in candidates:
            if draw < weight:
                chosen = word
                break
            draw -= weight
        mapping[old] = chosen
        forbidden.add(chosen)
        audit.append(dict(original=old, replacement=chosen, role=r,
                          candidate_count=len(candidates), total_weight=total,
                          weight=pool["roles"][r][chosen]))
    if len(set(mapping.values())) != len(mapping):
        raise AssertionError("Replacement mapping is not injective")
    return dict(mapping=mapping, choices=audit, seed=str(seed), source_sha256=inv["source_sha256"],
                algorithm=VERSION, collisions=0)


def verify_rewrite(source, mapping, before=None):
    before = before or inspect_source(source)
    rewritten, edits = rewrite_node(source, mapping)
    after = inspect_source(rewritten)
    if before["counts"] != after["counts"]:
        raise ValueError("Declaration counts changed")
    if any(is_marker(v["word"]) for v in after["lexemes"]):
        raise ValueError("Marker identifier remains")
    a, b = parse(source), parse(rewritten)
    def shape(tree):
        return [(n.type, len(n.children), n.is_named, n.is_missing) for n in walk(tree.root_node)]
    if shape(a) != shape(b):
        raise ValueError("AST topology changed during lexical substitution")
    return rewritten, dict(parser_errors=0, missing_nodes=0, declaration_counts=after["counts"],
                            ast_topology_identical=True, replaced_occurrences=len(edits),
                            compilation_verified=False)
