"""Validate the frozen input and relation schema used by DDG checkpoints.

Codex 2026-10-12. A state_dict omits the NetworkX/DGL graph, frozen node
features and the Python type dictionaries. Call assert_model_input BEFORE
loading checkpoint parameters. These checks do not serialize model weights.
The first supported feature mode is the existing inside_token interface.
"""
import base64
import hashlib
import json
import math

import numpy as np
import torch


MANIFEST_VERSION = "ddg-model-input-v1"


def _json_value(value):
    """Encode data deterministically, including ndarray dtype and shape."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, int):
        return {"integer": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite value in model input")
        return {"float": value.hex()}
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "biuf" or not np.isfinite(value).all():
            raise ValueError("Model input arrays must be finite numeric arrays")
        contiguous = np.ascontiguousarray(value)
        return {
            "array_dtype": value.dtype.str,
            "array_shape": list(value.shape),
            "array_bytes": base64.b64encode(contiguous.tobytes()).decode("ascii"),
        }
    if isinstance(value, tuple):
        return {"tuple": [_json_value(item) for item in value]}
    if isinstance(value, list):
        return {"list": [_json_value(item) for item in value]}
    if isinstance(value, dict):
        pairs = [
            (_json_value(key), _json_value(item))
            for key, item in value.items()
        ]
        pairs.sort(key=lambda pair: json.dumps(pair[0], sort_keys=True))
        return {"dict": pairs}
    raise TypeError("Unsupported model input value: " + type(value).__name__)


def _update(hasher, tag, value):
    raw = json.dumps(
        _json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    hasher.update(tag.encode("ascii") + b"\0")
    hasher.update(str(len(raw)).encode("ascii") + b":" + raw)


def _ordered_schema(mapping, canonical=False):
    if set(mapping.values()) != set(range(len(mapping))):
        raise ValueError("Model type IDs must be unique contiguous integers")
    ordered = sorted(mapping.items(), key=lambda pair: pair[1])
    return [
        [list(key) if canonical else key, int(index)]
        for key, index in ordered
    ]


def capture_model_input(model, external_inputs=None):
    """Return JSON-safe architecture/schema metadata and an input SHA256.

    The fingerprint covers ordered NX nodes/attributes and typed edges,
    actual post-reflection DGL endpoints, frozen inp tensors and supervision
    available on the model. Graph-level diagnostic metadata is deliberately
    excluded because it is not consumed by the model.

    external_inputs can bind caller-verified contract-label/fold/source
    digests. A graph classifier does not contain its external target JSON;
    callers must supply its digest here when recording a training run.
    Device, train/eval mode and trainable parameter values are excluded.
    """
    # The original graph classifier does not retain node_feature, so verify
    # its actual per-node input against token below instead of guessing.
    if getattr(model, "node_feature", None) not in (None, "inside_token"):
        raise ValueError("DDG input validation currently requires inside_token")
    if external_inputs is None:
        external_inputs = {}
    if not isinstance(external_inputs, dict):
        raise TypeError("external_inputs must be a dict or None")
    graph = model.symmetrical_global_graph
    if set(model.ntypes_dict) != set(graph.ntypes):
        raise ValueError("Node type dictionary does not match the DGL graph")
    if set(model.etypes_dict) != set(graph.canonical_etypes):
        raise ValueError("Relation type dictionary does not match the DGL graph")
    schema = {
        "model_class": model.__class__.__module__ + "." + model.__class__.__name__,
        "node_feature": "inside_token",
        "input_size": int(model.in_size),
        "hidden_size": int(model.hidden_size),
        "output_size": int(model.out_size),
        "num_heads": int(model.num_heads),
        "num_layers": int(model.num_layers),
        "use_norm": [bool(layer.use_norm) for layer in model.gcs],
        "dropout": [float(layer.drop.p) for layer in model.gcs],
        "node_types": _ordered_schema(model.ntypes_dict),
        "edge_types": _ordered_schema(model.etypes_dict, canonical=True),
    }
    hasher = hashlib.sha256()
    for node, data in model.nx_graph.nodes(data=True):
        _update(hasher, "node", (node, data))
    for source, target, key, data in model.nx_graph.edges(keys=True, data=True):
        _update(hasher, "edge", (source, target, key, data))
    _update(hasher, "node_ids_by_type", model.node_ids_dict)

    for node_type, _ in schema["node_types"]:
        inp = graph.nodes[node_type].data["inp"]
        if inp.requires_grad:
            raise ValueError("inside_token input features must remain frozen")
        if inp.ndim != 2 or tuple(inp.shape) != (graph.num_nodes(node_type), model.in_size):
            raise ValueError("Feature matrix does not match node IDs/input size")
        input_array = inp.detach().cpu().numpy()
        for row, node_id in enumerate(model.node_ids_dict[node_type]):
            token = model.nx_graph.nodes[node_id].get("token")
            if token is None:
                raise ValueError("inside_token input is missing a node token")
            expected_row = torch.tensor(token).numpy()
            if expected_row.dtype != input_array.dtype or not np.array_equal(
                expected_row, input_array[row]
            ):
                raise ValueError("inside_token feature mismatch between NX token and DGL inp")
        _update(hasher, "input", (node_type, input_array))
    for canonical_list, _ in schema["edge_types"]:
        canonical = tuple(canonical_list)
        source, target = graph.edges(etype=canonical, order="eid")
        _update(
            hasher, "model_edges",
            (canonical, source.detach().cpu().numpy(), target.detach().cpu().numpy()),
        )
    if hasattr(model, "node_labels"):
        _update(hasher, "node_labels", model.node_labels)
    if hasattr(model, "node_ids_by_filename"):
        _update(hasher, "file_membership", model.node_ids_by_filename)
    _update(hasher, "external_inputs", external_inputs or {})
    external_digest = hashlib.sha256()
    _update(external_digest, "external_inputs", external_inputs or {})
    return {
        "manifest_version": MANIFEST_VERSION,
        "schema": schema,
        "node_count": int(graph.num_nodes()),
        "edge_count": int(graph.num_edges()),
        "input_sha256": hasher.hexdigest(),
        "external_inputs_sha256": external_digest.hexdigest(),
    }


def assert_model_input(model, expected, external_inputs=None):
    """Reject graph/feature/label/schema drift before state_dict restoration."""
    actual = capture_model_input(model, external_inputs=external_inputs)
    if expected.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("Unsupported DDG model input manifest version")
    if expected.get("schema") != actual["schema"]:
        raise ValueError("DDG checkpoint model/relationship schema mismatch")
    for key in ("node_count", "edge_count", "input_sha256", "external_inputs_sha256"):
        if expected.get(key) != actual[key]:
            raise ValueError("DDG checkpoint input fingerprint mismatch: " + key)
    return actual
