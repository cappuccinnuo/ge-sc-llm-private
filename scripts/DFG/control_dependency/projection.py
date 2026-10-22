"""Exact raw-AST to frozen-HCG control dependence projection.

No vulnerability attributes or node features participate in selecting edges.
One projected edge can retain several independent function-context proofs.
"""
import copy
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from ..models import Unsupported
from ..projection import Projector
from ..graph_audit import fingerprint, frozen

RELATION = "CONTROL_DEPENDENCE"
VERSION = "guard-exact-projection-v1"


def project_results(graph, view, results):
    projector = Projector(graph, view)
    proofs, records = [], []
    for result in results:
        record = {"function": result.function, "status": result.status,
                  "semantic_facts": len(result.facts), "projected_facts": 0,
                  "diagnostics": list(result.diagnostics),
                  "semantic_evidence": result.evidence}
        records.append(record)
        if result.status != "analyzed":
            # Even an accidental stale fact list from a failed analysis cannot leak.
            record["discarded_fallback_facts"] = len(result.facts)
            continue
        temporary = []
        try:
            for fact in result.facts:
                if fact.function != result.function or fact.source_sha256 != view.sha256:
                    raise Unsupported("Fact function/source identity mismatch")
                if fact.relation != RELATION:
                    raise Unsupported("Unexpected control fact relation")
                nodes = []
                missing = []
                for role, anchor in (("controller", fact.controller),
                                     ("controlled", fact.controlled)):
                    if anchor.file != view.file:
                        raise Unsupported("Cross-file control fact")
                    key = view.compat_key(anchor)
                    identifier = projector.by_ast.get(view.compat_ids[key])
                    if identifier is None:
                        missing.append(dict(asdict(anchor), endpoint=role,
                            reason="Exact semantic anchor has no existing HCG node"))
                    nodes.append(identifier)
                if missing:
                    record["diagnostics"].append({"kind": "projection_missing", "anchors": missing})
                    continue
                source, target = nodes
                if source == target:
                    record["diagnostics"].append({"kind": "same_projected_node", "node_id": source})
                    continue
                temporary.append({"function": fact.function, "source_file": view.file,
                    "source_sha256": view.sha256, "source_node": source, "target_node": target,
                    "controller": asdict(fact.controller), "controlled": asdict(fact.controlled),
                    "branch": fact.branch, "cfg_edge": list(fact.cfg_edge),
                    "cfg_path": list(fact.cfg_path), "semantic_evidence": fact.evidence,
                    "relation": RELATION, "projection_version": VERSION})
        except Unsupported as exc:
            record.update(status="function_projection_fallback", discarded_partial_facts=len(temporary))
            record["diagnostics"].append({"kind": "function_projection_fallback", "reason": str(exc)})
            continue
        record["projected_facts"] = len(temporary)
        proofs.extend(temporary)
    return proofs, {"projector": projector.stats, "functions": records,
                    "status_counts": dict(Counter(x["status"] for x in records)),
                    "projected_facts": len(proofs)}


def assert_preserved(base, enhanced):
    if frozen(base.graph) != frozen(enhanced.graph):
        raise AssertionError("Graph attributes changed")
    if frozen(list(base.nodes(data=True))) != frozen(list(enhanced.nodes(data=True))):
        raise AssertionError("Node identities/order/types/features/labels changed")
    retained = [(s,t,k,d) for s,t,k,d in enhanced.edges(keys=True,data=True)
                if d.get("edge_type") != RELATION]
    if frozen(list(base.edges(keys=True,data=True))) != frozen(retained):
        raise AssertionError("Original CFG/CG/DDG edges, keys, order or attributes changed")
    pairs = set()
    for source, target, data in enhanced.edges(data=True):
        if data.get("edge_type") != RELATION:
            continue
        if source == target or (source,target) in pairs:
            raise AssertionError("Self/duplicate control relation")
        if enhanced.nodes[source]["source_file"] != enhanced.nodes[target]["source_file"]:
            raise AssertionError("Cross-file control relation")
        pairs.add((source,target))
    return {"nodes": len(base), "base_edges": base.number_of_edges(),
            "enhanced_edges": enhanced.number_of_edges(), "added_control_edges": len(pairs),
            "node_attributes_exact": True, "base_edges_exact": True,
            "node_attributes_sha256": hashlib.sha256(json.dumps(frozen(list(base.nodes(data=True))), sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "base_fingerprint": fingerprint(base), "enhanced_fingerprint": fingerprint(enhanced)}


def materialize(base, proofs):
    if any(d.get("edge_type") == RELATION for _,_,d in base.edges(data=True)):
        raise ValueError("Use frozen HCG_DDG input without an existing control extension")
    grouped = defaultdict(list)
    for index, proof in enumerate(proofs):
        if proof["relation"] != RELATION:
            raise ValueError("Unexpected relation in control evidence")
        source, target = proof["source_node"], proof["target_node"]
        if source not in base or target not in base or source == target:
            raise ValueError("Control endpoint missing or identical")
        if (base.nodes[source]["source_file"] != proof["source_file"] or
                base.nodes[target]["source_file"] != proof["source_file"]):
            raise ValueError("Control proof/source mismatch")
        grouped[(source,target)].append(index)
    enhanced = copy.deepcopy(base)
    context = Counter()
    incoming = {}
    for (source,target), indices in grouped.items():
        if base.has_edge(source,target):
            context["existing_direct_pair_new_relation"] += 1
        else:
            context["new_direct_pair"] += 1
            if target not in incoming:
                incoming[target] = set(base.predecessors(target))
            if set(base.successors(source)) & incoming[target]:
                context["new_pair_existing_two_hop_path"] += 1
            else:
                context["new_pair_no_existing_path_within_two_hops"] += 1
        functions = sorted({proofs[i]["function"] for i in indices})
        if len(functions) > 1:
            context["pairs_with_multiple_function_contexts"] += 1
        enhanced.add_edge(source, target, edge_type=RELATION,
            control_evidence_indices=indices, control_function_contexts=functions,
            control_projection_version=VERSION)
    invariants = assert_preserved(base, enhanced)
    return enhanced, invariants, dict(context)
