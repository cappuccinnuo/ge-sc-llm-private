"""Bind weights to the exact frozen model input and experiment protocol."""
import math
from pathlib import Path
import torch
from scripts.DFG.model_validation import capture_model_input, assert_model_input
from .common import digest, tensor_digest, sha256, write_json


class StopMonitor:
    """Save every strict new minimum; patience counts delta-sized improvements."""
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


def save_checkpoint(path, model, expected_input, binding, epoch, monitor, optimizer, scheduler):
    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    obj = {"format": "ddg-controlled-v1", "state_dict": state,
           "state_sha256": tensor_digest(state), "model_input": expected_input,
           "binding": binding, "binding_sha256": digest(binding), "epoch": epoch,
           "monitor": {"best_inner_val_loss": monitor.best, "counter": monitor.counter,
                       "reference": monitor.reference},
           "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict()}
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    torch.save(obj, str(temp))
    temp.replace(path)
    write_json(path.with_suffix(".json"), {
        k: obj[k] for k in ["format", "state_sha256", "model_input", "binding",
                            "binding_sha256", "epoch", "monitor"]})
    return sha256(path)


def restore_checkpoint(path, model, binding, expected_file_sha256):
    # Check bytes before loading our own local checkpoint.
    if sha256(path) != expected_file_sha256:
        raise ValueError("Checkpoint file changed")
    obj = torch.load(str(path), map_location=model.device)
    if obj.get("format") != "ddg-controlled-v1":
        raise ValueError("Unsupported checkpoint format")
    if obj["binding"] != binding or obj["binding_sha256"] != digest(binding):
        raise ValueError("Checkpoint experiment binding mismatch")
    assert_model_input(model, obj["model_input"], external_inputs=binding)
    if tensor_digest(obj["state_dict"]) != obj["state_sha256"]:
        raise ValueError("Checkpoint weights changed")
    model.load_state_dict(obj["state_dict"])
    return obj


def snapshot_input(model, binding):
    return capture_model_input(model, external_inputs=binding)
