"""Strict feature carrier assembly; frozen graph and feature inputs stay intact.

S0/S1 always use the unchanged 8G spelling_features.assemble integrity gate.
No label, prediction, method, or vulnerability field becomes a feature.
"""
import copy
import hashlib
import json
from pathlib import Path

import networkx as nx
import numpy as np

from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2 import AUX_NODE_TYPES
from scripts.DFG.dfg_v2.env import ENV_KEYS
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref
from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import (
    assemble, VERSION as SPELLING_VERSION,
)
from . import TOKEN_IDS
from .feature_spec import FeatureSpec

VERSION = "nodesem-carrier-v1"
MODALITY_VERSION = "nodesem-modality-v1"


def _sha_text(value):
    if not isinstance(value, str):
        raise ValueError("Feature code must be a string")
    return hashlib.sha256(value.encode("utf8")).hexdigest()


def vector_sha(value):
    value = np.asarray(value)
    if value.dtype != np.float32 or value.ndim != 1 or not np.isfinite(value).all():
        raise ValueError("Expected finite one-dimensional float32 carrier")
    return hashlib.sha256(value.tobytes(order="C")).hexdigest()


def row_key(node_id, attrs):
    if attrs["node_type"] in AUX_NODE_TYPES:
        key = attrs["code"]
        if attrs["node_type"] != "env_source" or key not in ENV_KEYS:
            raise ValueError("Unknown auxiliary node feature identity")
        return "env:{}:{}".format(attrs["source_file"], key)
    if isinstance(node_id, bool) or not isinstance(node_id, (int, str)):
        raise ValueError("Only integer/string original graph IDs are supported")
    return node_id


def _rows(view):
    return [r.get("row_key", r.get("original_graph_node_id")) for r in view["rows"]]


