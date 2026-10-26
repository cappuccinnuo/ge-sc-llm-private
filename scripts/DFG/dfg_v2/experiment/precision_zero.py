"""P7b.3 topology-only descriptions of accepted near-zero gradients.

No model construction, forward, backward, or optimization. Categories explain
old observations and are not new equivalence criteria. A shared key/query
tensor is attention-independent only if EVERY relevant training-reachable
canonical destination has one distinct source, including parallel edges.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import torch

from sco_models import graph_utils as gu
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.experiments.common import digest, read_json, sha256, tensor_digest, write_json
from scripts.DFG.dfg_v2 import AUX_NODE_TYPES
from scripts.DFG.dfg_v2.model_input import edge_data, materialize


CATEGORIES = {
    "a": "key_bias_softmax_translation_invariance",
    "b": "all_relevant_destinations_have_one_distinct_source",
    "c": "last_layer_target_has_no_supervision_path",
    "d": "observed_numerical_near_zero_without_topological_proof",
}


def topology_support(types, edges, supervised, layers):
    """Reverse reachability through remaining layers, including residuals."""
    if not isinstance(layers, int) or layers < 1 or len(types) != len(set(types)):
        raise ValueError("Invalid layer/type schema")
    if set(supervised) != set(types):
        raise ValueError("Supervision type schema mismatch")
    active = {typ: set(supervised[typ]) for typ in types}
    result = [None] * layers
    for layer in reversed(range(layers)):
        previous = {typ: set(active[typ]) for typ in types}
        relations = []
        for canonical in sorted(edges):
            if len(canonical) != 3 or canonical[0] not in active or canonical[2] not in active:
                raise ValueError("Invalid canonical schema")
            by_target = defaultdict(list)
            for source, target in edges[canonical]:
                if target in active[canonical[2]]:
                    by_target[target].append(source)
                    previous[canonical[0]].add(source)
            groups = [dict(destination=target, edge_count=len(sources),
                           distinct_source_count=len(set(sources)),
                           sources=sorted(set(sources)))
                      for target, sources in sorted(by_target.items())]
            relations.append(dict(
                canonical=list(canonical), reachable_edges=sum(g["edge_count"] for g in groups),
                reachable_destinations=len(groups),
                reachable_destinations_with_multiple_edges=sum(g["edge_count"] > 1 for g in groups),
                single_source_destinations=sum(g["distinct_source_count"] == 1 for g in groups),
                parallel_single_source_destinations=sum(g["edge_count"] > 1 and
                    g["distinct_source_count"] == 1 for g in groups),
                multiple_source_destinations=sum(g["distinct_source_count"] > 1 for g in groups),
                maximum_distinct_sources=max((g["distinct_source_count"] for g in groups), default=0),
                multi_source_examples=[g for g in groups if g["distinct_source_count"] > 1][:3]))
        result[layer] = dict(output_nodes_reaching_train={t: len(active[t]) for t in types},
                             relations=relations)
        active = previous
    return dict(node_types=list(types), layers=result,
                input_nodes_reaching_train={t: len(active[t]) for t in types})


def classify_parameter(name, support, profile):
    """Require a per-tensor proof across all applicable canonical relations."""
    row = dict(parameter=name, category="d", structural_proof=False, evidence={})
    fields = name.split(".")
    if (len(fields) == 5 and fields[0] == "gcs" and fields[1].isdigit()
            and fields[3].isdigit() and fields[4] in ("weight", "bias")):
        layer, type_index = int(fields[1]), int(fields[3])
        if layer >= len(support["layers"]) or type_index >= len(support["node_types"]):
            raise ValueError("Parameter references a missing layer or node type")
        kind, typ = fields[2], support["node_types"][type_index]
        layer_support = support["layers"][layer]
        row["evidence"] = dict(layer=layer, node_type=typ, parameter_kind=kind,
            reachable_target_nodes=layer_support["output_nodes_reaching_train"][typ])
        if kind == "k_linears" and fields[4] == "bias":
            row["category"] = "a"
        elif (profile == "G3R" and layer == len(support["layers"])-1
              and kind in ("q_linears", "a_linears", "norms")
              and not layer_support["output_nodes_reaching_train"][typ]):
            row["category"] = "c"
        elif kind in ("k_linears", "q_linears"):
            endpoint = 0 if kind == "k_linears" else 2
            relevant = [r for r in layer_support["relations"] if r["canonical"][endpoint] == typ
                        and r["reachable_edges"] > 0]
            row["evidence"].update(relevant_relations=relevant,
                relation_count=len(relevant),
                distinct_source_groups=sum(r["reachable_destinations"] for r in relevant),
                parallel_single_source_groups=sum(r["parallel_single_source_destinations"] for r in relevant))
            # No vacuous proof for a tensor with no reachable relation.
            if relevant and all(r["multiple_source_destinations"] == 0 for r in relevant):
                row["category"] = "b"
    row["structural_proof"] = row["category"] != "d"
    row["description"] = CATEGORIES[row["category"]]
    if row["category"] == "d":
        row["limitation"] = ("Numerically near zero at the accepted initial state; initial attention "
                             "saturation is possible but is not established by this static analysis.")
    return row


def _checked(ref):
    path = Path(ref["path"])
    if sha256(path) != ref["sha256"]:
        raise ValueError("Frozen evidence SHA mismatch: " + str(path))
    return path


def _static_topology(report):
    """Rebuild only edge/node topology with frozen row numbering and profile."""
    plan_path = _checked(report["archived_plan"])
    seal = read_json(plan_path.with_name("plan.seal.json"))
    if seal["plan_sha256"] != sha256(plan_path):
        raise ValueError("Archived plan seal mismatch")
    plan = read_json(plan_path)
    prepared_ref = plan["tasks"][report["task_id"]]["prepared"]["0/1"]
    prepared = read_json(_checked(prepared_ref))
    if digest(prepared["split"]) != report["split_sha256"]:
        raise ValueError("Frozen split identity mismatch")
    entry = prepared["profiles"][report["profile"]]
    if entry["graph"] != report["graph"] or entry["initial"] != report["initial"]:
        raise ValueError("Graph/initial identity mismatch")
    source = read_graph(_checked(report["graph"]))
    original_ids = list(source)
    identity = report["identity"]["source_input"]
    if digest(original_ids) != identity["original_node_ids_sha256"]:
        raise ValueError("Original node ordering mismatch")
    # Features and labels are not used. Copy only topology attributes.
    graph = nx.MultiDiGraph()
    ids = {node: i for i, node in enumerate(original_ids)}
    for node, attrs in source.nodes(data=True):
        graph.add_node(ids[node], node_type=attrs["node_type"], source_file=attrs["source_file"])
    for a, b, key, attrs in source.edges(keys=True, data=True):
        graph.add_edge(ids[a], ids[b], key=key, edge_type=attrs["edge_type"])
    del source
    gu.add_hetero_ids(graph)
    types = sorted({d["node_type"] for _, d in graph.nodes(data=True)})
    if {t: i for i, t in enumerate(types)} != identity["node_dictionary"]:
        raise ValueError("Node dictionary mismatch")
    if digest(gu.get_node_ids_dict(graph)) != identity["node_ids_sha256"]:
        raise ValueError("Type-local node order mismatch")
    data = materialize(edge_data(graph), report["profile"])
    if {"|".join(c): i for i, c in enumerate(sorted(data))} != identity["relation_dictionary"]:
        raise ValueError("Canonical dictionary mismatch")
    encoded = {}
    for i, canonical in enumerate(sorted(data)):
        for role, value in zip(("source", "target"), data[canonical]):
            encoded["|".join(canonical)+":"+role] = value
        encoded["|".join(canonical)+":data:id"] = torch.full(
            (len(data[canonical][0]),), i, dtype=torch.long)
    if tensor_digest(encoded) != identity["dgl_edges_sha256"]:
        raise ValueError("Materialized edge identity mismatch")
    train_files = set(prepared["split"]["inner_train_files"])
    supervised = {t: set() for t in types}
    for _, attrs in graph.nodes(data=True):
        if attrs["source_file"] in train_files and attrs["node_type"] not in AUX_NODE_TYPES:
            supervised[attrs["node_type"]].add(attrs["node_hetero_id"])
    edges = {c: list(zip(a.tolist(), b.tolist())) for c, (a, b) in data.items()}
    result = topology_support(types, edges, supervised, report["config"]["layers"])
    old = report["support"]
    if result["input_nodes_reaching_train"] != old["input_nodes_reaching_train"]:
        raise ValueError("Training input reachability differs from accepted static evidence")
    if types != old["node_type_names_by_index"]:
        raise ValueError("Parameter node type ordering differs")
    for i, row in enumerate(result["layers"]):
        if row["output_nodes_reaching_train"] != old["output_nodes_reaching_train_by_layer"][i]:
            raise ValueError("Training output reachability differs")
        expected = {tuple(r["canonical"]): r for r in old["canonical_training_path_support"][i]}
        for relation in row["relations"]:
            previous = expected[tuple(relation["canonical"])]
            for field in ("reachable_edges", "reachable_destinations_with_multiple_edges"):
                if relation[field] != previous[field]:
                    raise ValueError("Training canonical support differs")
    return result, prepared_ref


def classify_report(static_path, output):
    static_path, output = Path(static_path).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    report = read_json(static_path)
    comparison = report["gradient_comparison"]
    if report["status"] != "passed" or not comparison["passed"]:
        raise ValueError("Only accepted static evidence may be described")
    names = comparison["zero_tensors"]
    if len(names) != len(set(names)) or set(names) != set(comparison["candidate_zero_tensors"]):
        raise ValueError("Accepted near-zero tensor identities differ")
    topology, prepared_ref = _static_topology(report)
    rows = [classify_parameter(name, topology, report["profile"]) for name in names]
    result = dict(schema="prompt7b3-static-zero-description-v1", task_id=report["task_id"],
        profile=report["profile"], reducer=report["reducer"],
        static=dict(path=str(static_path), sha256=sha256(static_path)),
        graph=report["graph"], prepared=prepared_ref,
        implementation=dict(path=str(Path(__file__).resolve()), sha256=sha256(__file__)),
        classification_scope="Only topology and parameter names; descriptive, not a gate or new gradient evidence",
        model_constructions=0, forward_calls=0, backward_calls=0, optimizer_steps=0,
        numerical_threshold=comparison["absolute_term"],
        categories=CATEGORIES, counts=dict(Counter(row["category"] for row in rows)),
        parameter_count=len(rows), parameters=rows,
        topology=topology,
        old_dynamic_evidence="Prompt 7b.2 dynamic audits are retained unchanged; not rerun or used for categories")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = classify_report(args.static, args.output)
    print(json.dumps({k: result[k] for k in ("task_id", "profile", "reducer", "parameter_count", "counts")}, sort_keys=True))


if __name__ == "__main__":
    main()
