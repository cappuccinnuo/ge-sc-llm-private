"""benchmark: paper table, fold plans, source-line scoring, the two-phase detector, and a
tiny end-to-end run (paper protocol, 1 epoch, CPU) on real corpus files. No data needed."""
import json
import re
from pathlib import Path

import numpy as np
import pytest

from benchmark import evaluate, folds, lines, paper, report
from hcg.datasets.registry import DATASET_A

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"


# ---------------------------------------------------------------------- paper

def test_paper_tables_cover_both_datasets_in_order():
    assert paper.CATEGORIES == tuple(c.name for c in DATASET_A.categories)
    for ds in ("A", "B"):
        for level in ("contract", "line"):
            table = paper.tables(ds)[level]
            assert paper.SAME_TOKENIZER in table and set(paper.LLM_ROWS) <= set(table)
            for row in table.values():
                assert all(len(v) == 7 and all(0 < x <= 100 for x in v) for v in row.values())
    assert paper.value("A", "line", "codet5p-770m", "buggy_f1", "reentrancy") == 96.78
    assert paper.value("A", "line", "codet5p-770m", "macro_f1", "reentrancy") is None
    assert paper.best_llm("A", "contract", "buggy_f1", "reentrancy") == ("starcoder", 94.26)
    assert paper.value("B", "line", "codet5p-770m", "buggy_f1", "reentrancy") == 84.77
    assert paper.value("B", "line", "codet5p-770m", "buggy_f1", "access_control") == 71.78
    with pytest.raises(SystemExit):
        paper.tables("C")


# ---------------------------------------------------------------------- folds

def _labels(n_pos=12, n_neg=13):
    return {**{"buggy_%d.sol" % i: 1 for i in range(n_pos)}, **{"c%02d.sol" % i: 0 for i in range(n_neg)}}


def test_paper_contract_plan_is_seeded_stratified_and_validates_on_the_held_out_fold():
    labels = _labels()
    plan = folds.paper_contract("t_contract", labels, seed=1)
    assert plan == folds.paper_contract("t_contract", dict(reversed(list(labels.items()))), seed=1)
    assert plan != folds.paper_contract("t_contract", labels, seed=2)
    assert plan["k_folds"] == 5
    for split in plan["folds"]:
        assert split["inner_val_files"] == split["outer_test_files"]
        assert sorted(split["inner_train_files"] + split["outer_test_files"]) == sorted(labels)
        assert {labels[f] for f in split["outer_test_files"]} == {0, 1}


def test_paper_line_plan_is_ten_fold_and_cascade_keeps_the_contract_test_sets():
    labels = _labels()
    line = folds.paper_line("t_line", [f for f, y in labels.items() if y], seed=1)
    assert line["k_folds"] == 10 and all(len(s["outer_test_files"]) in (1, 2) for s in line["folds"])
    contract = folds.paper_contract("t_contract", labels)
    cascade = folds.cascade("t_cascade", contract, labels)
    for mine, theirs in zip(cascade["folds"], contract["folds"]):
        assert mine["outer_test_files"] == theirs["outer_test_files"]
        assert all(labels[f] for f in mine["inner_train_files"] + mine["inner_val_files"])
        assert set(mine["inner_val_files"]) <= set(mine["outer_test_files"])
    clean_val = {"folds": [{"fold": 0, "inner_train_files": ["buggy_0.sol"], "inner_val_files": ["c00.sol"],
                            "outer_test_files": ["buggy_1.sol"]}], "files": ["buggy_0.sol", "buggy_1.sol", "c00.sol"],
                 "seed": 1, "task_id": "x", "protocol": "grouped"}
    with pytest.raises(ValueError, match="no vulnerable contract"):
        folds.cascade("t", clean_val, labels)


