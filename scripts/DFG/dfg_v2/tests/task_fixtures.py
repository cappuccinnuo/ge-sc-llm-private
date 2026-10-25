"""Synthetic task bundles for interface tests; not an experimental dataset.

Twenty identities satisfy the unchanged 5/10-fold protocol. The graph generator
is reused only to supply tiny source anchors; all tokens below are synthetic.
No compiler validation or actual tokenizer equivalence is claimed.
"""
import copy
from pathlib import Path

import networkx as nx
import numpy as np

from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import sha256, write_json
from scripts.DFG.experiments.protocol import make_fold_document
from scripts.DFG.experiments.prepare import TOKENIZER, REVISION
from scripts.labeling_v2.safe_graph import write_graph
from scripts.DFG.dfg_v2.tokens import RECIPE
from scripts.DFG.dfg_v2.tests.test_l1 import graph_for

SOURCE = """pragma solidity ^0.5.0;
contract C {
 address owner;
 uint value;
 function f(uint x) public returns (uint) {
  require(msg.sender == owner);
  uint y = x;
  value = y;
  return y;
 }
}
"""


class SyntheticEncoder:
    provenance = {"kind": "synthetic deterministic fixture; not real tokenizer features"}
    def __init__(self, feature=None):
        self.feature = feature
    def __call__(self, code):
        out = np.zeros(512, dtype=np.float32)
        values = list(code.encode("utf8"))[:512]
        out[:len(values)] = values
        return out
    def verify_assets(self):
        return True


def reference(path):
    return {"path": str(Path(path).resolve()), "sha256": sha256(path)}


def synthetic_registry(tmp_path, category="synthetic"):
    """Return a temporary category registry with 20 contract / 10 node files."""
    directory = Path(tmp_path) / category
    directory.mkdir(parents=True)
    sources_dir = directory / "source"
    sources_dir.mkdir()
    encoder = SyntheticEncoder()
    graph = nx.MultiDiGraph()
    sources, labels = {}, []
    prototype = graph_for(SOURCE)
    for index in range(20):
        name = "case_%02d.sol" % index
        source_path = sources_dir / name
        source_path.write_bytes(SOURCE.encode("utf8"))
        sources[name] = dict(reference(source_path), metadata=None)
        label = int(index >= 10)
        labels.append({"contract_name": name, "targets": label})
        local = copy.deepcopy(prototype)
        for rank, (_, attrs) in enumerate(local.nodes(data=True)):
            attrs["source_file"] = name
            attrs["token"] = encoder(attrs["code"])
            attrs["node_info_vulnerabilities"] = (
                [{"lines": [1], "category": category}] if label and rank % 2 else None)
        graph = nx.disjoint_union(graph, local)
    labels_path = directory / "graph_labels.json"
    write_json(labels_path, labels)
    prepared_path = directory / "prepared.json"
    write_json(prepared_path, {"category": category, "cohort": category + "_fixture"})
    asset = directory / "synthetic_asset.json"
    write_json(asset, {"kind": "synthetic fixture tokenizer asset"})
    feature = dict(RECIPE, model=TOKENIZER, revision=REVISION,
        tokenizer_class="RobertaTokenizerFast",
        feature_generation="synthetic deterministic test values; not author/codet5 features",
        asset_hashes={str(asset): sha256(asset)})
    records = {}
    for task in ("contract", "node"):
        td = directory / task
        td.mkdir()
        selected = {r["contract_name"]: r["targets"] for r in labels if task == "contract" or r["targets"] == 1}
        task_graph = graph.subgraph([n for n,d in graph.nodes(data=True) if d["source_file"] in selected]).copy()
        graph_path = td / "original.gpickle"
        write_graph(task_graph, graph_path)
        graph_ref = dict(reference(graph_path), fingerprint=fingerprint(task_graph),
                         nodes=len(task_graph), edges=task_graph.number_of_edges())
        source_path = td / "sources.json"
        write_json(source_path, {"sources": {f: sources[f] for f in sorted(selected)}})
        folds_path = td / "folds.json"
        write_json(folds_path, make_fold_document(selected, task, sha256(prepared_path), seed=1, inner_fraction=.2))
        source_task_id = category + "_fixture_" + task
        task_path = td / "task.json"
        write_json(task_path, dict(task_id=source_task_id, task=task, cohort=category+"_fixture",
            graphs={"HCG": graph_ref}, feature=feature, label_version="synthetic_only",
            labels_path=str(labels_path), labels_sha256=sha256(labels_path),
            source_prepared_manifest=str(prepared_path), source_prepared_manifest_sha256=sha256(prepared_path)))
        records[task] = dict(source_task_id=source_task_id,
            source_task_manifest=reference(task_path),
            source_metadata_manifest=reference(source_path),
            prepared_manifest=reference(prepared_path),
            labels=reference(labels_path), folds=reference(folds_path))
    return {category: {"category": category, "tasks": records}}
