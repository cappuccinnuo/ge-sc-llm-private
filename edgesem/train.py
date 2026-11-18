"""Grouped nested cross-validation of EdgeSem profiles (protocol P2).

Per fold, every profile is built fresh from the fold's G3R anchor (``edgesem.model.build``),
fitted with the fold's fit seed on the DFG task's inner train/validation files for a fixed 50
epochs (the DFG task config with patience 51), and scored on the outer test files with the
strict-minimum inner-validation checkpoint and the last one. Folds, labels and node tokens
are exactly those of ``dfg.train`` for the same task; G3R here is EdgeSem's own baseline.
Results go to ``<out>/<task_id>/fold_<k>/<profile>/result.json`` and resume like dfg.train.
"""
import gc
import json
import time
from pathlib import Path

import torch

from dfg.train.init import seeds
from dfg.train.runner import TaskData
from dfg.train.trainer import ROLES, Supervision, fit, score, task_config
from dfg.utils import Timer, digest, seed_all, tensor_digest
from edgesem.model.build import make_edge_model, validate_registration
from edgesem.schema import P2_OVERRIDES, PROFILES, TRAIN_PROFILES, validate_profile
from edgesem.store import EdgeStore
from hcg.store.io import dump_json, sha256


class EdgeSupervision(Supervision):
    """dfg.train supervision whose per-forward check is EdgeSem's registration check."""

    def forward(self, model):
        validate_registration(model, deep=False)
        return model()[self.mask] if self.task == "node" else model(self.files)[0]


def load_inputs(dataset, category, task, dfg_root, edgesem_root, task_id):
    """F4 edges and attributes of a task, checked against the DFG F3 graph they were built on."""
    store = EdgeStore(edgesem_root, dataset, category, task)
    summary = store.summary()
    f3 = Path(dfg_root) / dataset / category / task / "F3/graph.gpickle"
    if summary["dfg_f3"]["sha256"] != sha256(f3):
        raise ValueError("%s: EdgeSem store was built from a different F3 graph; rerun "
                         "`python -m edgesem build`" % task_id)
    return store.edges(), store.attributes(), summary


def run_task(data, edges, attrs, out_dir, profiles=TRAIN_PROFILES, folds=None, seed=1, device="cpu",
             config_overrides=None, save_checkpoints=False, log=print):
    """Fit and score every (fold, profile); return the list of result records."""
    for profile in profiles:
        validate_profile(profile)
    config = task_config(data.task, **dict(P2_OVERRIDES, **(config_overrides or {})))
    graph = data.graph("G3R")
    out_dir = Path(out_dir) / data.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    identity = dict(task_id=data.task_id, task=data.task, seed=seed, config=config, protocol="P2",
                    features=data.feature_summary, folds_sha256=digest(data.folds),
                    edges_sha256=digest(edges))
    previous = out_dir / "task.json"
    if previous.is_file():
        old = json.loads(previous.read_text())
        if {k: old.get(k) for k in identity} != identity:
            raise ValueError("%s already holds a run with a different config, seed, features, folds or "
                             "EdgeSem inputs; use another --out" % out_dir)
    dump_json(out_dir / "folds.json", data.folds)
    dump_json(previous, dict(identity, groups=data.groups))
    results = []
    for fold in (range(len(data.folds["folds"])) if folds is None else folds):
        split, fold_seeds = data.folds["folds"][fold], seeds(data.task, fold, seed)
        for profile in profiles:
            folder = out_dir / ("fold_%d" % fold) / profile
            done = folder / "result.json"
            if done.is_file():
                results.append(json.loads(done.read_text()))
                continue
            started, timer = time.monotonic(), Timer()
            log("  %s fold %d %s" % (data.task_id, fold, profile))
            reads_attributes = PROFILES[profile]["edge_features"] != "none"
            model = make_edge_model(data.task, graph, profile, fold, edges=edges,
                                    attrs=attrs if reads_attributes else None, device=device, seed=seed,
                                    hidden_size=config["hidden_size"], layers=config["layers"],
                                    heads=config["heads"])
            initial_sha = tensor_digest(model.state_dict())
            parts = {role: EdgeSupervision(model, data.task, split[role + "_files"]) for role in ROLES}
            timer.mark("build")
            seed_all(fold_seeds["fit"])
            history, checkpoints, best_epoch = fit(model, parts, data.file_labels, config, log=log)
            timer.mark("fit")
            scores, predictions = score(model, parts, data.file_labels, checkpoints)
            timer.mark("score")
            folder.mkdir(parents=True, exist_ok=True)
            if save_checkpoints:
                torch.save({k: {n: t.cpu() for n, t in v.items()} for k, v in checkpoints.items()},
                           folder / "checkpoints.pt")
            dump_json(folder / "history.json", history)
            dump_json(folder / "predictions.json", predictions)
            record = dict(task_id=data.task_id, task=data.task, fold=fold, seed=seed, profile=profile,
                          protocol="P2", seeds=fold_seeds, initial_state_sha256=initial_sha,
                          best_epoch=best_epoch, epochs=len(history), inner_val=scores["inner_val"],
                          outer_test=scores["outer_test"], canonical_relations=len(model.etypes_dict),
                          device=str(device), parameters=sum(p.numel() for p in model.parameters()),
                          seconds=round(time.monotonic() - started, 1), timing=timer.summary(len(history)))
            dump_json(done, record)
            results.append(record)
            log("    outer_test best buggy F1 %.2f" % scores["outer_test"]["best"]["buggy_f1"])
            log(timer.line(len(history)))
            del model, parts, checkpoints
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    return results


def train(dataset, categories, tasks, hcg_root, dfg_root, edgesem_root, label_root, out_root,
          profiles=TRAIN_PROFILES, folds=None, seed=1, device="cpu", features="original",
          config_overrides=None, save_checkpoints=False, encoder=None, log=print):
    results = []
    for category in categories:
        for task in tasks:
            data = TaskData(dataset, category, task, hcg_root, dfg_root, label_root, features, encoder, log)
            edges, attrs, _ = load_inputs(dataset, category, task, dfg_root, edgesem_root, data.task_id)
            results += run_task(data, edges, attrs, out_root, profiles, folds, seed, device,
                                config_overrides, save_checkpoints, log)
    return results
