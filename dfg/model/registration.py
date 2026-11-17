"""Checks that a model's parameter banks match the registered graph schema."""
import mando.models.graph_utils as gu
import torch

from dfg.utils import digest


# ----------------------------------------------------------------------
# experiments/runtime (picked: assert_disconnected_files)
def assert_disconnected_files(graph):
    bad = [(s, t) for s, t in graph.edges()
           if graph.nodes[s]["source_file"] != graph.nodes[t]["source_file"]]
    if bad:
        raise ValueError("Cross-file edges: refusing split leakage; examples=" + repr(bad[:5]))


# ----------------------------------------------------------------------
# experiments/paper_runtime (picked: validate_registration)
def validate_registration(model, expected_schema=None, deep=True):
    """Reject unregistered/misindexed schema; never create or borrow parameters."""
    graph = model.symmetrical_global_graph
    nd = {t: i for i, t in enumerate(graph.ntypes)}
    ed = {c: i for i, c in enumerate(graph.canonical_etypes)}
    if model.ntypes_dict != nd or model.etypes_dict != ed:
        raise ValueError("Unregistered or misaligned model dictionary")
    schema = {"node_types": [{"name": t, "index": i} for t, i in nd.items()],
              "canonical_relations": [{"canonical": list(c), "index": i} for c, i in ed.items()]}
    schema["sha256"] = digest(schema)
    if expected_schema is not None and schema != expected_schema:
        raise ValueError("Registered schema differs from frozen task graph")
    if len(model.adapt_ws) != len(nd):
        raise ValueError("Node parameter bank does not match registration")
    for layer in model.gcs:
        if layer.node_dict != nd or layer.edge_dict != ed:
            raise ValueError("HGT layer dictionary misaligned")
        if any(getattr(layer, n).shape[0] != len(ed) for n in ("relation_pri", "relation_att", "relation_msg")):
            raise ValueError("Relation parameter bank does not match registration")
        if any(len(getattr(layer, n)) != len(nd) for n in ("k_linears", "q_linears", "v_linears", "a_linears")):
            raise ValueError("HGT node parameter bank does not match registration")
    for c, idx in ed.items():
        if not torch.all(graph.edges[c].data["id"] == idx):
            raise ValueError("DGL relation ID dictionary misaligned")
    if deep:
        assert_disconnected_files(model.nx_graph)
        expected_ids = gu.get_node_ids_dict(model.nx_graph)
        if model.node_ids_dict != expected_ids:
            raise ValueError("Node row dictionary misaligned")
        if hasattr(model, "node_ids_by_filename") and model.node_ids_by_filename != gu.get_node_ids_by_filename(model.nx_graph):
            raise ValueError("File row dictionary misaligned")
        data = gu.reflect_graph(gu.generate_hetero_graph_data(model.nx_graph))
        if set(data) != set(ed) or set(expected_ids) != set(nd):
            raise ValueError("Graph/schema mismatch")
        for typ, rows in expected_ids.items():
            if len(rows) != graph.num_nodes(typ):
                raise ValueError("Graph node count mismatch")
        for c, endpoints in data.items():
            if not all(torch.equal(x.cpu(), y.cpu()) for x, y in zip(endpoints, graph.edges(etype=c, order="eid"))):
                raise ValueError("Graph endpoints mismatch")
    return schema
