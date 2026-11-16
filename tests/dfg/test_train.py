"""Training-side tests: splits, anonymized features, family init, trainer, report.

Sealed references (tests/dfg/reference/sealed_training.json) come from the Prompt 8
artifacts archived on branch archive/pre-restructure-2026-11-15.
"""
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from dfg.inputs import REPO
from dfg.train import features, splits
from dfg.train.init import initialize_family, semantic_state
from dfg.train.report import holm, select, summarize
from dfg.train.runner import initial_states
from dfg.train.trainer import ROLES, StopMonitor, Supervision, fit, score, task_config
from dfg.utils import seed_all, tensor_digest

SEALED = json.loads((Path(__file__).parent / "reference/sealed_training.json").read_text())
CORPUS = REPO / "experiments/ge-sc-data/source_code/{}/source_files"


# ---------------------------------------------------------------------- splits

def test_strip_comments_keeps_strings_and_lines():
    text = 'a = "//not"; // gone\n/* x\ny */ b = \'/*\';'
    out = splits.strip_comments(text)
    assert out.count("\n") == text.count("\n")
    assert '"//not"' in out and "'/*'" in out and "gone" not in out and "x" not in out.split("\n")[1]


def test_duplicate_pairs_exact_and_near():
    base = "contract A { function f() public { uint x = 1; } }\n" * 30
    sources = {"a.sol": base, "b.sol": base.replace(" ", "  "), "c.sol": base + "// note\n",
               "d.sol": base[:-12] + "x = 2; } }\n", "e.sol": "contract Z { }"}
    ids = [splits.source_identity("cat", "co", f, s) for f, s in sorted(sources.items())]
    pairs = splits.duplicate_pairs(ids, {r["source_id"]: sources[r["file"]] for r in ids})
    file_of = {r["source_id"]: r["file"] for r in ids}
    exact = {tuple(sorted((file_of[a], file_of[b]))) for a, b in pairs["exact"]}
    near = {tuple(sorted((file_of[a], file_of[b]))) for a, b in pairs["near"]}
    assert exact == {("a.sol", "b.sol")}
    assert {("a.sol", "c.sol"), ("a.sol", "d.sol")} <= near and not any("e.sol" in p for p in near)


@pytest.mark.parametrize("task_id", sorted(SEALED["folds"]))
def test_grouped_folds_reproduce_sealed_folds(task_id):
    ref = SEALED["folds"][task_id]
    mine = splits.grouped_folds(task_id, ref["rows"], ref["k_folds"], ref["seed"], ref["inner_fraction"])
    assert [{r: f[r] for r in splits.ROLES} for f in mine["folds"]] == ref["folds"]


@pytest.mark.parametrize("category", sorted(SEALED["groups"]))
def test_duplicate_groups_reproduce_sealed_partition(category):
    corpus = Path(str(CORPUS).format(category))
    files = sorted(f for group in SEALED["groups"][category] for f in group)
    sources = {f: (corpus / f).read_bytes().decode("utf8") for f in files}
    group_of, _ = splits.category_groups(category, category + "_author", sources)
    mine = {}
    for f, g in group_of.items():
        mine.setdefault(g, []).append(f)
    assert sorted(sorted(v) for v in mine.values()) == SEALED["groups"][category]


# ---------------------------------------------------------------------- features

SOURCE = """pragma solidity ^0.4.24;
contract Bank {
    mapping(address => uint) balances;
    function withdraw_re_ent1(uint amount) public {
        require(tx.origin == msg.sender);
        msg.sender.transfer(amount);
        balances[msg.sender] -= amount;
    }
}
"""


def test_anonymize_is_a_checked_bijection():
    result = features.anonymize(SOURCE)
    assert result["status"] == "renamed"
    mapping = result["mapping"]
    assert {"Bank", "balances", "withdraw_re_ent1", "amount"} == set(mapping)
    assert len(set(mapping.values())) == len(mapping)
    out = result["rewritten"]
    assert "withdraw_re_ent1" not in out and "tx.origin" in out and "msg.sender.transfer(" in out
    assert features.anonymize(SOURCE) == result


def test_anonymize_falls_back_on_grammar_errors():
    assert features.anonymize("contract { function (")["status"] == "fallback"


@pytest.fixture(scope="module")
def three_contracts():
    from hcg.cfg.builder import build_corpus
    corpus = Path(str(CORPUS).format("reentrancy"))
    names = sorted(p.name for p in corpus.glob("*.sol"))[:3]
    graph, failures = build_corpus([corpus / n for n in names])
    assert not failures
    rng = np.random.RandomState(0)
    for _, data in graph.nodes(data=True):
        data["token"] = rng.randint(0, 50, 512).astype(np.float32)
        data["node_info_vulnerabilities"] = "[{'category': 'reentrancy', 'lines': [1]}]" if rng.rand() < .3 else None
    return graph, {n: (corpus / n).read_bytes().decode("utf8") for n in names}


