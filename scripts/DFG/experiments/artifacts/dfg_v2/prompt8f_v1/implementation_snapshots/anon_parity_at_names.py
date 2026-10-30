"""Prompt 8F exact source-bound HCG code view and temporary semantic parity.

No model input graph is written. Original nodes, labels, tokens and edges stay
unchanged. Synthetic CFG nodes have no saved AST ID: their code can only change
if every exact AST text match yields the same rewritten string; otherwise the
whole source/graph check fails, without nearest-line guesses.
"""
import copy
from collections import Counter
import pydot

from scripts.DFG.projection import ANCHOR, decoded, code_equal, Projector
from ..projection_view import ProjectionView
from ..pipeline import build
from .anon_binding import replace_spans
from .feature_view import graph_fingerprint
from .rename_parity import evidence_counter, count_facts, edge_counter


def node_code_view(graph, file, source, result):
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
    # Tree topology is already checked on raw AST; verify the compatibility IDs too.
    for ident in old_ids:
        if old_ids[ident][2] != new_ids[ident][2]:
            raise ValueError("Compatibility AST role differs")
    changes, proof = {}, []
    for nid, attrs in graph.nodes(data=True):
        if attrs["source_file"] != file:
            raise ValueError("File subgraph contains foreign source")
        label = ANCHOR.search(decoded(attrs.get("label", "")))
        if label:
            ids = [int(label.group(1))]
            if projector.by_ast.get(ids[0]) != nid:
                raise ValueError("Source anchor differs")
            mode = "saved_ast_id"
        elif attrs["node_type"] in ("end_if", "end_loop"):
            kinds = {"if_statement"} if attrs["node_type"] == "end_if" else {
                "for_statement", "while_statement", "do_while_statement", "if_statement"}
            ids = [ident for ident, k in old_ids.items() if k[2] in kinds
                   and code_equal(attrs["code"], before.compat[k[0]:k[1]].decode("utf8"))]
            mode = "all_exact_ast_text_matches_agree"
        else:
            raise ValueError("Node lacks an exact source anchor")
        rewritten = set()
        for ident in ids:
            old, new = old_ids[ident], new_ids[ident]
            a = before.compat[old[0]:old[1]].decode("utf8")
            b = after.compat[new[0]:new[1]].decode("utf8")
            if not code_equal(attrs["code"], a):
                raise ValueError("HCG code differs from exact original AST")
            rewritten.add(b if attrs["code"] == a else pydot.quote_if_necessary(b))
        if len(rewritten) != 1:
            raise ValueError("Synthetic code projection has missing/ambiguous declaration binding")
        changes[nid] = rewritten.pop()
        proof.append(dict(node=nid, basis=mode, compat_ast_ids=ids))
    return changes, proof


def check_file(base, archived, archived_audit, source, file, result, metadata, encoder):
    before = graph_fingerprint(base)
    codes, proof = node_code_view(base, file, source, result)
    temp = copy.deepcopy(base)
    for nid, code in codes.items():
        temp.nodes[nid]["code"] = code
    restored = copy.deepcopy(temp)
    for nid in restored:
        restored.nodes[nid]["code"] = base.nodes[nid]["code"]
    if graph_fingerprint(restored) != before:
        raise AssertionError("In-memory parity copy changed non-code graph data")
    original, orig_audit = build(base, {file: source}, {file: metadata},
                                 ["L1", "L2", "L3"], encoder)
    # Never pass the original source SHA-bound compiler metadata for renamed text.
    # The new temporary source uses its unchanged pragma. Exact fact equality is
    # required; a version-dependent support difference is a failed check.
    renamed, new_audit = build(temp, {file: result["rewritten"]}, {file: None},
                               ["L1", "L2", "L3"], encoder)
    inverse = {result["names"][d["id"]]: d["name"] for d in result["declarations"]
               if not d["preserved"]}
    counts = [count_facts(a, file) for a in (archived_audit, orig_audit, new_audit)]
    facts = [evidence_counter(archived_audit, file, source),
             evidence_counter(orig_audit, file, source),
             evidence_counter(new_audit, file, result["rewritten"], inverse, source)]
    edges = [edge_counter(g, file) for g in (archived, original, renamed)]
    same_counts = counts[0] == counts[1] == counts[2]
    same_facts = facts[0] == facts[1] == facts[2]
    same_edges = edges[0] == edges[1] == edges[2]
    if graph_fingerprint(base) != before:
        raise AssertionError("Original HCG mutated")
    deltas = {k: dict(archive_extra=sum((facts[1][k]-facts[0][k]).values()),
                     archive_missing=sum((facts[0][k]-facts[1][k]).values()),
                     renamed_extra=sum((facts[2][k]-facts[1][k]).values()),
                     renamed_missing=sum((facts[1][k]-facts[2][k]).values()))
              for k in facts[0]}
    return dict(file=file, passed=same_counts and same_facts and same_edges,
                counts=counts, fact_counts_equal=same_counts, normalized_facts_exact=same_facts,
                projected_endpoints_exact=same_edges, fact_differences=deltas,
                archived_edge_counts=dict(Counter(k[2] for k in edges[0])),
                renamed_edge_counts=dict(Counter(k[2] for k in edges[2])),
                node_code_proof=proof, original_hcg_exact=True, temporary_code_only=True,
                original_metadata_used=metadata is not None, renamed_metadata_used=False,
                renamed_version_source="unchanged pragma, no claim of compilation")
