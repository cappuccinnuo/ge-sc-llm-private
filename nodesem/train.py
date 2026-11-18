"""Grouped nested cross-validation of NodeSem feature configurations.

Folds, supervision, the epoch engine and scoring are ``dfg.train``'s. Per fold and
profile, the DFG fold initial state seeds every configuration (``nodesem.init``);
S5/S6/S8 additionally start from S4's state, and S8 shares S5's modality-dropout
stream. Students (S5, S8) are fitted per fold on the fold's inner split only.
Results: ``<out>/<task_id>/fold_<k>/<config>@<profile>/result.json`` (resumable).
"""
import gc
import json
import time
from pathlib import Path

import numpy as np
import torch

from dfg.train.runner import TaskData, initial_states
from dfg.train.trainer import ROLES, Supervision, fit, score, task_config
from dfg.utils import Timer, digest, seed_all, tensor_digest
from hcg.store.io import dump_json
from nodesem.features import CONFIGS, CTX_VIEW, DROPOUT_PAIR, EXTENDS, carry, spec_for
from nodesem.init import extend_state, initial_state, pair_dropout
from nodesem.model import make_nodesem_model
from nodesem.store import TaskStore
from nodesem.student import fit_student, permute, student_seed

PROFILES = ("G0", "G3R")


def needs(name):
    return {m["name"] for m in CONFIGS[name]["modalities"]}


def _students(store, split, task_id, fold, fit_seed):
    """S5 student vectors for one fold and their S8 permutation."""
    rows, m = store.rows(), store.matrices()
    present = m["teacher_present"].astype(bool)
    result = fit_student(m["ctx"].astype(np.float32), m["static"].astype(np.float32),
                         m["teacher"].astype(np.float32), present, [r["file"] for r in rows], split,
                         student_seed(fit_seed, task_id, fold))
    permuted, _ = permute(result["values"], [r["node_type"] for r in rows], task_id, fold, fit_seed)
    return dict(S5=result["values"], S8=permuted), result["diagnostics"]


def _build(data, store, name, profile, config, device, student=None, vocabulary=None):
    spec = spec_for(name)
    carried, record = carry(data.graph(profile), spec, store.modalities(CTX_VIEW[name], student))
    model = make_nodesem_model(data.task, carried, record, profile, spec, config, device, vocabulary)
    return spec, model


def initial(data, store, name, profile, fold, config, fold_seeds, base, students, vocabulary=None):
    """Initial weights of one configuration (CPU), following the S4 extension rule."""
    seed_all(fold_seeds["constructor"])
    spec, model = _build(data, store, name, profile, config, "cpu", students.get(name), vocabulary)
    state, _ = initial_state(model, spec, data.task_id, fold, profile, base[profile],
                             fold_seeds["constructor"])
    if name in EXTENDS:
        s4, _ = initial(data, store, EXTENDS[name], profile, fold, config, fold_seeds, base, students, vocabulary)
        state, _ = extend_state(state, s4, "student" if "student" in needs(name) else "teacher")
    return state, tensor_digest(state)