def test_validate_rejects_leaks_and_missing_files():
    plan = folds.paper_line("t", ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"])
    plan["folds"][0]["inner_train_files"].append(plan["folds"][0]["outer_test_files"][0])
    with pytest.raises(ValueError, match="fits a file"):
        folds.validate(plan, plan["files"], "paper")
    with pytest.raises(ValueError, match="exactly once"):
        folds.validate(folds.paper_line("t", list("abcdefghij")), list("abcdefghijk"), "paper")


# ---------------------------------------------------------------------- lines

def test_counts_and_scores_on_a_hand_example():
    truth = {"a": {3, 9}, "b": set()}
    predicted = {"a": {3, 5}, "b": {7}}
    addressable = {"a": {3, 5, 6}, "b": {7, 8}}
    c = lines.counts(["a", "b"], truth, predicted, addressable)
    # a: tp {3}, fp {5}, fn {9} (not addressable), tn {6}; b: fp {7}, tn {8}
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (1, 2, 1, 2)
    s = lines.scores(c)
    assert s["buggy_f1"] == pytest.approx(200 / 5) and s["precision"] == pytest.approx(100 / 3)
    assert s["recall"] == 50 and s["coverage"] == 50 and s["hit_rate"] == 100
    assert s["macro_f1"] == pytest.approx((40 + 200 * 2 / 7) / 2)


def test_project_uses_label_endpoints_and_checks_files():
    import networkx as nx
    g = nx.MultiDiGraph()
    g.add_node(0, source_file="a", node_type="if", node_source_code_lines=[[4, 7]])
    g.add_node(1, source_file="a", node_type="end_if", node_source_code_lines=[[0]])
    g.add_node(2, source_file="a", node_type="env_source", node_source_code_lines=[[1]])
    of = lines.node_lines(g)
    assert of == {0: ("a", (4, 7)), 1: ("a", ())}
    predicted, addressable = lines.project([dict(file="a", node=0, best=1), dict(file="a", node=1, best=1)], of)
    assert predicted == {"a": {4, 7}} and addressable == {"a": {4, 7}}
    with pytest.raises(ValueError, match="names b"):
        lines.project([dict(file="b", node=0, best=1)], of)


def test_original_lines_map_back_through_comments_and_blank_lines():
    source = "pragma solidity ^0.4.0;\n\n// note\ncontract A {\n  /* x */ uint y;\n}\n"
    mapping = lines.original_lines(source)
    assert mapping == {1: [1], 2: [4], 3: [5], 4: [6]}
    assert lines.to_original({2, 3}, mapping) == [4, 5]


# ---------------------------------------------------------------------- two-phase detector

class _Refs:
    category = "t"
    file_labels = {"v": 1, "c": 0}
    source = {"v": "SolidiFI", "c": evaluate.CLEAN}
    truth = {"v": {2}, "c": set()}
    node_lines = {"contract": {0: ("v", (2,)), 1: ("v", (5,)), 2: ("c", (3,))}}

    def original(self, name):
        return {2: [12], 3: [13], 5: [15]}


def test_cascade_gates_the_line_model_with_the_contract_verdict():
    contract = [dict(file="v", target=1, best=0, best_probability=.2),
                dict(file="c", target=0, best=1, best_probability=.9)]
    nodes = [dict(file="v", node=0, target=1, best=1), dict(file="v", node=1, target=0, best=0),
             dict(file="c", node=2, target=0, best=1)]
    out = evaluate.cascade_fold(contract, nodes, _Refs())
    assert out["gated"]["lines"]["tn_fp_fn_tp"] == [1, 1, 1, 0]      # v missed, c flagged
    assert out["oracle"]["lines"]["tn_fp_fn_tp"] == [2, 0, 0, 1]
    assert out["ungated"]["lines"]["tn_fp_fn_tp"] == [1, 1, 0, 1]
    assert out["gated"]["nodes"]["tn_fp_fn_tp"] == [1, 1, 1, 0]
    found = {f["file"]: f for f in evaluate.findings(contract, nodes, _Refs(), fold=3)}
    assert found["c"]["flagged_lines"] == [13] and found["v"]["flagged_lines"] == []
    assert found["v"]["annotated_lines"] == [12] and found["v"]["fold"] == 3


# ---------------------------------------------------------------------- end to end

@pytest.fixture(scope="module")
def mini_hcg(tmp_path_factory):
    """A 20-contract hcg output (real graphs, synthetic labels/tokens) and a label root."""
    from hcg.cfg.builder import build_corpus
    from hcg.labels import line_level
    from hcg.store.io import dump_json, write_gpickle
    files = sorted(CORPUS.glob("*.sol"), key=lambda p: p.stat().st_size)
    vulnerable = [p for p in files if re.fullmatch(r"buggy_\d+\.sol", p.name)][:12]
    clean = [p for p in files if not p.name.startswith("buggy_")][:8]
    graph, failures = build_corpus(vulnerable + clean)
    assert not failures
    targets = {p.name: int(p in vulnerable) for p in vulnerable + clean}
    rng = np.random.RandomState(0)
    truth = {name: set() for name in targets}
    for _, data in graph.nodes(data=True):
        data["token"] = rng.randint(0, 50, 512).astype(np.float32)
        hit = targets[data["source_file"]] and rng.rand() < .3
        data["node_info_vulnerabilities"] = "[{'category': 'reentrancy', 'lines': [1]}]" if hit else None
        if hit:
            truth[data["source_file"]].update(x for x in lines.label_endpoints(data["node_source_code_lines"]) if x)
    root = tmp_path_factory.mktemp("hcg")
    out = root / "A" / "reentrancy"
    sub, _ = line_level(graph, targets)
    write_gpickle(graph, out / "contract_level.gpickle")
    write_gpickle(sub, out / "line_level.gpickle")
    dump_json(out / "graph_labels.json", [{"contract_name": n, "targets": t} for n, t in sorted(targets.items())])
    dump_json(out / "annotations.json", {"preprocessed": {n: [{"category": "reentrancy", "lines": sorted(v)}]
                                                          for n, v in truth.items()}})
    dump_json(out / "manifest.json", {"output_sha256": {}})
    label_root = tmp_path_factory.mktemp("labels")
    (label_root / "smartbug-dataset").mkdir()
    (label_root / "smartbug-dataset" / "versions.csv").write_text("file,compiled version\n")
    return root, label_root


def test_one_epoch_run_writes_scores_findings_and_report(mini_hcg, tmp_path):
    from benchmark.__main__ import main
    hcg_root, label_root = mini_hcg
    out = tmp_path / "run"
    args = ["--categories", "reentrancy", "--hcg", str(hcg_root), "--dfg", str(tmp_path / "nodfg"),
            "--label-root", str(label_root)]
    assert main(["run", "--out", str(out), "--protocols", "paper", "--folds", "0", "--epochs", "1",
                 "--device", "cpu"] + args) == 0
    scored = json.loads((out / "evaluation.json").read_text())["protocols"]["paper"]["G0"]["reentrancy"]
    assert scored["folds"] == {"contract": [0], "line": [0], "cascade": [0]}
    assert {"contract", "line_nodes", "line_source", "cascade", "by_source"} <= set(scored)
    assert set(scored["by_source"]) == {"SolidiFI"}      # the fixture's vulnerable files are SolidiFI
    assert set(scored["by_source"]["SolidiFI"]) == {"contract", "line_nodes", "line_source", "detector_lines"}
    assert set(scored["cascade"]) == {"gated", "oracle", "ungated", "folds"}
    found = json.loads((out / "findings/paper/G0/reentrancy.json").read_text())
    held_out = json.loads((out / "paper/reentrancy_contract/folds.json").read_text())["folds"][0]["outer_test_files"]
    assert sorted(f["file"] for f in found) == held_out
    text = (out / "report.md").read_text()
    assert "Contract level (paper Table 3)" in text and "| reentrancy | 1 |" in text
    assert "By contract source" in text
    assert main(["run", "--out", str(out), "--protocols", "paper", "--folds", "0", "--epochs", "1",
                 "--device", "cpu"] + args) == 0     # finished fits are reused
    assert report.render(json.loads((out / "evaluation.json").read_text()), {}).startswith("# Benchmark")


def test_paper_folds_equal_the_authors_trainers_folds(mini_hcg, tmp_path):
    """The authors' trainers (1 epoch) hold out exactly the paper plan's files."""
    from benchmark.__main__ import main
    hcg_root, label_root = mini_hcg
    out = tmp_path / "run"
    args = ["--categories", "reentrancy", "--hcg", str(hcg_root), "--dfg", str(tmp_path / "nodfg"),
            "--label-root", str(label_root), "--epochs", "1", "--device", "cpu", "--out", str(out)]
    assert main(["run", "--protocols", "upstream", "paper", "--folds", "0"] + args) == 0
    for level in ("contract", "line"):
        theirs = json.loads((out / "upstream" / ("reentrancy_" + level) / "result.json").read_text())
        mine = json.loads((out / "paper" / ("reentrancy_" + level) / "folds.json").read_text())
        assert [f["outer_test_files"] for f in theirs["folds"]] == [f["outer_test_files"] for f in mine["folds"]]
    with pytest.raises(ValueError, match="1 epochs, seed 1"):
        main(["run", "--protocols", "upstream", "--seed", "2"] + args)
