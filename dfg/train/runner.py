"""Grouped nested cross-validation of DFG profiles on one task.

For every fold: a G0 anchor is built with the fold's constructor seed, each enhanced
profile is family-initialized from it, then every profile is fitted with the fold's
fit seed on the same inner train/validation files and scored on the outer test files.
Results go to ``<out>/<task_id>/fold_<k>/<profile>/result.json``; finished fits are
skipped on rerun, so an interrupted run resumes.
"""
import gc
import json
import time
from pathlib import Path

import torch

from dfg.graph.pipeline import key_for_profile
from dfg.inputs import TASKS, hcg_dir, load_task
from dfg.model.model import make_model
from dfg.schema import PROFILES
from dfg.train.features import anonymize_features
from dfg.train.init import initialize_family, seeds
from dfg.train.splits import K_FOLDS, category_groups, grouped_folds, population
from dfg.train.trainer import ROLES, Supervision, fit, score, task_config
from dfg.utils import seed_all, tensor_digest
from hcg.store.io import dump_json, read_gpickle

ALL_PROFILES = ("G0", "G1R", "G2R", "G3R", "G3")


class TaskData:
    """Graphs per graph key, file labels and nested folds of one task."""

    def __init__(self, dataset, category, task, hcg_root, dfg_root, label_root,
                 features="anonymous", encoder=None, log=print):
        if features not in ("anonymous", "original"):
            raise ValueError("features must be 'anonymous' or 'original'")
        self.task = task
        inp = load_task(hcg_root, dataset, category, task, label_root)
        self.task_id = inp.task_id
        labels = json.loads((hcg_dir(hcg_root, dataset, category) / "graph_labels.json").read_text())
        self.file_labels = {r["contract_name"]: int(r["targets"]) for r in labels}
        self.graphs = {"F0": inp.graph}
        for key in ("F1", "F2", "F3"):
            path = Path(dfg_root) / dataset / category / task / key / "graph.gpickle"
            if path.is_file():
                self.graphs[key] = read_gpickle(path)
        self.feature_summary = dict(view=features)
        if features == "anonymous":
            if encoder is None:
                from dfg.inputs import TokenEncoder
                encoder = TokenEncoder()
            anonymous, self.feature_summary = anonymize_features(inp.graph, inp.sources, encoder)
            self.feature_summary["view"] = features
            for key, graph in self.graphs.items():
                for nid, data in anonymous.nodes(data=True):
                    if graph.nodes[nid]["code"] != data["code"]:
                        raise ValueError("%s %s does not extend the HCG node order" % (self.task_id, key))
                    graph.nodes[nid]["token"] = data["token"].copy()
        # Duplicate groups over the whole category (the contract-level population),
        # so transitive duplicates through files outside a node task still group.
        corpus = load_task(hcg_root, dataset, category, "contract", label_root).sources \
            if task != "contract" else inp.sources
        group_of, groups = category_groups(category, "%s_%s" % (category, dataset), corpus)
        rows = population(inp.graph, self.file_labels, group_of)
        self.folds = grouped_folds(self.task_id, rows, K_FOLDS[task])
        self.groups = len({r["group_id"] for r in rows})
        log("%s: %d files, %d duplicate groups, %d folds, features %s (%s changed nodes, %d fallback files)" % (
            self.task_id, len(rows), self.groups, len(self.folds["folds"]), features,
            self.feature_summary.get("changed_nodes", "-"), len(self.feature_summary.get("fallback_files", {}))))

    def graph(self, profile):
        key = key_for_profile(profile)
        if key not in self.graphs:
            raise FileNotFoundError("%s needs DFG graph %s; run `python -m dfg build`" % (profile, key))
        return self.graphs[key]


def _model(task, graph, profile, config, device):
    return make_model(task, graph, profile, device,
                      hidden_size=config["hidden_size"], layers=config["layers"], heads=config["heads"],
                      reducer=config["reducer"], layer_impl=config["layer_impl"])