def test_anonymous_codes_cover_every_node(three_contracts):
    graph, sources = three_contracts
    codes, fallbacks = features.anonymous_codes(graph, sources)
    assert set(codes) == set(graph.nodes) and not fallbacks
    changed = [n for n in codes if codes[n] != graph.nodes[n]["code"]]
    assert changed
    encoder = lambda text: np.full(512, len(text), dtype=np.float32)  # noqa: E731
    anon, summary = features.anonymize_features(graph, sources, encoder)
    assert summary["changed_nodes"] == len(changed)
    assert all(anon.nodes[n]["code"] == graph.nodes[n]["code"] for n in graph.nodes)


# ---------------------------------------------------------------------- init / trainer

@pytest.fixture(scope="module")
def three_contract_graphs(three_contracts):
    from dfg.graph.pipeline import iter_build, key_for_profile
    from tests.dfg.test_units import fake_encoder
    graph, sources = three_contracts
    built = {k: g for k, g, _ in iter_build(graph, sources, {f: None for f in sources},
                                             ("L1", "L2", "L3"), token_encoder=fake_encoder)}
    return lambda profile: built[key_for_profile(profile)], sorted(sources)


def test_family_initialization_shares_g0_parameters(three_contract_graphs):
    graph_of, _ = three_contract_graphs
    config = task_config("node")
    s, states = initial_states("node", graph_of, 0, ["G0", "G3R"], config)
    again = initial_states("node", graph_of, 0, ["G0", "G3R"], config)[1]
    assert all(tensor_digest(states[p]) == tensor_digest(again[p]) for p in states)
    from dfg.model.model import make_model
    models = {}
    for p in ("G0", "G3R"):
        seed_all(s["constructor"])
        models[p] = make_model("node", graph_of(p), p, "cpu", reducer="mean", layer_impl="shared_projection")
    initialize_family(models, s["constructor"])
    g0, g3 = semantic_state(models["G0"]), semantic_state(models["G3R"])
    assert set(g0) < set(g3) and all(torch.equal(g0[k], g3[k]) for k in g0)


def test_stop_monitor():
    stop = StopMonitor(patience=2, delta=.1)
    assert stop.step(1.0) == (True, False)
    assert stop.step(.95) == (True, False)
    assert stop.step(.94) == (True, True)


def test_fit_and_score_are_deterministic(three_contract_graphs):
    graph_of, files = three_contract_graphs
    config = task_config("node", maximum_training_epochs=3, schedule_epochs=3)
    split = dict(zip([r + "_files" for r in ROLES], [[f] for f in files]))
    runs = []
    for _ in range(2):
        s, states = initial_states("node", graph_of, 0, ["G0", "G3R"], config)
        from dfg.train.runner import _model
        model = _model("node", graph_of("G3R"), "G3R", config, "cpu")
        model.load_state_dict(states["G3R"])
        parts = {r: Supervision(model, "node", split[r + "_files"]) for r in ROLES}
        seed_all(s["fit"])
        history, checkpoints, best = fit(model, parts, {}, config, log=lambda *a: None)
        scores, predictions = score(model, parts, {}, checkpoints)
        runs.append(([h["train_loss"] for h in history], scores))
        assert len(history) == 3 and set(scores) == {"inner_val", "outer_test"}
        assert all(r["file"] == files[2] for r in predictions["outer_test"])
    assert runs[0] == runs[1]


# ---------------------------------------------------------------------- report

def _record(task, profile, fold, f1, val):
    m = lambda v: dict(buggy_f1=v, macro_f1=v, precision=v, recall=v)  # noqa: E731
    return dict(task_id=task, task="node", profile=profile, fold=fold,
                outer_test={"best": m(f1)}, inner_val={"best": m(val)})


def test_report_summary_selection_and_holm():
    records = [_record("t_node", p, f, base + f, base) for f in range(4)
               for p, base in (("G0", 50), ("G1R", 52), ("G3R", 60), ("G3", 59.95))]
    rows = {r["profile"]: r for r in summarize(records)}
    assert rows["G3R"]["buggy_f1"] == pytest.approx(61.5)
    assert select(records)["selected"] == "G3"   # within 0.1 pp: fewer relations wins
    assert holm({"a": .01, "b": .04, "c": None}) == {"a": .02, "b": .04, "c": None}


def test_resume_refuses_a_run_directory_with_another_config(tmp_path):
    from types import SimpleNamespace
    from dfg.train.runner import run_task
    ref = SEALED["folds"]["reentrancy_node"]
    data = SimpleNamespace(task="node", task_id="reentrancy_node", groups=1, feature_summary=dict(view="original"),
                           folds=splits.grouped_folds("reentrancy_node", ref["rows"], 10))
    (tmp_path / "reentrancy_node").mkdir()
    (tmp_path / "reentrancy_node" / "task.json").write_text(json.dumps(dict(task_id="reentrancy_node", config={})))
    with pytest.raises(ValueError, match="different config"):
        run_task(data, tmp_path, folds=[])
