"""NodeSem composition around the unchanged fixed-graph DFG v2 model.

Only adapt_ws is replaced; HGT, supervision, forward, labels and graph edges
retain their frozen implementations. Initial states are loaded by the caller.
"""
import copy
from pathlib import Path

import networkx as nx
import numpy as np
import torch
from torch import nn

from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.model import make_model, validate_registration
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read
from scripts.DFG.dfg_v2.tokens import TokenEncoder

from . import TOKEN_IDS
from .adapter import NodeSemAdapter
from .carrier import carry, vector_sha
from .feature_spec import FeatureSpec


def _task_id(spec):
    identities = {read(checked(m["manifest"]))["task_id"] for m in spec.modalities}
    if len(identities) != 1:
        raise ValueError("Feature modalities have different task identities")
    return identities.pop()


def _vocabulary(record):
    feature = record.get("tokenizer")
    if not isinstance(feature, dict):
        raise ValueError("Missing frozen tokenizer provenance")
    encoder = TokenEncoder(feature)
    # TokenEncoder deliberately exposes no vocabulary accessor. Its verified
    # local tokenizer includes added tokens through __len__, unlike vocab_size.
    vocabulary = len(encoder._tokenizer)
    if not isinstance(vocabulary, int) or vocabulary <= 1:
        raise ValueError("Invalid verified tokenizer vocabulary")
    if encoder._tokenizer.pad_token_id != 0:
        raise ValueError("Frozen tokenizer padding must be zero")
    return vocabulary, encoder.provenance


def _validate_token_rows(graph, vocabulary):
    for _, attrs in graph.nodes(data=True):
        # One presence bit precedes the only supported S1 modality.
        tokens = attrs["token"][1:]
        if (not np.isfinite(tokens).all() or np.any(tokens < 0)
                or np.any(tokens != np.floor(tokens)) or np.any(tokens >= vocabulary)):
            raise ValueError("Token IDs are not exact vocabulary indices")
        nonzero = tokens != 0
        if np.any(nonzero[1:] & ~nonzero[:-1]):
            raise ValueError("Token padding must be a continuous right suffix")


def make_nodesem_model(task, graph_ref, profile, spec, config, device="cpu", task_id=None):
    """Construct fresh parameters; execution/init owns checked initial loading."""
    if not isinstance(spec, FeatureSpec):
        spec = FeatureSpec.from_json(spec)
    if profile not in ("G0", "G3R"):
        raise ValueError("NodeSem v1 supports only frozen G0/G3R profiles")
    layers = config["layers"] if spec.layers is None else spec.layers
    if layers == 0 and profile != "G0":
        raise ValueError("Zero-layer ablation is supported only on G0")
    if task_id is None:
        task_id = _task_id(spec)
    if isinstance(graph_ref, nx.MultiDiGraph):
        graph = graph_ref
    elif isinstance(graph_ref, dict):
        graph = read_graph(checked(graph_ref))
    else:
        raise TypeError("Model input must be a SHA-bound graph reference or an in-memory graph")
    carried, record = carry(graph, spec, task_id)
    model = make_model(task, carried, profile, device, node_feature="inside_token",
                       hidden_size=config["hidden_size"], layers=layers, heads=config["heads"],
                       reducer=config.get("reducer", "mean"),
                       layer_impl=config["layer_impl"])
    if spec.token_mode != "raw_linear":
        if spec.token_mode != "embed_pool" or len(spec.modalities) != 1:
            raise NotImplementedError("Continuous/multimodal fusion is reserved for NS-P4")
        vocabulary, provenance = _vocabulary(record)
        _validate_token_rows(carried, vocabulary)
        bag = nn.EmbeddingBag(vocabulary, 64, mode="mean")
        with torch.no_grad():
            bag.weight[0].zero_()
        model.nodesem_shared = nn.ModuleDict({
            "token_bag": bag, "token_norm": nn.LayerNorm(64),
        })
        model.adapt_ws = nn.ModuleList([
            NodeSemAdapter(spec, node_type, shared=model.nodesem_shared,
                           hidden_size=config["hidden_size"])
            for node_type, index in sorted(model.ntypes_dict.items(), key=lambda item: item[1])
        ])
        model.nodesem_tokenizer = provenance
        model.nodesem_vocabulary = vocabulary
        model.to(device)
    model.nodesem_spec = spec.to_json()
    model.nodesem_spec_sha256 = spec.digest()
    model.nodesem_carrier_record = copy.deepcopy(record)
    model.nodesem_task_id = task_id
    validate(model, spec)
    return model


