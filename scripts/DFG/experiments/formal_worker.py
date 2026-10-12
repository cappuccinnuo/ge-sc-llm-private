"""Telemetry around the unchanged paper runner; no mathematical changes."""
import argparse
import time
import torch
from . import paper_run
from .common import write_json, utc


def memory(device):
    if not str(device).startswith("cuda"):
        return {"device": str(device), "cuda": False}
    torch.cuda.synchronize(device)
    return {"device": str(device), "cuda": True,
            "allocated_bytes": torch.cuda.memory_allocated(device),
            "reserved_bytes": torch.cuda.memory_reserved(device),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(device)}


def parameters(model):
    return {"total": sum(p.numel() for p in model.parameters()),
            "trainable": sum(p.numel() for p in model.parameters() if p.requires_grad),
            "shapes": {n: list(p.shape) for n, p in model.named_parameters()}}


def execute(args):
    original_make, original_fit = paper_run.make_model, paper_run.fit_variant
    loaded = []
    def make(*a, **kw):
        model = original_make(*a, **kw)
        loaded.append(parameters(model))
        return model
    def fit(model, parts, task, labels, config, dest, binding, original_ids, support):
        before = memory(model.device)
        if str(model.device).startswith("cuda"):
            torch.cuda.reset_peak_memory_stats(model.device)
        start = time.perf_counter()
        result = original_fit(model, parts, task, labels, config, dest, binding, original_ids, support)
        after = memory(model.device)
        write_json(dest / "telemetry.json", {"created_utc": utc(),
            "fit_eval_checkpoint_wall_seconds": time.perf_counter() - start,
            "parameters": parameters(model), "memory_before": before, "memory_after": after,
            "simultaneously_loaded_model_count": len(loaded),
            "note": "Wall time includes fitting, validation, checkpoint IO and reload scoring; not pure GPU kernel time."})
        return result
    paper_run.make_model, paper_run.fit_variant = make, fit
    try:
        return paper_run.run(args)
    finally:
        paper_run.make_model, paper_run.fit_variant = original_make, original_fit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "splits", "output"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--task", choices=("node", "contract"), required=True)
    p.add_argument("--fold", type=int, required=True)
    p.add_argument("--device", required=True)
    p.add_argument("--threads", type=int, default=2)
    a = p.parse_args()
    a.mode, a.epochs, a.smoke_epochs, a.seed = "full", 50, 3, 1
    execute(a)


if __name__ == "__main__":
    main()
