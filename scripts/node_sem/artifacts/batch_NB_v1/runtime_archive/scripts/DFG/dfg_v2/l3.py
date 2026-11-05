"""L3 environment hubs on frozen HCG/L1/L2; source-only analysis.

Existing nodes/edges/features/labels remain unchanged. Only successfully
projected uses create an auxiliary node. REV relations belong to model input.
"""
import copy
import hashlib
from collections import Counter, defaultdict
from dataclasses import asdict
from numbers import Integral

import networkx as nx
import numpy as np

from scripts.DFG.frontend import walk
from scripts.DFG.graph_audit import fingerprint, frozen
from scripts.DFG.models import Unsupported
from scripts.DFG.projection import Projector
from scripts.DFG.experiments.runtime import assert_disconnected_files
from . import VERSION, ENV_SOURCE, ENV_FLOW
from .env import ENV_KEYS, EnvExtractor
from .l2 import context, identity, describe
from .projection_view import ProjectionView
from .state_binding import StateBinder
from .units import iter_statement_regions, projected_node

ENV_NODE_KEYS = frozenset(("node_type", "source_file", "code", "label", "method",
    "node_info_vulnerabilities", "node_source_code_lines", "type_label", "token", "dfg_v2_aux"))


def strip_aux(graph):
    """Return an independent original-node graph; never mutate the input."""
    result = copy.deepcopy(graph)
    result.remove_nodes_from([n for n, d in result.nodes(data=True)
                              if d.get("node_type") == ENV_SOURCE])
    return result


def _input(graph):
    if not isinstance(graph, nx.MultiDiGraph) or not graph:
        raise ValueError("Expected a nonempty MultiDiGraph")
    for node, data in graph.nodes(data=True):
        if not isinstance(node, Integral) or isinstance(node, bool):
            raise ValueError("Original HCG node IDs must be integers")
        if data.get("node_type") == ENV_SOURCE or data.get("dfg_v2_aux"):
            raise ValueError("Input already contains auxiliary nodes")
        if not isinstance(data.get("source_file"), str) or not data.get("node_type"):
            raise ValueError("Original nodes require source_file and node_type")
        token = data.get("token")
        if (type(token) is not np.ndarray or token.dtype != np.float32 or
                token.shape != (512,) or not np.isfinite(token).all()):
            raise ValueError("Original tokens must be float32 ndarray of shape (512,)")
    for _, _, data in graph.edges(data=True):
        relation = data.get("edge_type")
        if not isinstance(relation, str) or relation == ENV_FLOW or relation.startswith("REV_"):
            raise ValueError("Expected original/L1/L2 relations, without ENV_FLOW or REV")
    assert_disconnected_files(graph)


def assert_preserved(base, output):
    if fingerprint(strip_aux(output)) != fingerprint(base):
        raise AssertionError("Original HCG/L1/L2 changed")
    if list(output)[:len(base)] != list(base):
        raise AssertionError("Original node insertion order changed")
    added = [n for n in output if n not in base]
    if added != list(range(int(max(base)) + 1, int(max(base)) + 1 + len(added))):
        raise AssertionError("Auxiliary node allocation is not consecutive")
    seen = set()
    for node in added:
        data = output.nodes[node]
        if set(data) != ENV_NODE_KEYS or data["node_type"] != ENV_SOURCE or data["dfg_v2_aux"] is not True:
            raise AssertionError("Unexpected auxiliary attributes")
        key = (data["source_file"], data["code"])
        if data["code"] not in ENV_KEYS or key in seen:
            raise AssertionError("Unknown/duplicate file environment hub")
        seen.add(key)
        if output.in_degree(node) != 0 or output.out_degree(node) == 0:
            raise AssertionError("Environment hubs require outgoing uses only")
        if data["node_info_vulnerabilities"] is not None or data["node_source_code_lines"] != []:
            raise AssertionError("Auxiliary nodes cannot carry source labels")
        for _, target, attrs in output.out_edges(node, data=True):
            if target not in base or attrs["edge_type"] != ENV_FLOW:
                raise AssertionError("Unexpected auxiliary edge")
    edges = [(s, t, d) for s, t, d in output.edges(data=True) if d["edge_type"] == ENV_FLOW]
    if len({(s, t) for s, t, _ in edges}) != len(edges):
        raise AssertionError("Duplicate ENV_FLOW edge")
    if any(s not in added or t not in base for s, t, _ in edges):
        raise AssertionError("Unexpected environment endpoints")
    assert_disconnected_files(output)
    return dict(original_graph_exact=True, original_node_order_exact=True,
                L1_L2_edges_exact=True, added_nodes=len(added), added_edges=len(edges))


def _inside_assembly(node):
    while node is not None:
        if node.type == "assembly_statement":
            return True
        node = node.parent
    return False


