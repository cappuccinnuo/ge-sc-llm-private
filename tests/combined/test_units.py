"""Unit tests for the combined model on one reentrancy contract (no dataset needed).

The NodeSem store is synthetic (seeded vectors of the S6 modality widths); the graph,
F4 edges and attributes are EdgeSem's one-contract fixture.
"""
import hashlib
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from combined import model as full
from dfg.train.init import seeds
from dfg.train.trainer import ROLES, fit, score, task_config
from edgesem.model.build import make_edge_model
from edgesem.train import EdgeSupervision
from nodesem.model import NodeSemAdapter
from nodesem.rows import row_key
from tests.dfg.test_units import CONTRACT
from tests.edgesem import test_units as edgesem_units

built = edgesem_units.built          # EdgeSem's one-contract fixture (module scope)
DIMS = dict(code=256, ctx=256, ctx_masked=256, static=245, teacher=384)


class FakeStore:
    """The parts of ``nodesem.store.TaskStore`` the combined model reads."""

    def __init__(self, graph, seed=0):
        rng = np.random.default_rng(seed)
        self._rows = [dict(row_key=row_key(n, d), file=d["source_file"], node_type=d["node_type"],
                           code_sha256=hashlib.sha256(d["code"].encode("utf8")).hexdigest())
                      for n, d in graph.nodes(data=True)]
        self._m = {k: rng.standard_normal((len(self._rows), dim)).astype(np.float32) for k, dim in DIMS.items()}
        self._m["teacher_present"] = np.ones(len(self._rows), dtype=np.uint8)
        self._m["teacher_present"][0] = 0
        self._m["teacher"][0] = 0

    def rows(self):
        return self._rows

    def matrices(self):
        return self._m

    def summary(self):
        return dict(features="synthetic")

    def modalities(self, ctx_view="original", student=None):
        from nodesem.store import TaskStore
        return TaskStore.modalities(self, ctx_view, student)


def _config(task):
    return task_config(task, maximum_training_epochs=2, schedule_epochs=2)


@pytest.fixture(scope="module")
def inputs(built):
    context, edges, attrs = built
    graph = context["graphs"]["F3"]
    return graph, FakeStore(graph), edges, attrs, {"G0": context["graphs"]["F0"], "G3R": graph}.get


@pytest.mark.parametrize("task", ["node", "contract"])
def test_combined_model_joins_edgesem_graph_parts_and_nodesem_adapters(inputs, task):
    graph, store, edges, attrs, graph_of = inputs
    config = _config(task)
    model = full.make_full_model(task, "reentrancy_" + task, graph_of, store, edges, attrs, 0, config)
    assert all(type(a) is NodeSemAdapter for a in model.adapt_ws)
    assert model.in_size == full.SPEC.carrier_dim() and model.edge_profile == "G4R-AC"
    # graph, relation, edge-encoder and classifier tensors are EdgeSem's G4R-AC initialization ...
    carried, _ = full.carried_graph(graph, store)
    edge = make_edge_model(task, carried, "G4R-AC", 0, edges=edges, attrs=attrs, hidden_size=config["hidden_size"],
                           layers=config["layers"], heads=config["heads"])
    state, reference = model.state_dict(), edge.state_dict()
    assert {k for k in state if not k.startswith("adapt_ws.")} == {k for k in reference if not k.startswith("adapt_ws.")}
    assert all(torch.equal(state[k], reference[k]) for k in reference if not k.startswith("adapt_ws."))
    # ... and every adapter tensor is NodeSem's S6@G3R initialization of the fold
    adapters = full.adapter_state(task, "reentrancy_" + task, graph_of, store, 0, config, 1)
    assert set(adapters) == {k for k in state if k.startswith("adapt_ws.")}
    assert all(torch.equal(state[k], v) for k, v in adapters.items())
    assert any(".proj.teacher." in k for k in adapters)
    # deterministic, and the input graph is untouched
    twin = full.make_full_model(task, "reentrancy_" + task, graph_of, store, edges, attrs, 0, config)
    assert all(torch.equal(v, twin.state_dict()[k]) for k, v in state.items())
    assert all(d["token"].shape == (512,) for _, d in graph.nodes(data=True))
    model.eval()
    with torch.no_grad():
        out = model() if task == "node" else model([CONTRACT])[0]
    assert out.shape == ((graph.number_of_nodes(), 2) if task == "node" else (1, 2)) and torch.isfinite(out).all()