def validate(model, spec):
    if not isinstance(spec, FeatureSpec):
        spec = FeatureSpec.from_json(spec)
    if model.nodesem_spec_sha256 != spec.digest() or model.nodesem_spec != spec.to_json():
        raise ValueError("NodeSem model/spec binding differs")
    if len(model.gcs) != model.num_layers or (spec.layers is not None and model.num_layers != spec.layers):
        raise ValueError("NodeSem HGT layer count differs")
    if model.in_size != spec.carrier_dim():
        raise ValueError("NodeSem carrier width differs")
    if len(model.adapt_ws) != len(model.ntypes_dict):
        raise ValueError("NodeSem adapter count differs")
    record = model.nodesem_carrier_record
    if (record["spec_sha256"] != spec.digest()
            or record["feature_shape"] != [model.total_nodes, spec.carrier_dim()]):
        raise ValueError("NodeSem carrier record differs")
    if [row["original_graph_node_id"] for row in record["rows"]] != model.original_graph_node_ids:
        raise ValueError("NodeSem carrier node identity/order differs")
    for (node, attrs), row in zip(model.nx_graph.nodes(data=True), record["rows"]):
        if vector_sha(attrs["token"]) != row["vector_sha256"]:
            raise ValueError("NodeSem carrier vector digest differs")
    if spec.token_mode == "raw_linear":
        if hasattr(model, "nodesem_shared"):
            raise ValueError("S0 must not register new shared parameters")
        for adapter in model.adapt_ws:
            if (type(adapter) is not nn.Linear or adapter.in_features != 512
                    or adapter.out_features != model.hidden_size):
                raise ValueError("S0 must preserve the original Linear adapters")
    else:
        shared = getattr(model, "nodesem_shared", None)
        if not isinstance(shared, nn.ModuleDict) or set(shared) != {"token_bag", "token_norm"}:
            raise ValueError("Missing unique model-level token embedding")
        bag = shared["token_bag"]
        if (type(bag) is not nn.EmbeddingBag or bag.embedding_dim != 64
                or bag.num_embeddings != model.nodesem_vocabulary or bag.mode != "mean"
                or bag.include_last_offset or bag.max_norm is not None
                or bag.scale_grad_by_freq or bag.sparse):
            raise ValueError("Shared token embedding configuration differs")
        norm = shared["token_norm"]
        if (type(norm) is not nn.LayerNorm or norm.normalized_shape != (64,)
                or not norm.elementwise_affine or norm.eps != 1e-5):
            raise ValueError("Shared token normalization configuration differs")
        for ntype, index in model.ntypes_dict.items():
            adapter = model.adapt_ws[index]
            if (type(adapter) is not NodeSemAdapter or adapter.spec_digest != spec.digest()
                    or adapter.spec.digest() != spec.digest()
                    or adapter.ntype != ntype or adapter.hidden_size != model.hidden_size
                    or adapter.token_bag is not bag or adapter.token_norm is not norm):
                raise ValueError("NodeSem adapter semantic registration differs")
            projection = adapter.token_projection
            if (type(projection) is not nn.Linear or projection.in_features != 64
                    or projection.out_features != model.hidden_size):
                raise ValueError("NodeSem token projection differs")
        expected = {"nodesem_shared.token_bag.weight",
                    "nodesem_shared.token_norm.weight", "nodesem_shared.token_norm.bias"}
        for values in (model.state_dict(), dict(model.named_parameters())):
            keys = [key for key in values if "token_bag" in key or "token_norm" in key]
            if len(keys) != 3 or set(keys) != expected:
                raise ValueError("Shared embedding/normalization registered more than once")
    if model.num_layers == 0 and model.dfg_profile != "G0":
        raise ValueError("Zero HGT layers require G0")
    return validate_registration(model)