def _load(manifest_ref):
    view = read(checked(manifest_ref))
    if view.get("version") not in (MODALITY_VERSION, SPELLING_VERSION):
        raise ValueError("Unknown modality version")
    if view.get("view") not in ("anonymous", "original"):
        raise ValueError("Unknown modality view")
    if not isinstance(view.get("task_id"), str) or not view["task_id"]:
        raise ValueError("Missing modality task identity")
    if view.get("feature_dtype") != "float32":
        raise ValueError("Modality dtype declaration differs")
    rows = view.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing modality rows")
    keys = _rows(view)
    if any(isinstance(key, bool) or not isinstance(key, (str, int)) for key in keys):
        raise ValueError("Invalid modality row identity")
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate modality row identity")
    shape = view.get("feature_shape")
    if (not isinstance(shape, list) or len(shape) != 2
            or shape[0] != len(rows) or isinstance(shape[1], bool)
            or not isinstance(shape[1], int) or shape[1] <= 0):
        raise ValueError("Invalid modality shape")
    with np.load(str(checked(view["data"])), allow_pickle=False) as archive:
        if set(archive.files) != {"features"}:
            raise ValueError("Unexpected modality NPZ arrays")
        values = archive["features"].copy()
    if values.dtype != np.float32 or list(values.shape) != shape:
        raise ValueError("Modality shape/dtype differs")
    if not np.isfinite(values).all():
        raise ValueError("Non-finite modality values")
    sources = view.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Missing modality source identities")
    for source in sources.values():
        checked(source)
    digest_field = (view.get("vector_sha_field") if view["version"] == SPELLING_VERSION
                    else "vector_sha256")
    if not isinstance(digest_field, str):
        raise ValueError("Missing vector digest field")
    for row, value in zip(rows, values):
        if row.get(digest_field) != vector_sha(value):
            raise ValueError("Modality vector digest differs")
        filename = row.get("file")
        if (filename not in sources
                or row.get("source_sha256") != sources[filename]["sha256"]):
            raise ValueError("Modality source identity differs")
        digest = row.get("code_sha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("Missing modality code SHA")
        if view["version"] == MODALITY_VERSION:
            present = row.get("present")
            if type(present) is not bool:
                raise ValueError("Modality row needs an explicit boolean presence")
            if not present and np.any(value != 0):
                raise ValueError("Absent modality must contain zeros")
    if view["version"] == MODALITY_VERSION:
        if not isinstance(view.get("modality"), str):
            raise ValueError("Missing modality name")
        if not view.get("implementation"):
            raise ValueError("Missing modality implementation provenance")
        for key in ("implementation", "assets"):
            if not isinstance(view.get(key), dict):
                raise ValueError("Missing modality provenance: " + key)
            for reference in view[key].values():
                checked(reference)
        checked(view["input_text"])
    return view, values


def load_modality(manifest_ref):
    """Return row-keyed copied vectors after complete artifact validation."""
    view, values = _load(manifest_ref)
    return {key: value.copy() for key, value in zip(_rows(view), values)}


def _aligned(view, graph, task_id, spec_view, dim, original_only=False):
    if view["task_id"] != task_id or view["view"] != spec_view:
        raise ValueError("Modality task/view mismatch")
    if view["version"] == MODALITY_VERSION:
        profiles = view.get("profiles", {})
        if (not isinstance(profiles, dict) or not profiles
                or graph_fingerprint(graph) not in {p["graph_fingerprint"] for p in profiles.values()}):
            raise ValueError("Modality graph fingerprint differs")
    if view["feature_shape"][1] != dim:
        raise ValueError("Modality dimension mismatch")
    nodes = [(n, a) for n, a in graph.nodes(data=True)
             if not original_only or a["node_type"] not in AUX_NODE_TYPES]
    if [row_key(n, a) for n, a in nodes] != _rows(view):
        raise ValueError("Modality row identity/order differs from graph")
    for (_, attrs), row in zip(nodes, view["rows"]):
        if (attrs["source_file"] != row["file"]
                or attrs["node_type"] != row["node_type"]
                or _sha_text(attrs["code"]) != row["code_sha256"]):
            raise ValueError("Modality row code/source/type differs")


def _anchor_gate(graph, sources):
    """Delegate structural DOT anchor reads exclusively to frozen Projector."""
    files = {attrs["source_file"] for _, attrs in graph.nodes(data=True)
             if attrs["node_type"] not in AUX_NODE_TYPES}
    if files != set(sources):
        raise ValueError("Source population differs from original HCG files")
    for filename in sorted(files):
        source = checked(sources[filename]).read_text(encoding="utf8")
        nodes = [n for n, a in graph.nodes(data=True)
                 if a["source_file"] == filename and a["node_type"] not in AUX_NODE_TYPES]
        # Source text/role/endpoints must agree with the exact saved AST anchor.
        # The frozen Projector alone reads structural DOT labels; none of their
        # text or absolute coordinates enters the carrier feature vector.
        Projector(graph.subgraph(nodes).copy(), ProjectionView(source, filename))


def carry(graph, spec, task_id):
    """Assemble a new in-memory graph; never change the caller's graph."""
    if not isinstance(spec, FeatureSpec):
        spec = FeatureSpec.from_json(spec)
    if not isinstance(graph, nx.MultiDiGraph):
        raise TypeError("Carrier requires a directed multigraph")
    keys = [row_key(n, a) for n, a in graph.nodes(data=True)]
    if len(keys) != len(set(keys)):
        raise ValueError("Graph contains duplicate feature row identities")
    before = graph_fingerprint(graph)
    result = copy.deepcopy(graph)
    layout = spec.layout()
    views, values, by_key = {}, {}, {}
    tokenizer = None
    checked_sources = None
    for modality in spec.modalities:
        name = modality["name"]
        view, matrix = _load(modality["manifest"])
        if checked_sources is None:
            _anchor_gate(graph, view["sources"])
            checked_sources = copy.deepcopy(view["sources"])
        elif view["sources"] != checked_sources:
            raise ValueError("Feature modalities bind different source identities")
        token = name == TOKEN_IDS
        if token != (view["version"] == SPELLING_VERSION):
            raise ValueError("TOKEN_IDS requires the frozen 8G spelling view")
        if not token and view["modality"] != name:
            raise ValueError("Modality name differs")
        _aligned(view, graph, task_id, spec.view, modality["dim"], original_only=token)
        if token:
            # This unchanged gate binds every original graph field, including
            # fields deliberately excluded from feature extraction.
            token_graph = assemble(graph, modality["manifest"])
            values[name] = {row_key(n, a): np.asarray(token_graph.nodes[n]["token"]).copy()
                            for n, a in graph.nodes(data=True)}
            tokenizer = copy.deepcopy(view["tokenizer"])
        else:
            values[name] = {k: v.copy() for k, v in zip(_rows(view), matrix)}
        by_key[name] = {k: row for k, row in zip(_rows(view), view["rows"])}
        views[name] = view
    rows = []
    for nid, attrs in graph.nodes(data=True):
        key = row_key(nid, attrs)
        if spec.token_mode == "raw_linear":
            vector = values[TOKEN_IDS][key].copy()
            presence = []
        else:
            vector = np.zeros(spec.carrier_dim(), dtype=np.float32)
            presence = []
            for modality in spec.modalities:
                name, dimension = modality["name"], modality["dim"]
                item = np.asarray(values[name][key])
                if item.dtype != np.float32 or item.shape != (dimension,):
                    raise ValueError("Carrier modality vector differs")
                present = (bool(np.any(item != 0)) if name == TOKEN_IDS
                           else by_key[name][key]["present"])
                part = layout[name]
                vector[part["presence"]] = float(present)
                vector[part["start"]:part["stop"]] = item
                presence.append(present)
        if vector.shape != (spec.carrier_dim(),):
            raise ValueError("Carrier width differs")
        digest = vector_sha(vector)
        result.nodes[nid]["token"] = vector
        rows.append(dict(original_graph_node_id=nid, row_key=key,
                         file=attrs["source_file"], node_type=attrs["node_type"],
                         code_sha256=_sha_text(attrs["code"]),
                         vector_sha256=digest, presence=presence))
    restored = copy.deepcopy(result)
    for nid in graph:
        restored.nodes[nid]["token"] = copy.deepcopy(graph.nodes[nid]["token"])
    if graph_fingerprint(restored) != before or graph_fingerprint(graph) != before:
        raise AssertionError("Carrier changed non-token attributes or original graph")
    record = dict(version=VERSION, task_id=task_id, view=spec.view,
                  spec=spec.to_json(), spec_sha256=spec.digest(),
                  rows=rows, feature_shape=[len(graph), spec.carrier_dim()],
                  feature_dtype="float32", original_graph_fingerprint=before,
                  carrier_graph_fingerprint=graph_fingerprint(result),
                  modalities={m["name"]: copy.deepcopy(m["manifest"]) for m in spec.modalities},
                  original_inputs_unchanged=True, tokenizer=tokenizer)
    return result, record


def write_carrier(spec, task_id, graph, out_dir):
    """Exclusively create a SHA-bound NPZ and manifest in graph node order."""
    carried, record = carry(graph, spec, task_id)
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=False)
    data = directory / "carrier.npz"
    with data.open("xb") as stream:
        np.savez_compressed(stream, features=np.stack(
            [attrs["token"] for _, attrs in carried.nodes(data=True)]))
    record["data"] = ref(data)
    manifest = directory / "carrier_manifest.json"
    with manifest.open("x", encoding="utf8") as stream:
        json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return dict(manifest=ref(manifest), data=ref(data), record=record)
