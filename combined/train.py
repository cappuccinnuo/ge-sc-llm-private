"""Grouped nested cross-validation of the combined model on one benchmark track.

Folds, supervision, the epoch engine, checkpoint selection and scoring are
``dfg.train``'s, with the same task configuration the benchmark uses for G0, so the
two arms differ only in the model. Per fold the model is built fresh
(``combined.model``), fitted with the fold's fit seed (NodeSem's modality dropout
seeded from it) and scored on the outer test files. Results go to
``<out>/<task_id>/fold_<k>/FULL/{result,predictions,history}.json`` next to the G0
fits, and resume like ``dfg.train``. ``full.json`` records the stage inputs.
"""
import gc
import json
import time
from dataclasses import dataclass
from pathlib import Path

import torch

from combined import EDGE_PROFILE, GRAPH_PROFILE, NODE_CONFIG, PROFILE
from combined.model import make_full_model, parameters, reset_dropout
from dfg.train.init import seeds
from dfg.train.trainer import ROLES, fit, score, task_config
from dfg.utils import Timer, digest, seed_all, tensor_digest
from edgesem.train import EdgeSupervision, load_inputs
from hcg.store.io import dump_json
from nodesem.store import TaskStore


@dataclass(frozen=True)
class Inputs:
    """Where the three stages' outputs live (``python -m dfg|nodesem|edgesem build``)."""
    dataset: str
    dfg: Path
    nodesem: Path
    edgesem: Path
    partial_teacher: bool = False       # accept a smoke-run teacher (describe --limit)

    def load(self, category, graph_task, task_id):
        """(NodeSem store, F4 edges, edge attributes) of the graph a track trains on."""
        store = TaskStore(self.nodesem, self.dataset, category, graph_task)
        if "teacher" not in store.matrices():
            raise ValueError("%s: NodeSem %s needs the teacher vectors; run `python -m nodesem describe` and "
                             "`python -m nodesem encode --teacher`" % (task_id, NODE_CONFIG))
        if not store.summary().get("teacher", {}).get("complete", True) and not self.partial_teacher:
            raise ValueError("%s: the teacher text comes from a limited (smoke) describe run; rerun "
                             "`python -m nodesem describe` without --limit" % task_id)
        edges, attrs, _ = load_inputs(self.dataset, category, graph_task, self.dfg, self.edgesem, task_id)
        return store, edges, attrs


def run_track(track, inputs, out_dir, folds=None, seed=1, device="cpu", config_overrides=None, log=print):
    """Fit and score the combined model on every chosen fold of ``track``; return the records.

    ``track`` is a ``benchmark.tracks.Track`` (task, task_id, folds, graph, file_labels,
    category, graph_task).
    """
    config = task_config(track.task, **(config_overrides or {}))
    store, edges, attrs = inputs.load(track.category, track.graph_task, track.task_id)
    seed_task_id = "%s_%s" % (track.category, track.task)
    out_dir = Path(out_dir) / track.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    identity = dict(task_id=track.task_id, task=track.task, seed=seed, config=config, folds_sha256=digest(track.folds),
                    graph_profile=GRAPH_PROFILE, edge_profile=EDGE_PROFILE, node_config=NODE_CONFIG,
                    nodesem=store.summary().get("features"), edges_sha256=digest(edges))
    previous = out_dir / "full.json"
    if previous.is_file() and json.loads(previous.read_text()) != identity:
        raise ValueError("%s already holds a FULL run from other inputs or settings; use another --out" % out_dir)
    dump_json(previous, identity)
    records = []
    for fold in (range(len(track.folds["folds"])) if folds is None else folds):
        folder = out_dir / ("fold_%d" % fold) / PROFILE
        if (folder / "result.json").is_file():
            records.append(json.loads((folder / "result.json").read_text()))
            continue
        split, fold_seeds = track.folds["folds"][fold], seeds(track.task, fold, seed)
        started, timer = time.monotonic(), Timer()
        log("  %s fold %d %s" % (track.task_id, fold, PROFILE))
        model = make_full_model(track.task, seed_task_id, track.graph, store, edges, attrs, fold, config, seed,
                                device)
        initial_sha = tensor_digest(model.state_dict())
        parts = {role: EdgeSupervision(model, track.task, split[role + "_files"]) for role in ROLES}
        seed_all(fold_seeds["fit"])
        reset_dropout(model, fold_seeds["fit"], seed_task_id, fold)
        timer.mark("build")
        history, checkpoints, best_epoch = fit(model, parts, track.file_labels, config, log=log)
        timer.mark("fit")
        scores, predictions = score(model, parts, track.file_labels, checkpoints)
        timer.mark("score")
        folder.mkdir(parents=True, exist_ok=True)
        dump_json(folder / "history.json", history)
        dump_json(folder / "predictions.json", predictions)
        record = dict(task_id=track.task_id, task=track.task, fold=fold, seed=seed, profile=PROFILE,
                      graph_profile=GRAPH_PROFILE, edge_profile=EDGE_PROFILE, node_config=NODE_CONFIG,
                      seeds=fold_seeds, initial_state_sha256=initial_sha, adapter_sha256=model.combined_adapter_sha256,
                      best_epoch=best_epoch, epochs=len(history), inner_val=scores["inner_val"],
                      outer_test=scores["outer_test"], device=str(device), parameters=parameters(model),
                      seconds=round(time.monotonic() - started, 1), timing=timer.summary(len(history)))
        dump_json(folder / "result.json", record)
        records.append(record)
        log("    outer_test best buggy F1 %.2f" % scores["outer_test"]["best"]["buggy_f1"])
        log(timer.line(len(history)))
        del model, parts, checkpoints
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return records
