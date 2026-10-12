"""Why are the scores near 99? Break the held-out predictions down and compare with
baselines that use no graph and no neural network, on exactly the same folds.

Covers both the locally built graphs (labeling_v3 runs) and the authors' published
graphs (earlier author-graph runs). Reads best.pt per fold + selection.json; trains
nothing, writes only Test_code/benchmark_headroom/diagnosis.json.

    python -B Test_code/benchmark_headroom/diagnose.py
"""
import ast
import json
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score, precision_score, recall_score

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
V3 = REPO / "Test_code/labeling_v3"
RE = REPO / "experiments/ge-sc-data/source_code/reentrancy"
AC = REPO / "scripts/access_control_test"
UP = REPO / "data/upstream_mando_llm/graph_detection"
# Identifier suffix SolidiFI gives every snippet it injects for the bug type.
MARKER = {"reentrancy": re.compile(r"re_ent\d+"), "access_control": re.compile(r"txorigin\d+")}

# name -> bug, contract graph/run/labels, {line label variant: (graph, run)}
EXPERIMENTS = {
    "reentrancy / local graph": dict(
        bug="reentrancy",
        contract=(V3 / "artifacts/v1/reentrancy/hcg_tok_author.gpickle", V3 / "runs/v1/reentrancy/contract",
                  RE / "graph_labels.json"),
        line={"clean labels": (V3 / "artifacts/v1/reentrancy/linelevel_tok_clean.gpickle", V3 / "runs/v1/reentrancy/line_clean"),
              "author labels": (V3 / "artifacts/v1/reentrancy/linelevel_tok_author.gpickle", V3 / "runs/v1/reentrancy/line_author")}),
    "reentrancy / author graph": dict(
        bug="reentrancy",
        contract=(RE / "upstream_contractlevel_tok.gpickle", REPO / "models/contractlevel/author_hcg_contract_v1",
                  UP / "reentrancy_graph_labels.json"),
        line={"author labels": (RE / "upstream_linelevel_cfg_cg_tok.gpickle", REPO / "models/linelevel/author_hcg_line_v1")}),
    "access_control / local graph": dict(
        bug="access_control",
        contract=(V3 / "artifacts/v1/access_control/hcg_tok_author.gpickle", V3 / "runs/v1/access_control/contract",
                  AC / "artifacts/dataset_a_source_range_v1/graph_labels.json"),
        line={"clean labels": (V3 / "artifacts/v1/access_control/linelevel_tok_clean.gpickle", V3 / "runs/v1/access_control/line_clean"),
              "author labels": (V3 / "artifacts/v1/access_control/linelevel_tok_author.gpickle", V3 / "runs/v1/access_control/line_author")}),
    "access_control / author graph": dict(
        bug="access_control",
        contract=(AC / "artifacts/author_graph_v1/hcg_author_tok.gpickle", AC / "runs/author_graph_v1/contract",
                  UP / "access_control_graph_labels.json"),
        line={"author labels": (AC / "artifacts/author_graph_v1/linelevel_author_tok.gpickle", AC / "runs/author_graph_v1/line")}),
}


def positive(data):
    value = data.get("node_info_vulnerabilities")
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
    return int(isinstance(value, list))


def metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    if len(y) == 0:
        return None
    return {"n": int(len(y)), "positives": int(y.sum()),
            "buggy_f1": round(100 * f1_score(y, p, labels=[0, 1], average=None, zero_division=0)[1], 2),
            "precision": round(100 * precision_score(y, p, zero_division=0), 2),
            "recall": round(100 * recall_score(y, p, zero_division=0), 2)}


def fold_dirs(run_dir):
    return sorted(Path(run_dir).glob("*_fold*"), key=lambda d: int(d.name.rsplit("fold", 1)[1]))