def test_combined_model_trains_and_scores_with_the_dfg_engine(inputs):
    graph, store, edges, attrs, graph_of = inputs
    config = _config("node")
    model = full.make_full_model("node", "reentrancy_node", graph_of, store, edges, attrs, 0, config)
    labels = {CONTRACT: 1}
    parts = {role: EdgeSupervision(model, "node", [CONTRACT]) for role in ROLES}
    fit_seed = seeds("node", 0, 1)["fit"]
    assert set(full.reset_dropout(model, fit_seed, "reentrancy_node", 0)) == set(model.ntypes_dict)
    before = {k: v.clone() for k, v in model.state_dict().items()}
    history, checkpoints, _ = fit(model, parts, labels, config, log=lambda *_: None)
    assert len(history) == 2
    assert any(not torch.equal(before[k], v) for k, v in model.state_dict().items() if k.startswith("adapt_ws."))
    scores, predictions = score(model, parts, labels, checkpoints)
    assert {"best", "last"} <= set(scores["outer_test"])
    full.validate(model)


def test_inputs_refuse_a_nodesem_store_without_the_teacher(monkeypatch):
    from combined import train
    without = SimpleNamespace(matrices=lambda: dict(code=None, ctx=None, static=None))
    monkeypatch.setattr(train, "TaskStore", lambda *args: without)
    with pytest.raises(ValueError, match="teacher"):
        train.Inputs("B", "dfg", "nodesem", "edgesem").load("reentrancy", "node", "reentrancy_line")


# ---------------------------------------------------------------------- comparison over seeds

class _Refs:
    category = "t"
    source = {"d1": "DAppSCAN", "d2": "DAppSCAN", "s1": "SolidiFI", "c1": "clean", "w1": "clean"}
    pairs = {"c1": "DAppSCAN", "w1": "SolidiFI"}


def _fit(root, track, fold, profile, rows):
    import json as _json
    folder = root / "grouped" / ("t_%s" % track) / ("fold_%d" % fold) / profile
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(_json.dumps(dict(fold=fold)))
    (folder / "predictions.json").write_text(_json.dumps(dict(outer_test=rows)))


def test_compare_pairs_full_with_g0_per_seed_and_fold(tmp_path):
    from combined import compare
    runs = {}
    for seed in (1, 2):
        run = runs[seed] = tmp_path / ("s%d" % seed)
        for fold in (0, 1):
            nodes = [dict(file="d1", node=0, target=1), dict(file="d1", node=1, target=0),
                     dict(file="s1", node=2, target=1)]
            _fit(run, "line", fold, "FULL", [dict(r, best=r["target"]) for r in nodes])          # perfect
            _fit(run, "line", fold, "G0", [dict(r, best=int(r["file"] == "s1")) for r in nodes])  # misses d1
            files = [dict(file=f, target=t) for f, t in (("d1", 1), ("c1", 0), ("s1", 1), ("w1", 0))]
            _fit(run, "contract", fold, "FULL", [dict(r, best=r["target"]) for r in files])
            _fit(run, "contract", fold, "G0", [dict(r, best=1) for r in files])
    scores = compare.category_scores(runs, _Refs())
    assert [p[2:] for p in scores["line_dappscan"]["pairs"]] == [(100.0, 0.0)] * 4
    assert scores["line_all"]["pooled"][1] == pytest.approx((100.0, 200 / 3))
    # DAppSCAN contracts are scored against their own clean counterparts only (c1, not w1)
    assert scores["contract_dappscan"]["pairs"][0][2:] == pytest.approx((100.0, 200 / 3))
    result = compare.test(scores["line_dappscan"]["pairs"])
    assert result["improved"] == 4 and result["difference_mean_pp"] == 100.0
    assert result["p_raw"] == pytest.approx(0.125)   # the smallest exact two-sided p of 4 pairs


def test_run_track_writes_resumable_results_next_to_g0(inputs, tmp_path):
    from combined import train
    graph, store, edges, attrs, graph_of = inputs
    roles = {"%s_files" % role: [CONTRACT] for role in ROLES}
    track = SimpleNamespace(task="node", task_id="reentrancy_line", category="reentrancy", graph_task="node",
                            folds=dict(k_folds=1, folds=[roles]), graph=graph_of, file_labels={CONTRACT: 1})
    stages = SimpleNamespace(load=lambda category, graph_task, task_id: (store, edges, attrs))
    overrides = dict(maximum_training_epochs=1, schedule_epochs=1)
    first = train.run_track(track, stages, tmp_path, seed=1, config_overrides=overrides, log=lambda *_: None)
    folder = tmp_path / "reentrancy_line" / "fold_0" / "FULL"
    assert {p.name for p in folder.iterdir()} == {"result.json", "predictions.json", "history.json"}
    assert first[0]["profile"] == "FULL" and first[0]["edge_profile"] == "G4R-AC" and first[0]["node_config"] == "S6"
    again = train.run_track(track, stages, tmp_path, seed=1, config_overrides=overrides, log=lambda *_: None)
    assert again == first                                                    # resumed, not refitted
    with pytest.raises(ValueError, match="other inputs or settings"):
        train.run_track(track, stages, tmp_path, seed=2, config_overrides=overrides, log=lambda *_: None)