def augment_l3(graph, sources, metadata, token_encoder):
    _input(graph)
    before = fingerprint(graph)
    output = copy.deepcopy(graph)
    audit = dict(version=VERSION, layer="L3", profiles=["G3", "G3R"], files={},
                 evidence=[], source_hashes={}, labels_used_for_analysis=False,
                 original_features_changed=False, tokenizer=copy.deepcopy(
                     getattr(token_encoder, "provenance", {"source": "caller_supplied_encoder"})))
    pending = defaultdict(list)
    for file in sorted({d["source_file"] for _, d in graph.nodes(data=True)}):
        record = dict(diagnostics=[], keys={}, units=0, assembly_skipped=0,
                      unknown_env_member={}, shadowed={}, unmapped_by_statement={},
                      callables={}, binding_scopes={})
        audit["files"][file] = record
        if file not in sources:
            record["diagnostics"].append(dict(kind="file_fallback", reason="missing_exact_source"))
            continue
        source = sources[file]
        audit["source_hashes"][file] = hashlib.sha256(source.encode("utf8")).hexdigest()
        try:
            view = ProjectionView(source, file)
            projector = Projector(graph, view)
        except Unsupported as exc:
            record["diagnostics"].append(dict(kind="projection_fallback", reason=str(exc)))
            continue
        record["projector"] = dict(projector.stats)
        for node in walk(view.tree.root_node):
            if node.type == "assembly_statement":
                record["assembly_skipped"] += 1
                record["diagnostics"].append(dict(kind="assembly_skipped",
                    reason="yul_not_interpreted", file=file, start=node.start_byte, end=node.end_byte))
        extractors = {}
        for candidate in iter_statement_regions(view, projector):
            if not candidate.regions or _inside_assembly(candidate.ast_node):
                continue
            owner = context(candidate.ast_node)
            if owner is None:
                continue
            owner_id = identity(file, owner)
            if owner_id not in extractors:
                binder = StateBinder(view, owner, (metadata or {}).get(file))
                extractors[owner_id] = EnvExtractor(binder)
                record["binding_scopes"][owner_id] = dict(scope_fallback=binder.scope_fallback,
                    locals=sorted(binder.locals), members=sorted(binder.members))
            target = projected_node(view, projector, candidate.ast_node)
            record["units"] += 1
            for occurrence in extractors[owner_id].extract(candidate.regions):
                key = occurrence.key
                rec = record["keys"].setdefault(key, dict(occurrences=0, projected=0,
                    unmapped=0, spellings={}, unmapped_by_statement={}))
                rec["occurrences"] += 1
                rec["spellings"][occurrence.spelling] = rec["spellings"].get(occurrence.spelling, 0) + 1
                status = "projected" if target is not None else "unmapped"
                rec[status] += 1
                if target is None:
                    kind = candidate.ast_node.type
                    rec["unmapped_by_statement"][kind] = rec["unmapped_by_statement"].get(kind, 0) + 1
                    record["unmapped_by_statement"][kind] = record["unmapped_by_statement"].get(kind, 0) + 1
                ev = dict(file=file, callable=owner_id, callable_kind=owner.type,
                    env_key=key, spelling=occurrence.spelling, occurrence=asdict(occurrence.span),
                    statement=describe(view, candidate.ast_node), source=None, target=target,
                    status=status)
                index = len(audit["evidence"])
                audit["evidence"].append(ev)
                record["callables"].setdefault(owner_id, dict(occurrences=0, projected=0))
                record["callables"][owner_id]["occurrences"] += 1
                record["callables"][owner_id]["projected"] += int(target is not None)
                if target is not None:
                    pending[(file, key, target)].append(index)
        for extractor in extractors.values():
            record["diagnostics"].extend(extractor.diagnostics)
        for diag in record["diagnostics"]:
            if diag["kind"] == "unknown_env_member":
                spelling = diag["spelling"]
                record["unknown_env_member"][spelling] = record["unknown_env_member"].get(spelling, 0) + 1
            elif diag["kind"] == "shadowed":
                key, reason = diag["key"], diag["reason"]
                bucket = record["shadowed"].setdefault(key, {})
                bucket[reason] = bucket.get(reason, 0) + 1
    used = {(file, key) for file, key, _ in pending}
    hubs = {}
    next_id = int(max(graph)) + 1
    for file, key in sorted(used, key=lambda item: (item[0], ENV_KEYS.index(item[1]))):
        token = token_encoder(key)
        if type(token) is not np.ndarray or token.dtype != np.float32 or token.shape != (512,) or not np.isfinite(token).all():
            raise ValueError("Encoder token type/dtype/shape differs from original")
        hubs[(file, key)] = next_id
        output.add_node(next_id, node_type=ENV_SOURCE, source_file=file, code=key,
            label="ENV:" + key, method="", node_info_vulnerabilities=None,
            node_source_code_lines=[], type_label=ENV_SOURCE, token=token.copy(), dfg_v2_aux=True)
        next_id += 1
    for (file, key, target), indices in pending.items():
        source_id = hubs[(file, key)]
        for index in indices:
            audit["evidence"][index]["source"] = source_id
        output.add_edge(source_id, target, edge_type=ENV_FLOW, dfg_v2_version=VERSION,
            env_key=key, spellings=sorted({audit["evidence"][i]["spelling"] for i in indices}),
            evidence_indices=indices)
    audit["invariants"] = assert_preserved(graph, output)
    if fingerprint(graph) != before:
        raise AssertionError("L3 mutated its input")
    audit["canonical_counts"] = [dict(canonical=list(key), edges=count) for key, count in sorted(Counter(
        (output.nodes[s]["node_type"], d["edge_type"], output.nodes[t]["node_type"])
        for s, t, d in output.edges(data=True) if d["edge_type"] == ENV_FLOW).items())]
    return output, audit
