"""Read-only: which graph did the authors' own line-level artefacts in the repository use?

The repository tracks node2vec embedding matrices the authors produced for the line-level
("fine-grained") and contract-level ("coarse_grained") baselines. Their row counts identify
the graph they were computed on, independently of any folder or file name:
  - CFG-only node_detection graph           -> its node count
  - fused CFG+CG graph, buggy contracts only -> a different node count
Also inspects the edge types of the per-contract .dot files tracked under <bug>/cfg/.

    python -B Test_code/author_graph_audit/check_line_level_graph_kind.py
"""
import pickle
import re
from collections import Counter
from pathlib import Path

import pickle5

REPO = Path(__file__).resolve().parents[2]
UP = REPO / "data/upstream_mando_llm"
SRC = REPO / "experiments/ge-sc-data/source_code"
BUGS = ["access_control", "arithmetic", "denial_of_service", "front_running", "reentrancy",
        "time_manipulation", "unchecked_low_level_calls"]


def load(path):
    with open(path, "rb") as handle:
        try:
            return pickle.load(handle)
        except Exception:
            handle.seek(0)
            return pickle5.load(handle)


def size(obj):
    if hasattr(obj, "shape"):
        return tuple(obj.shape)
    if isinstance(obj, dict):
        return {"dict_len": len(obj), "sample_key": repr(next(iter(obj)))[:40]}
    if hasattr(obj, "__len__"):
        return len(obj)
    return type(obj).__name__


for bug in BUGS:
    hcg = load(UP / f"graph_detection/{bug}_tree_sitter_cfg_cg_compressed_graphs.gpickle")
    buggy = {d["source_file"] for _, d in hcg.nodes(data=True)
             if d.get("node_info_vulnerabilities") not in (None, "None")}
    hcg_buggy_nodes = sum(d["source_file"] in buggy for _, d in hcg.nodes(data=True))
    cfg_path = UP / f"node_detection/{bug}_tree_sitter_cfg_compressed_graphs.gpickle"
    cfg_nodes = load(cfg_path).number_of_nodes() if cfg_path.exists() else None
    print("=" * 80)
    print(bug)
    print(f"  fused graph, all contracts          : {hcg.number_of_nodes()} nodes")
    print(f"  fused graph, buggy contracts only   : {hcg_buggy_nodes} nodes ({len(buggy)} contracts with a positive node)")
    print(f"  CFG-only node_detection graph       : {cfg_nodes} nodes")
    for name in ("node2vec_cfg_cg_compressed_graphs.pkl", "node2vec_coarse_grained_cfg_cg_compressed_graphs.pkl"):
        path = SRC / bug / "cfg_cg" / name
        if path.exists():
            print(f"  tracked {name}: {size(load(path))}")
    dots = sorted((SRC / bug / "cfg").glob("*.dot"))
    edge_types = Counter()
    node_types = Counter()
    for dot in dots:
        text = dot.read_text(errors="ignore")
        edge_types.update(re.findall(r"edge_type=\"?([a-z_]+)", text))
        node_types.update(re.findall(r"node_type=\"?([a-z_]+)", text))
    print(f"  tracked {bug}/cfg/*.dot: {len(dots)} files, edge types {dict(edge_types)}")
    decl = {k: v for k, v in node_types.items() if "declaration" in k or k in ("modifier_definition", "constructor_definition")}
    print(f"     nodes {sum(node_types.values())}, declaration-type nodes {decl}")
