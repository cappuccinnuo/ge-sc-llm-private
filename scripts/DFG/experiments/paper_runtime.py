"""Full fixed-task-graph execution; registration is not training support."""
import copy
from collections import Counter
import networkx as nx
import torch
import sco_models.graph_utils as gu
from .common import digest
from .runtime import assert_disconnected_files
from .paper_protocol import SCHEMA_POLICY, FORWARD_SCOPE

DDG = "DATA_DEF_USE"


def graph_schema_and_support(graph, split):
    """Use the production reflection rule, without constructing/training weights."""
    assert_disconnected_files(graph)
    train, val = set(split["train_files"]), set(split["val_files"])
    files = {d["source_file"] for _, d in graph.nodes(data=True)}
    if not train or not val or train & val or train | val != files:
        raise ValueError("Invalid train/val file partition")
    if len(train) != len(split["train_files"]) or len(val) != len(split["val_files"]):
        raise ValueError("Duplicate split files")
    # gu.add_hetero_ids mutates attrs; never change the frozen graph.
    g = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(graph)))
    ids = gu.get_node_ids_dict(g)
    data = gu.reflect_graph(gu.generate_hetero_graph_data(g))
    node_types, relations = sorted(ids), sorted(data)
    schema = {"node_types": [{"name": t, "index": i} for i, t in enumerate(node_types)],
              "canonical_relations": [{"canonical": list(c), "index": i}
                                      for i, c in enumerate(relations)]}
    schema["sha256"] = digest(schema)
    nodes, edges = [], []
    for t in node_types:
        counts = Counter("train" if g.nodes[n]["source_file"] in train else "val" for n in ids[t])
        nodes.append({"name": t, "train_nodes": counts["train"], "val_nodes": counts["val"]})
    for c in relations:
        source, target = data[c]
        counts = Counter()
        for s, t in zip(source.tolist(), target.tolist()):
            sf, tf = g.nodes[ids[c[0]][s]]["source_file"], g.nodes[ids[c[2]][t]]["source_file"]
            if sf != tf:
                raise ValueError("Reflected cross-file edge")
            counts["train" if sf in train else "val"] += 1
        edges.append({"canonical": list(c), "train_edges": counts["train"], "val_edges": counts["val"]})
    return {"policy": SCHEMA_POLICY, "forward_scope": FORWARD_SCOPE, "schema": schema,
            "supported": True, "files": {"train": len(train), "val": len(val)},
            "nodes": nodes, "relations": edges,
            "registered_without_train_nodes": [r["name"] for r in nodes if not r["train_nodes"]],
            "registered_without_train_relations": [r["canonical"] for r in edges if not r["train_edges"]],
            "ddg_training_edges": sum(r["train_edges"] for r in edges if r["canonical"][1] == DDG),
            "no_samples_or_edges_removed": True}


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


class Supervision:
    """Only row/file supervision changes. The model graph is never swapped."""
    def __init__(self, model, task, files):
        self.task, self.files = task, sorted(files)
        selected = set(self.files)
        if len(selected) != len(self.files):
            raise ValueError("Duplicate supervised files")
        population = {d["source_file"] for _, d in model.nx_graph.nodes(data=True)}
        if not selected or not selected <= population:
            raise ValueError("Absent/empty supervised files")
        self.full_ids = [n for n, d in model.nx_graph.nodes(data=True) if d["source_file"] in selected]
        self.mask = torch.tensor([d["source_file"] in selected for _, d in model.nx_graph.nodes(data=True)],
                                 dtype=torch.bool, device=model.device)
        self.manifest = {"task": task, "files": self.files, "model_node_ids": self.full_ids,
                         "forward_scope": FORWARD_SCOPE,
                         "supervision": "node_mask" if task == "node" else "file_batch"}
        self.manifest["sha256"] = digest(self.manifest)

    def targets(self, model, graph_labels):
        values = [model.node_labels[n] for n in self.full_ids] if self.task == "node" else [graph_labels[f] for f in self.files]
        return torch.tensor(values, dtype=torch.long, device=model.device)

    def forward(self, model):
        validate_registration(model, deep=False)
        return model()[self.mask] if self.task == "node" else model(self.files)[0]


def gradient_audit(model, support):
    backbone = [(n, p) for n, p in model.named_parameters() if not n.startswith("classify.")]
    if not any(p.grad is not None for n, p in backbone):
        raise AssertionError("Integration error: HGT backbone disconnected from supervised loss")
    result = {"backbone_gradient_l1": sum(float(p.grad.abs().sum()) for n, p in backbone if p.grad is not None),
              "classifier_gradient_l1": sum(float(p.grad.abs().sum()) for n, p in model.named_parameters()
                                           if n.startswith("classify.") and p.grad is not None),
              "ddg_relations": []}
    for row in support["relations"]:
        c = tuple(row["canonical"])
        if c[1] != DDG:
            continue
        idx = model.etypes_dict[c]
        grad = sum(float(layer.relation_msg.grad[idx].abs().sum()) for layer in model.gcs
                   if layer.relation_msg.grad is not None)
        connected = any(layer.relation_msg.grad is not None for layer in model.gcs)
        if row["train_edges"] and not connected:
            raise AssertionError("Integration error: registered supported DDG bank disconnected")
        if not row["train_edges"] and grad != 0:
            raise AssertionError("Unexpected supervised gradient on validation-only DDG relation")
        status = ("no_training_ddg_support" if not row["train_edges"] else
                  "training_support_nonzero_gradient" if grad > 0 else "training_support_zero_gradient_observed")
        result["ddg_relations"].append(dict(row, message_gradient_l1=grad, status=status))
    result["ddg_training_support"] = support["ddg_training_edges"]
    result["note"] = ("Zero with no train instances is allowed, not an integration error. "
                      "Zero observed with support remains explicit diagnostic, not proof of disconnection. "
                      "Weight decay updates are separate from supervised gradients.")
    return result
