"""Prompt 8G parity using 8F exact projection and field-specific normalization.

Temporary source/code views are discarded. No graph/label/token is written.
A spelling bijection intentionally does not claim declaration or ABI semantics.
"""
import copy
import json
from collections import Counter

from .spelling_names import validate
from .anon_parity import node_code_view, bound_evidence_counter
from .rename_parity import count_facts, edge_counter
from .feature_view import graph_fingerprint
from ..pipeline import build


def expanded(counter):
    return [dict(value=json.loads(k), count=n) for k, n in sorted(counter.items())]


def edge_rows(counter):
    return [dict(source=s, target=t, relation=r, count=n)
            for (s, t, r), n in sorted(counter.items(), key=lambda item: repr(item[0]))]


def check_file(base, archived, archive_audit, source, file, result, metadata, encoder):
    validate(source, result)
    before = graph_fingerprint(base)
    codes, proof = node_code_view(base, file, source, result)
    temp = copy.deepcopy(base)
    for nid, code in codes.items():
        temp.nodes[nid]["code"] = code
    restored = copy.deepcopy(temp)
    for nid in restored:
        restored.nodes[nid]["code"] = base.nodes[nid]["code"]
    if graph_fingerprint(restored) != before:
        raise AssertionError("Temporary view changed non-code graph data")
    original, orig_audit = build(base, {file: source}, {file: metadata},
                                 ["L1", "L2", "L3"], encoder)
    # Original-SHA metadata is not proof that the transformed text was compiled.
    renamed, new_audit = build(temp, {file: result["rewritten"]}, {file: None},
                               ["L1", "L2", "L3"], encoder)
    inverse = {new: old for old, new in result["mapping"].items()}
    counts = [count_facts(a, file) for a in (archive_audit, orig_audit, new_audit)]
    facts = [bound_evidence_counter(archive_audit, file, source),
             bound_evidence_counter(orig_audit, file, source),
             bound_evidence_counter(new_audit, file, result["rewritten"], inverse, source)]
    edges = [edge_counter(g, file) for g in (archived, original, renamed)]
    if graph_fingerprint(base) != before:
        raise AssertionError("Original HCG mutated")
    same_counts = counts[0] == counts[1] == counts[2]
    same_facts = facts[0] == facts[1] == facts[2]
    same_edges = edges[0] == edges[1] == edges[2]
    difference = {layer: dict(
        original_extra=expanded(facts[1][layer] - facts[0][layer]),
        original_missing=expanded(facts[0][layer] - facts[1][layer]),
        renamed_extra=expanded(facts[2][layer] - facts[1][layer]),
        renamed_missing=expanded(facts[1][layer] - facts[2][layer])) for layer in facts[0]}
    failed = not (same_counts and same_facts and same_edges)
    return dict(passed=not failed, fact_counts_equal=same_counts,
                normalized_facts_exact=same_facts, projected_endpoints_exact=same_edges,
                counts=counts, fact_differences=difference,
                edge_differences=dict(
                    original_extra=edge_rows(edges[1]-edges[0]), original_missing=edge_rows(edges[0]-edges[1]),
                    renamed_extra=edge_rows(edges[2]-edges[1]), renamed_missing=edge_rows(edges[1]-edges[2])),
                function_diagnostics=(dict(
                    original=orig_audit["layers"]["L1"]["files"][file]["analysis"]["functions"],
                    renamed=new_audit["layers"]["L1"]["files"][file]["analysis"]["functions"]) if failed else {}),
                node_code_proof=proof, original_hcg_exact=True, temporary_code_only=True,
                renamed_metadata_used=False, original_metadata_used=metadata is not None,
                renamed_version_source="unchanged pragma; original-SHA compiler evidence not transferred",
                compilation_verified=False, binding_resolution_claimed=False)


def projection_resolution(graph, source, file, result, expected_nodes):
    """Verify each historical ambiguous node with all exact AST candidates."""
    validate(source, result)
    codes, proof = node_code_view(graph, file, source, result)
    indexed = {p["node"]: p for p in proof}
    output = []
    for nid in expected_nodes:
        if nid not in indexed:
            raise ValueError("Historical synthetic node missing")
        row = indexed[nid]
        if row["basis"] != "all_exact_ast_text_matches_agree":
            raise ValueError("Historical node no longer uses original synthetic mapping")
        output.append(dict(node=nid, proof=row, rewritten_code=codes[nid],
                           all_exact_candidates_agree=True))
    return output
