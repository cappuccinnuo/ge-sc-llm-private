"""Read sealed N-A carriers without rerunning feature production.
Model adapter allocation copied from scripts/node_sem/model.py
SHA256: 4532126aa3406ca349ac5028c10187be0bd3009ade004cd9768d4dce802bb369
Only the carrier source/duplicate validation changes. Frozen make_model,
adapter allocation order and forward remain unchanged; 32-group and CPU
equivalence gates are mandatory before formal execution.
"""
import copy
import hashlib
import numpy as np
import torch
from torch import nn
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.model import make_model
from .feature_spec import FeatureSpec
from .carrier import row_key
from .model import _vocabulary, _validate_token_rows
from .adapter import NodeSemAdapter


def load_carrier(job):
    spec = FeatureSpec.from_json(read(checked(job["spec"])))
    if spec.digest() != job["spec_sha256"]:
        raise ValueError("Spec digest differs")
    record = read(checked(job["feature_view"]))
    if record.get("data") != job["feature_npz"]:
        raise ValueError("Carrier data reference differs")
    if (record["task_id"] != job["task_id"] or record["view"] != "original"
            or record["spec_sha256"] != spec.digest() or record["spec"] != spec.to_json()):
        raise ValueError("Carrier semantic identity differs")
    graph = read_graph(checked(job["graph"]))
    fingerprint = graph_fingerprint(graph)
    if fingerprint != record["original_graph_fingerprint"] or fingerprint != job["original_graph_fingerprint"]:
        raise ValueError("Original graph fingerprint differs")
    with np.load(str(checked(job["feature_npz"])), allow_pickle=False) as arrays:
        if arrays.files != ["features"]:
            raise ValueError("Carrier array dictionary differs")
        matrix = arrays["features"]
    if (matrix.dtype != np.float32 or list(matrix.shape) != record["feature_shape"]
            or matrix.shape != (len(graph), spec.carrier_dim())
            or not np.isfinite(matrix).all() or len(record["rows"]) != len(graph)):
        raise ValueError("Invalid carrier matrix")
    for (nid, attrs), row in zip(graph.nodes(data=True), record["rows"]):
        if (type(nid) is not type(row["original_graph_node_id"]) or nid != row["original_graph_node_id"]
                or row_key(nid, attrs) != row["row_key"] or attrs["source_file"] != row["file"]
                or attrs["node_type"] != row["node_type"]):
            raise ValueError("Carrier row identity/order differs")
    carried = copy.deepcopy(graph)
    for index, nid in enumerate(carried):
        carried.nodes[nid]["token"] = matrix[index]
    record = {k: v for k, v in record.items() if k != "data"}
    return carried, record, spec


def construct_carried(job, carried, record, spec):
    cfg = job["config"]
    layers = cfg["layers"] if spec.layers is None else spec.layers
    if job["profile"] not in ("G0", "G3R") or (layers == 0 and job["profile"] != "G0"):
        raise ValueError("Unsupported profile/layers")
    model = make_model(job["granularity"], carried, job["profile"], "cpu",
        node_feature="inside_token", hidden_size=cfg["hidden_size"],
        layers=layers, heads=cfg["heads"], reducer=cfg.get("reducer", "mean"),
        layer_impl=cfg["layer_impl"])
    if spec.token_mode != "raw_linear":
        shared = None
        if spec.token_mode == "embed_pool":
            vocabulary, provenance = _vocabulary(record)
            _validate_token_rows(carried, vocabulary, spec)
            bag = nn.EmbeddingBag(vocabulary, 64, mode="mean")
            with torch.no_grad():
                bag.weight[0].zero_()
            model.nodesem_shared = nn.ModuleDict({
                "token_bag": bag, "token_norm": nn.LayerNorm(64)})
            shared = model.nodesem_shared
            model.nodesem_tokenizer = provenance
            model.nodesem_vocabulary = vocabulary
        model.adapt_ws = nn.ModuleList([
            NodeSemAdapter(spec, ntype, shared=shared, hidden_size=cfg["hidden_size"])
            for ntype, idx in sorted(model.ntypes_dict.items(), key=lambda item: item[1])])
        model.to("cpu")
    model.nodesem_spec = spec.to_json()
    model.nodesem_spec_sha256 = spec.digest()
    model.nodesem_carrier_record = record
    model.nodesem_task_id = job["task_id"]
    if (model.original_graph_node_ids != [r["original_graph_node_id"] for r in record["rows"]]
            or model.in_size != spec.carrier_dim()
            or sum(p.numel() for p in model.parameters()) != job["parameters"]):
        raise ValueError("Constructed model identity/dimension/parameter count differs")
    return model