def initial_states(task, graph_of, fold, profiles, config, seed=1):
    """Family-initialized untrained states of every profile for one fold (built on CPU).

    ``graph_of(profile)`` returns the task graph the profile's model registers.
    """
    s = seeds(task, fold, seed)
    seed_all(s["constructor"])
    anchor = _model(task, graph_of("G0"), "G0", config, "cpu")
    states = {"G0": {k: v.detach().clone() for k, v in anchor.state_dict().items()}}
    for profile in profiles:
        if profile == "G0":
            continue
        seed_all(s["constructor"])
        model = _model(task, graph_of(profile), profile, config, "cpu")
        initialize_family({"G0": anchor, profile: model}, s["constructor"])
        states[profile] = {k: v.detach().clone() for k, v in model.state_dict().items()}
        del model
    del anchor
    gc.collect()
    return s, {p: states[p] for p in profiles}


def run_task(data, out_dir, profiles=ALL_PROFILES, folds=None, seed=1, device="cpu",
             config_overrides=None, save_checkpoints=False, log=print):
    """Fit and score every (fold, profile); return the list of result records."""
    unknown = [p for p in profiles if p not in PROFILES]
    if unknown:
        raise ValueError("Unknown profiles: %s" % unknown)
    config = task_config(data.task, **(config_overrides or {}))
    out_dir = Path(out_dir) / data.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_json(out_dir / "folds.json", data.folds)
    dump_json(out_dir / "task.json", dict(task_id=data.task_id, task=data.task, config=config,
                                          groups=data.groups, features=data.feature_summary))
    chosen = range(len(data.folds["folds"])) if folds is None else folds
    results = []
    for fold in chosen:
        split = data.folds["folds"][fold]
        pending = [p for p in profiles if not (out_dir / ("fold_%d" % fold) / p / "result.json").is_file()]
        for profile in profiles:
            done = out_dir / ("fold_%d" % fold) / profile / "result.json"
            if done.is_file():
                results.append(json.loads(done.read_text()))
        if not pending:
            continue
        s, states = initial_states(data.task, data.graph, fold,
                                   ["G0"] + [p for p in pending if p != "G0"], config, seed)
        for profile in pending:
            started = time.monotonic()
            log("  %s fold %d %s" % (data.task_id, fold, profile))
            seed_all(s["constructor"])
            model = _model(data.task, data.graph(profile), profile, config, device)
            model.load_state_dict({k: v.to(device) for k, v in states[profile].items()}, strict=True)
            initial_sha = tensor_digest(states[profile])
            parts = {role: Supervision(model, data.task, split[role + "_files"]) for role in ROLES}
            seed_all(s["fit"])
            history, checkpoints, best_epoch = fit(model, parts, data.file_labels, config, log=log)
            scores, predictions = score(model, parts, data.file_labels, checkpoints)
            folder = out_dir / ("fold_%d" % fold) / profile
            folder.mkdir(parents=True, exist_ok=True)
            done = folder / "result.json"
            if save_checkpoints:
                torch.save({k: {n: t.cpu() for n, t in v.items()} for k, v in checkpoints.items()},
                           folder / "checkpoints.pt")
            dump_json(folder / "history.json", history)
            dump_json(folder / "predictions.json", predictions)
            record = dict(task_id=data.task_id, task=data.task, fold=fold, seed=seed, profile=profile,
                          seeds=s, initial_state_sha256=initial_sha, best_epoch=best_epoch,
                          epochs=len(history), inner_val=scores["inner_val"], outer_test=scores["outer_test"],
                          canonical_relations=len(model.etypes_dict), device=str(device),
                          parameters=sum(p.numel() for p in model.parameters()),
                          seconds=round(time.monotonic() - started, 1))
            dump_json(done, record)
            results.append(record)
            log("    outer_test best buggy F1 %.2f" % scores["outer_test"]["best"]["buggy_f1"])
            del model, parts, checkpoints
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    return results


def train(dataset, categories, tasks, hcg_root, dfg_root, label_root, out_root, profiles=ALL_PROFILES,
          folds=None, seed=1, device="cpu", features="anonymous", config_overrides=None,
          save_checkpoints=False, encoder=None, log=print):
    results = []
    for category in categories:
        for task in tasks:
            if task not in TASKS:
                raise ValueError("Unknown task " + task)
            data = TaskData(dataset, category, task, hcg_root, dfg_root, label_root, features, encoder, log)
            results += run_task(data, out_root, profiles, folds, seed, device, config_overrides,
                                save_checkpoints, log)
    return results
