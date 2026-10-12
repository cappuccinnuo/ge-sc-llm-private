"""Disposable CUDA preflight: pair loading AND full-graph optimizer-step peak."""
import argparse
import gc
import json
import subprocess
import traceback
from pathlib import Path
import torch
from .common import write_json, seed_all, utc, digest, sha256
from .paper_run import load_inputs, effective_config
from .paper_protocol import initialize_pair
from .paper_runtime import Supervision, graph_schema_and_support, gradient_audit, validate_registration
from .runtime import make_model
from .formal_worker import memory, parameters


def hardware():
    result = {"utc": utc(), "torch": torch.__version__, "torch_cuda": torch.version.cuda,
              "cuda_available": torch.cuda.is_available()}
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used,driver_version",
                            "--format=csv,noheader"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
        result["nvidia_smi"] = {"exit_code": r.returncode, "output": r.stdout.decode()}
    except Exception as e:
        result["nvidia_smi"] = {"error": str(e)}
    result["host_meminfo"] = Path("/proc/meminfo").read_text().splitlines()[:5]
    return result


def probe(args):
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("Resource report exists")
    report = {"status": "running", "hardware_before": hardware(), "device": args.device,
              "task": args.task, "prepared": str(Path(args.prepared).resolve()), "steps": {}}
    try:
        if not args.device.startswith("cuda") or not torch.cuda.is_available():
            raise RuntimeError("This preflight requires available CUDA; no automatic CPU fallback")
        torch.set_num_threads(args.threads)
        torch.cuda.set_device(args.device)
        torch.cuda.reset_peak_memory_stats(args.device)
        manifest, splits, paths, label_path, labels, graphs, _ = load_inputs(args.prepared, args.splits, args.task)
        report["prepared_manifest_sha256"] = sha256(Path(args.prepared) / "manifest.json")
        report["split_sha256"] = sha256(args.splits)
        split = splits["folds"][0]
        seed = 10000 + (1000 if args.task == "contract" else 0)
        models = {}
        for v in ("E0", "E1"):
            seed_all(seed)
            models[v] = make_model(args.task, paths[v], args.device)
            validate_registration(models[v])
            report[v + "_parameters"] = parameters(models[v])
        report["simultaneous_load"] = memory(args.device)
        initialize_pair(models["E0"], models["E1"], seed + 77)
        # Same full fixed graphs, original optimizer/schedule and supervised fold0.
        # These disposable weights are NEVER used for formal initialization.
        for v in ("E0", "E1"):
            model = models[v]
            config = effective_config(args.task, argparse.Namespace(mode="full", seed=1, epochs=50,
                      smoke_epochs=3, device=args.device, threads=args.threads))
            optimizer = torch.optim.Adam(model.parameters(), lr=config["initial_lr"], weight_decay=config["weight_decay"])
            scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=config["max_lr"], total_steps=50,
                        div_factor=config["div_factor"], final_div_factor=1, cycle_momentum=True)
            part = Supervision(model, args.task, split["train_files"])
            val = Supervision(model, args.task, split["val_files"])
            support = graph_schema_and_support(graphs[v], split)
            seed_all(seed + 1000000)
            torch.cuda.reset_peak_memory_stats(args.device)
            model.train()
            optimizer.zero_grad()
            loss = torch.nn.functional.cross_entropy(part.forward(model), part.targets(model, labels))
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite resource-probe loss")
            loss.backward()
            grads = gradient_audit(model, support)
            optimizer.step()
            scheduler.step()
            model.eval()
            with torch.no_grad():
                val_logits = val.forward(model)
                if not torch.isfinite(val_logits).all():
                    raise ValueError("Nonfinite validation logits")
            report["steps"][v] = {"memory": memory(args.device), "train_loss": float(loss.detach()),
                                 "gradient": grads}
            del optimizer, scheduler, loss, val_logits
            gc.collect()
        report["status"] = "passed"
        report["note"] = ("Pair loading plus one train/backward/Adam step and validation for both variants. "
                          "Not a performance result, not proof of checkpoint reload determinism or future free VRAM.")
    except Exception as e:
        report["status"] = "blocked"
        report["error"] = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}
        if torch.cuda.is_available():
            try:
                report["memory_at_failure"] = memory(args.device)
            except Exception as memory_error:
                report["memory_at_failure"] = {"error": str(memory_error)}
    report["hardware_after"] = hardware()
    write_json(output, report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("steps", "E0_parameters", "E1_parameters")}, indent=2), flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("prepared", "splits", "output", "device"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--task", choices=("contract", "node"), required=True)
    p.add_argument("--threads", type=int, default=2)
    args = p.parse_args()
    raise SystemExit(0 if probe(args)["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