def run_task(data, store, out_dir, configs, profiles=PROFILES, folds=None, seed=1, device="cpu",
             config_overrides=None, vocabulary=None, log=print):
    for name in configs:
        if name not in CONFIGS:
            raise ValueError("Unknown NodeSem configuration " + name)
        missing = needs(name) - set(store.matrices()) - {"token_ids", "student"}
        if "student" in needs(name) and "teacher" not in store.matrices():
            missing.add("teacher")
        if missing:
            raise ValueError("%s needs %s; run the corresponding nodesem stage" % (name, sorted(missing)))
    config = task_config(data.task, **(config_overrides or {}))
    out_dir = Path(out_dir) / data.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    identity = dict(task_id=data.task_id, task=data.task, seed=seed, config=config,
                    features=store.summary().get("features"), folds_sha256=digest(data.folds))
    previous = out_dir / "task.json"
    if previous.is_file():
        old = json.loads(previous.read_text())
        if {k: old.get(k) for k in identity} != identity:
            raise ValueError("%s already holds a run with a different config, seed, features or folds" % out_dir)
    dump_json(out_dir / "folds.json", data.folds)
    dump_json(previous, dict(identity, groups=data.groups))
    records = []
    for fold in (range(len(data.folds["folds"])) if folds is None else folds):
        split = data.folds["folds"][fold]
        jobs = [(n, p) for n in configs for p in profiles if not (CONFIGS[n]["layers"] == 0 and p != "G0")]
        pending = [(n, p) for n, p in jobs if not (out_dir / ("fold_%d" % fold) / ("%s@%s" % (n, p)) / "result.json").is_file()]
        for n, p in jobs:
            done = out_dir / ("fold_%d" % fold) / ("%s@%s" % (n, p)) / "result.json"
            if done.is_file():
                records.append(json.loads(done.read_text()))
        if not pending:
            continue
        fold_timer = Timer()
        fold_seeds, base = initial_states(data.task, data.graph, fold, ["G0", "G3R"], config, seed)
        students, student_info = {}, None
        if any("student" in needs(n) for n, _ in pending):
            students, student_info = _students(store, split, data.task_id, fold, fold_seeds["fit"])
        fold_setup = fold_timer.mark("fold_setup").seconds
        for name, profile in pending:
            started, timer = time.monotonic(), Timer(fold_setup)
            log("  %s fold %d %s@%s" % (data.task_id, fold, name, profile))
            state, initial_sha = initial(data, store, name, profile, fold, config, fold_seeds, base, students, vocabulary)
            seed_all(fold_seeds["constructor"])
            spec, model = _build(data, store, name, profile, config, device, students.get(name), vocabulary)
            model.load_state_dict({k: v.to(device) for k, v in state.items()}, strict=True)
            if name in DROPOUT_PAIR:
                pair_dropout(model, spec_for(DROPOUT_PAIR[name]))
            parts = {role: Supervision(model, data.task, split[role + "_files"]) for role in ROLES}
            seed_all(fold_seeds["fit"])
            for adapter in getattr(model, "adapt_ws", []):
                if hasattr(adapter, "reset_dropout"):
                    adapter.reset_dropout(fold_seeds["fit"], data.task_id, fold, profile)
            timer.mark("build")
            history, checkpoints, best_epoch = fit(model, parts, data.file_labels, config, log=log)
            timer.mark("fit")
            scores, predictions = score(model, parts, data.file_labels, checkpoints)
            timer.mark("score")
            folder = out_dir / ("fold_%d" % fold) / ("%s@%s" % (name, profile))
            folder.mkdir(parents=True, exist_ok=True)
            dump_json(folder / "history.json", history)
            dump_json(folder / "predictions.json", predictions)
            record = dict(task_id=data.task_id, task=data.task, fold=fold, seed=seed, profile="%s@%s" % (name, profile),
                          config_name=name, graph_profile=profile, spec_sha256=spec.digest(),
                          initial_state_sha256=initial_sha, best_epoch=best_epoch, epochs=len(history),
                          inner_val=scores["inner_val"], outer_test=scores["outer_test"],
                          student=student_info if name in ("S5", "S8") else None, device=str(device),
                          parameters=sum(p.numel() for p in model.parameters()),
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


def train(dataset, categories, tasks, hcg_root, dfg_root, nodesem_root, label_root, out_root, configs,
          profiles=PROFILES, folds=None, seed=1, device="cpu", config_overrides=None, vocabulary=None, log=print):
    records = []
    for category in categories:
        for task in tasks:
            data = TaskData(dataset, category, task, hcg_root, dfg_root, label_root, "original", log=log)
            store = TaskStore(nodesem_root, dataset, category, task)
            records += run_task(data, store, out_root, configs, profiles, folds, seed, device,
                                config_overrides, vocabulary, log)
    return records