def line_level(bug, graph_path, run_dir, device):
    from sco_models.model_hgt import HGTVulNodeClassifier
    graph = pickle.load(open(graph_path, "rb"))
    ids = sorted(graph.nodes())
    y = np.array([positive(graph.nodes[n]) for n in ids])
    files = [graph.nodes[n]["source_file"] for n in ids]
    codes = [(graph.nodes[n]["node_type"], graph.nodes[n].get("code") or "") for n in ids]
    solidifi = np.array([f.startswith("buggy_") for f in files])
    marker = np.array([int(bool(MARKER[bug].search(c))) for _, c in codes])

    model = HGTVulNodeClassifier(str(graph_path), feature_extractor=None, node_feature="inside_token", device=device)
    model.to(device)
    pred = np.full(len(ids), -1)
    lookup = np.full(len(ids), -1)
    seen_same_label = 0
    fold_f1 = defaultdict(list)
    for fold_dir in fold_dirs(run_dir):
        sel = json.load(open(fold_dir / "selection.json"))
        val = set(sel["val_files"])
        val_idx = np.array([i for i, f in enumerate(files) if f in val])
        train_idx = np.array([i for i, f in enumerate(files) if f not in val])
        model.load_state_dict(torch.load(fold_dir / "best.pt", map_location=device))
        model.eval()
        with torch.no_grad():
            pred[val_idx] = model()[val_idx].argmax(dim=1).cpu().numpy()
        # lookup table: exact (node type, code) -> majority training label; unseen -> training majority
        votes = defaultdict(Counter)
        for i in train_idx:
            votes[codes[i]][y[i]] += 1
        default = int(y[train_idx].mean() >= 0.5)
        for i in val_idx:
            lookup[i] = votes[codes[i]].most_common(1)[0][0] if codes[i] in votes else default
            seen_same_label += int(y[i] == 1 and codes[i] in votes and votes[codes[i]][1] > 0)
        for name, p in (("hgt", pred), ("lookup", lookup), ("marker", marker)):
            fold_f1[name].append(100 * f1_score(y[val_idx], p[val_idx], labels=[0, 1], average=None, zero_division=0)[1])
    assert (pred >= 0).all(), "a node was never held out"
    out = {"contracts": len(set(files)), "nodes": len(ids), "positives": int(y.sum()),
           "positives_in_solidifi_files_percent": round(100 * y[solidifi].sum() / y.sum(), 2),
           "distinct_code_snippets": len(set(codes)),
           "held_out_positives_seen_as_training_positive_percent": round(100 * seen_same_label / y.sum(), 2),
           "fold_mean_buggy_f1": {k: round(float(np.mean(v)), 2) for k, v in fold_f1.items()}}
    for name, p in (("hgt", pred), ("lookup", lookup), ("marker", marker)):
        out[name] = {"solidifi_files": metrics(y[solidifi], p[solidifi]),
                     "smartbugs_files": metrics(y[~solidifi], p[~solidifi])}
    return out


def contract_level(bug, graph_path, run_dir, label_path, device):
    from sco_models.model_hgt import HGTVulGraphClassifier
    graph = pickle.load(open(graph_path, "rb"))
    targets = {c["contract_name"]: int(c["targets"]) for c in json.load(open(label_path))}
    has_marker = defaultdict(bool)
    for _, d in graph.nodes(data=True):
        if MARKER[bug].search(d.get("code") or ""):
            has_marker[d["source_file"]] = True
    names = sorted(targets)
    y = np.array([targets[n] for n in names])
    kind = np.array(["solidifi" if n.startswith("buggy_") else ("smartbugs" if targets[n] else "clean") for n in names])
    marker = np.array([int(has_marker[n]) for n in names])
    model = HGTVulGraphClassifier(str(graph_path), feature_extractor=None, node_feature="inside_token", device=device)
    model.to(device)
    pred = {}
    for fold_dir in fold_dirs(run_dir):
        sel = json.load(open(fold_dir / "selection.json"))
        model.load_state_dict(torch.load(fold_dir / "best.pt", map_location=device))
        model.eval()
        with torch.no_grad():
            logits, _ = model(sel["val_files"])
        for name, p in zip(sel["val_files"], logits.argmax(dim=1).cpu().numpy()):
            pred[name] = int(p)
    p = np.array([pred[n] for n in names])
    out = {"hgt_pooled_buggy_f1": metrics(y, p)["buggy_f1"], "marker_rule_buggy_f1": metrics(y, marker)["buggy_f1"]}
    for k in ("solidifi", "smartbugs", "clean"):
        sel = kind == k
        out[f"hgt_correct_on_{k}"] = f"{int((p[sel] == y[sel]).sum())}/{int(sel.sum())}"
    return out


def main():
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    result = {}
    for name, exp in EXPERIMENTS.items():
        entry = {"contract": contract_level(exp["bug"], *exp["contract"], device)}
        for variant, (graph_path, run_dir) in exp["line"].items():
            entry[f"line / {variant}"] = line_level(exp["bug"], graph_path, run_dir, device)
        result[name] = entry
    (HERE / "diagnosis.json").write_text(json.dumps(result, indent=2))
    print("RESULT_JSON " + json.dumps(result))


if __name__ == "__main__":
    main()
