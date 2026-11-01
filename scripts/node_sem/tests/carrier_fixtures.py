"""Disposable real-parser fixtures for NodeSem carrier/model tests."""
import copy
import hashlib
import json
from pathlib import Path
import networkx as nx
import numpy as np
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
from scripts.DFG.dfg_v2 import DATA_DEF_USE, ENV_FLOW
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import VERSION as SPELLING_VERSION
from scripts.node_sem import TOKEN_IDS
from scripts.node_sem.carrier import vector_sha
from scripts.node_sem.feature_spec import FeatureSpec

SOURCE = "pragma solidity ^0.4.24;\ncontract Fixture {\n uint state;\n function run(uint value) public {\n  uint x = value;\n  state = x;\n }\n}\n"


def dump(path, payload):
    Path(path).write_text(json.dumps(payload, sort_keys=True), encoding="utf8")
    return ref(path)


def make_spelling_fixture(tmp_path, enhanced=False):
    graph = nx.MultiDiGraph()
    sources = {}
    for fileindex, filename in enumerate(("train.sol", "val.sol", "test.sol")):
        source_path = Path(tmp_path) / filename
        source_path.write_text(SOURCE, encoding="utf8")
        sources[filename] = ref(source_path)
        part = nx.MultiDiGraph(generate_cfg_from_source(SOURCE, filename))
        part = nx.relabel_nodes(part, {n: "{}:{}".format(filename, n) for n in part})
        for index, (_, attrs) in enumerate(part.nodes(data=True)):
            token = np.zeros(512, dtype=np.float32)
            token[:3] = [1, 2 + index % 7, 2]
            attrs["token"] = token
            attrs["node_info_vulnerabilities"] = (
                [{"category": "synthetic", "lines": [1]}] if index % 3 == 1 else None)
        graph.add_nodes_from(part.nodes(data=True))
        graph.add_edges_from(part.edges(keys=True, data=True))
        if enhanced:
            ids = list(part)
            graph.add_edge(ids[-2], ids[-1], edge_type=DATA_DEF_USE)
            env = "env-{}".format(fileindex)
            token = np.zeros(512, dtype=np.float32)
            token[:2] = [1, 2]
            graph.add_node(env, node_type="env_source", source_file=filename,
                           code="msg.sender", token=token)
            graph.add_edge(env, ids[-1], edge_type=ENV_FLOW)
    rows, vectors = [], []
    for nid, attrs in graph.nodes(data=True):
        if attrs["node_type"] == "env_source":
            continue
        token = attrs["token"].copy()
        token[token > 0] += 1
        rows.append(dict(original_graph_node_id=nid, file=attrs["source_file"],
                         node_type=attrs["node_type"],
                         source_sha256=sources[attrs["source_file"]]["sha256"],
                         code_sha256=hashlib.sha256(attrs["code"].encode("utf8")).hexdigest(),
                         rewritten_code_sha256=hashlib.sha256(attrs["code"].encode("utf8")).hexdigest(),
                         original_vector_sha256=vector_sha(attrs["token"]),
                         anonymous_vector_sha256=vector_sha(token)))
        vectors.append(token)
    data = Path(tmp_path) / "anonymous.npz"
    np.savez_compressed(str(data), features=np.stack(vectors))
    view = dict(version=SPELLING_VERSION, view="anonymous", task_id="fixture_node",
                rows=rows, profiles={"G3R" if enhanced else "G0":
                      {"graph_fingerprint": graph_fingerprint(graph)}},
                sources=sources, data=ref(data), feature_shape=[len(rows), 512],
                feature_dtype="float32", vector_sha_field="anonymous_vector_sha256",
                tokenizer={"fixture_only": True})
    manifest = Path(tmp_path) / "anonymous_manifest.json"
    view_ref = dump(manifest, view)
    return dict(graph=graph, view=view, view_ref=view_ref, task_id="fixture_node",
                manifest=manifest, data=data, sources=sources)


def token_spec(fixture, name="S0", layers=None):
    return FeatureSpec(
        name=name, view="anonymous",
        modalities=[dict(name=TOKEN_IDS, dim=512, manifest=fixture["view_ref"], normalize=False)],
        token_mode="raw_linear" if name == "S0" else "embed_pool",
        fusion="raw_linear" if name == "S0" else "concat",
        modality_dropout=0.0, layers=layers)


class FixtureTokenEncoder:
    """Own-module dependency test double; never installed into frozen modules."""
    class Tokenizer:
        pad_token_id = 0
        def __len__(self):
            return 32

    def __init__(self, feature):
        if feature != {"fixture_only": True}:
            raise ValueError("Expected disposable fixture provenance")
        self._tokenizer = self.Tokenizer()
        self.provenance = copy.deepcopy(feature)
