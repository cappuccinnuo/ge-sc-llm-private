"""Epoch engine and supervision of one fit (Prompt 8H numerics, without sealing).

The full fixed task graph is forwarded every epoch. ``inner_train`` files (contract
task) or their original nodes (node task) give one full-batch Adam + OneCycle step
per epoch; ``inner_val`` loss alone selects the best checkpoint and drives early
stopping; ``outer_test`` targets are first read after fitting. ``env_source`` nodes
are never supervised or scored.
"""
import copy
import math
import time

import torch

from dfg.model.model import validate_registration
from dfg.schema import AUX_NODE_TYPES
from dfg.utils import metrics

ROLES = ("inner_train", "inner_val", "outer_test")
CONFIG = {
    "contract": dict(k_folds=5, initial_lr=0.0005, max_lr=0.01, weight_decay=5e-06, div_factor=20),
    "node": dict(k_folds=10, initial_lr=0.0002, max_lr=0.005, weight_decay=0.0, div_factor=25),
}
COMMON = dict(hidden_size=128, layers=2, heads=8, reducer="mean", layer_impl="shared_projection",
              dropout=0.2, maximum_training_epochs=50, schedule_epochs=50,
              final_div_factor=1, cycle_momentum=True, patience=7, delta=0.001)


def task_config(task, **overrides):
    config = dict(COMMON, **CONFIG[task])
    unknown = set(overrides) - set(config)
    if unknown:
        raise ValueError("Unknown config keys: %s" % sorted(unknown))
    config.update(overrides)
    return config


class Supervision:
    """Which rows a role supervises: a node mask (node task) or a file batch (contract)."""

    def __init__(self, model, task, files):
        if task not in ("node", "contract") or task != model.dfg_task:
            raise ValueError("Supervision task does not match model")
        self.task, self.files = task, sorted(files)
        selected = set(self.files)
        if len(selected) != len(self.files):
            raise ValueError("Duplicate supervised files")
        population = {d["source_file"] for _, d in model.nx_graph.nodes(data=True)
                      if d["node_type"] not in AUX_NODE_TYPES}
        if not selected or not selected <= population:
            raise ValueError("Absent/empty supervised files")
        included = [d["source_file"] in selected and (task != "node" or d["node_type"] not in AUX_NODE_TYPES)
                    for _, d in model.nx_graph.nodes(data=True)]
        self.full_ids = [n for (n, _), keep in zip(model.nx_graph.nodes(data=True), included) if keep]
        self.mask = torch.tensor(included, dtype=torch.bool, device=model.device)

    def targets(self, model, file_labels):
        values = ([model.node_labels[n] for n in self.full_ids] if self.task == "node"
                  else [file_labels[f] for f in self.files])
        return torch.tensor(values, dtype=torch.long, device=model.device)

    def forward(self, model):
        validate_registration(model, deep=False)
        return model()[self.mask] if self.task == "node" else model(self.files)[0]


class StopMonitor:
    """Best = every strict new minimum; patience counts delta-sized improvements."""

    def __init__(self, patience=7, delta=0.001):
        if patience < 1 or delta < 0:
            raise ValueError("Invalid early-stopping settings")
        self.patience, self.delta = patience, delta
        self.best, self.reference, self.counter = float("inf"), None, 0

    def step(self, inner_val_loss):
        value = float(inner_val_loss)
        if not math.isfinite(value):
            raise ValueError("Nonfinite inner validation loss")
        save_best = value < self.best
        self.best = min(self.best, value)
        if self.reference is None or value < self.reference - self.delta:
            self.reference, self.counter = value, 0
        else:
            self.counter += 1
        return save_best, self.counter >= self.patience


def _state(model):
    return {k: v.detach().clone() for k, v in model.state_dict().items()}


def fit(model, parts, file_labels, config, log=print):
    """Train in place; return (history, {"best": state, "last": state}, best_epoch)."""
    train, valid = parts["inner_train"], parts["inner_val"]
    ytrain, yvalid = train.targets(model, file_labels), valid.targets(model, file_labels)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["initial_lr"],
                                 weight_decay=config["weight_decay"])
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=config["max_lr"], total_steps=config["schedule_epochs"],
        div_factor=config["div_factor"], final_div_factor=config["final_div_factor"],
        cycle_momentum=config["cycle_momentum"])
    stop, criterion = StopMonitor(config["patience"], config["delta"]), torch.nn.CrossEntropyLoss()
    states, history, best_epoch, epoch = {}, [], None, -1
    for epoch in range(config["maximum_training_epochs"]):
        started = time.monotonic()
        model.train()
        optimizer.zero_grad()
        loss = criterion(train.forward(model), ytrain)
        if not torch.isfinite(loss):
            raise ValueError("Nonfinite training loss")
        loss.backward()
        lr = optimizer.param_groups[0]["lr"]
        optimizer.step()
        scheduler.step()
        model.eval()
        with torch.no_grad():
            logits = valid.forward(model)
            val_loss = float(criterion(logits, yvalid))
        save_best, stop_now = stop.step(val_loss)
        if save_best:
            best_epoch, states["best"] = epoch, _state(model)
        history.append(dict(epoch=epoch, lr=lr, train_loss=float(loss.detach()), inner_val_loss=val_loss,
                            inner_val=metrics(yvalid.cpu().tolist(), logits.argmax(1).cpu().tolist()),
                            patience_counter=stop.counter, saved_best=save_best,
                            seconds=round(time.monotonic() - started, 3)))
        if stop_now:
            break
    states["last"] = _state(model)
    log("    epochs %d, best epoch %s, best inner_val loss %.4f" % (epoch + 1, best_epoch, stop.best))
    return history, states, best_epoch


def score(model, parts, file_labels, states, roles=("inner_val", "outer_test")):
    """Metrics and per-unit predictions of each checkpoint on each role."""
    scores, predictions = {}, {}
    for role in roles:
        part = parts[role]
        truth = part.targets(model, file_labels).cpu().tolist()
        scores[role], rows = {}, None
        for checkpoint in ("best", "last"):
            model.load_state_dict(states[checkpoint], strict=True)
            model.eval()
            with torch.no_grad():
                logits = part.forward(model)
            pred = logits.argmax(1).cpu().tolist()
            prob = logits.softmax(1)[:, 1].cpu().tolist()
            scores[role][checkpoint] = metrics(truth, pred)
            if rows is None:
                units = ([dict(file=model.nx_graph.nodes[i]["source_file"], node=i) for i in part.full_ids]
                         if part.task == "node" else [dict(file=f) for f in part.files])
                rows = [dict(u, target=y) for u, y in zip(units, truth)]
            for row, p, q in zip(rows, pred, prob):
                row[checkpoint], row[checkpoint + "_probability"] = p, q
        predictions[role] = rows
    return scores, predictions


def clone_state(state):
    return copy.deepcopy({k: v.detach().cpu() for k, v in state.items()})
