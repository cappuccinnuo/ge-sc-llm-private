"""Serial fixed-checkpoint replay. Never constructs an optimizer or calls backward."""
import argparse
import gc
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
import numpy as np
import torch
from scripts.DFG.experiments.audit.ddg_diagnostics_v1.diagnostic_common import (
    write_json, read_json, file_sha, compare_outputs)
from scripts.DFG.experiments.audit.ddg_diagnostics_v1.run_diagnostics import base_records, archived_gate
from scripts.DFG.experiments.common import tensor_digest, seed_all
from scripts.DFG.model_validation import capture_model_input, assert_model_input
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.experiments.e23_pilot.model import make_model
from scripts.DFG.experiments.e23_pilot.runtime import Supervision
from scripts.DFG.experiments.e23_pilot.checkpoint import restore_checkpoint
from scripts.DFG.experiments.e23_pilot.training import CardMonitor
from scripts.DFG.experiments.e23_h2.report import read_fit
from .common import (CONDITIONS, ROLE, H2, DEFAULT_OUTPUT, REPO, build_plan,
                     verify_plan, job_output, verified_success, key)
from .entry_validation import validate_entry
from .interventions import intervention


def replay(output, job, plan):
    dest = job_output(output, job)
    if verified_success(dest, file_sha(Path(output) / "plan.json"), job):
        print("Verified reuse", key(job), flush=True)
        return
    parent = Path(job["historical_plan"])
    if file_sha(parent) != job["historical_plan_sha256"]:
        raise ValueError("Historical plan changed")
    parent_plan = read_json(parent)
    original_job = next(x for x in parent_plan["jobs"] if key(x) == key(job))
    fit = read_fit(Path(job["historical_output"]), original_job, parent_plan, {})
    if fit["attempt"] != job["attempt"] or fit["receipt_sha256"] != job["receipt_sha256"]:
        raise ValueError("Accepted fit identity changed")
    info, attempt = fit["info"], Path(fit["attempt"])
    spec = info["graphs"][job["variant"]]
    if file_sha(spec["path"]) != spec["sha256"]:
        raise ValueError("Frozen graph changed")
    if file_sha(info["labels_path"]) != info["labels_sha256"]:
        raise ValueError("Frozen labels changed")
    if file_sha(info["source_prepared_manifest"]) != info["source_prepared_manifest_sha256"]:
        raise ValueError("Source manifest changed")
    sources = read_json(info["source_prepared_manifest"])["sources"]
    raw = read_graph(Path(spec["path"]))
    entry = validate_entry(raw, "e23_pilot")
    original_ids = list(raw)
    identity = [(n, d["source_file"], d["node_type"], d.get("code")) for n, d in raw.nodes(data=True)]
    del raw
    config = read_json(attempt / "effective_config.json")
    binding = read_json(attempt / "binding.json")
    expected = read_json(attempt / "model_input.json")
    if config["device"] != plan["device"]:
        raise ValueError("Device differs from accepted fit")
    processes = subprocess.run(["/usr/lib/wsl/lib/nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if processes.returncode or processes.stdout.strip():
        raise RuntimeError("Cannot reserve exclusive GPU worker: " + processes.stdout + processes.stderr)
    import dgl, sklearn, networkx
    observed = {"python": sys.version, "torch": torch.__version__, "dgl": dgl.__version__,
                "sklearn": sklearn.__version__, "numpy": np.__version__, "networkx": networkx.__version__}
    if observed != info["config"]["environment"]:
        raise ValueError("Package versions differ from frozen training environment")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; no CPU fallback")
    torch.set_num_threads(config["threads"])
    torch.cuda.init()
    torch.cuda.reset_peak_memory_stats(plan["device"])
    seed_all(info["fit_seed"])
    dest.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    try:
        with CardMonitor() as monitor:
            model = make_model(job["task"], spec["path"], plan["device"],
                hidden_size=config["hidden_size"], layers=config["layers"], heads=config["heads"])
            model.eval()
            if model.original_graph_node_ids != original_ids:
                raise ValueError("Original node identity mapping differs")
            for idx, (_, file, typ, code) in enumerate(identity):
                d = model.nx_graph.nodes[idx]
                if (d["source_file"], d["node_type"], d.get("code")) != (file, typ, code):
                    raise ValueError("Reindexed node mapping differs")
            part = Supervision(model, job["task"], info["split"]["val_files"])
            if part.manifest != read_json(attempt / "val_supervision.json"):
                raise ValueError("Frozen supervision differs")
            labels = {x["contract_name"]: x["targets"] for x in read_json(info["labels_path"])}
            records = base_records(model, part, original_ids, job["task"], labels)
            truth, files = [x["target"] for x in records], [x["file"] for x in records]
            all_checks = {}
            for ck in plan["checkpoints"]:
                ckdest = dest / ck
                ckdest.mkdir()
                obj = restore_checkpoint(attempt / (ck + ".pt"), model, binding,
                                         fit["result"]["checkpoint_sha256"][ck])
                del obj
                model.eval()
                weights = tensor_digest(model.state_dict())
                parameter_ids = {n: id(v) for n, v in model.named_parameters()}
                input_before = capture_model_input(model, external_inputs=binding)
                assert_model_input(model, expected, external_inputs=binding)
                with torch.no_grad():
                    native = part.forward(model).detach()
                    native_probs = native.softmax(1)[:, 1].cpu().tolist()
                gate = archived_gate(fit["predictions"], records, job["task"], ck,
                                     native, native_probs, fit["scores"][ck])
                rows = [dict(x, task_id=job["task_id"], task=job["task"], cohort=job["cohort"],
                    fold=job["fold"], variant=job["variant"], checkpoint=ck, score_role=ROLE,
                    source_sha256=sources[x["file"]]["sha256"]) for x in records]
                scores, audits = [], {}
                for name, relations in CONDITIONS.items():
                    with torch.no_grad(), intervention(model, relations=relations,
                                                       record=name in ("N", "Z_ALL")) as ctx:
                        logits = part.forward(model).detach()
                    if name == "N" and not torch.equal(native, logits):
                        raise AssertionError("Normal wrapper changed native outputs")
                    available = {c[1] for c in model.etypes_dict}
                    if not available.intersection(relations) and not torch.equal(native, logits):
                        raise AssertionError("Absent-relation intervention was not an exact no-op")
                    score, per_file, probabilities = compare_outputs(truth, native.cpu().numpy(),
                        logits.cpu().numpy(), files)
                    scores.append(dict(condition=name, score_role=ROLE, **score))
                    predicted = logits.argmax(1).cpu().tolist()
                    for row, pred, prob in zip(rows, predicted, probabilities):
                        row[name + "_pred"], row[name + "_prob"] = int(pred), float(prob)
                    audits[name] = ctx.audit
                    with torch.no_grad():
                        restored = part.forward(model).detach()
                    if not torch.equal(native, restored):
                        raise AssertionError("Context exit did not restore native outputs")
                    print("replay", job["task_id"], job["fold"], job["variant"], ck, name,
                          "flips", score["prediction_flips"], flush=True)
                    del logits, restored
                if weights != tensor_digest(model.state_dict()):
                    raise AssertionError("Parameters changed")
                if parameter_ids != {n: id(v) for n, v in model.named_parameters()}:
                    raise AssertionError("Parameter objects changed")
                if input_before != capture_model_input(model, external_inputs=binding):
                    raise AssertionError("Graph/features/labels/schema changed")
                assert_model_input(model, expected, external_inputs=binding)
                if any(v.grad is not None for v in model.parameters()):
                    raise AssertionError("Inference created gradients")
                checks = dict(archive_replay=gate, wrapper_exact=True, restored_native_exact=True,
                    weights_unchanged=True, parameter_objects_unchanged=True, input_unchanged=True,
                    no_gradients=True, optimizer_steps=0)
                write_json(ckdest / "scores.json", scores)
                write_json(ckdest / "predictions.json", rows)
                write_json(ckdest / "audit.json", dict(gates=checks, messages=audits,
                    checkpoint_sha256=fit["result"]["checkpoint_sha256"][ck],
                    state_sha256=weights, score_role=ROLE))
                all_checks[ck] = checks
                del native, rows, audits
            resources = dict(parameters=sum(v.numel() for v in model.parameters()),
                peak_allocated_bytes=torch.cuda.max_memory_allocated(plan["device"]),
                peak_reserved_bytes=torch.cuda.max_memory_reserved(plan["device"]))
            del model, part
            gc.collect()
            torch.cuda.empty_cache()
        resources.update(wall_seconds=time.perf_counter() - start, card=monitor.report())
        write_json(dest / "metadata.json", dict(job=job, entry=entry, resource=resources,
            plan_sha256=file_sha(Path(output) / "plan.json"), status="passed", checks=all_checks))
        artifacts = {str(p.relative_to(dest)): file_sha(p) for p in dest.rglob("*.json")}
        write_json(dest / "receipt.json", dict(status="passed", artifact_sha256=artifacts,
            plan_sha256=file_sha(Path(output) / "plan.json"), source_receipt_sha256=job["receipt_sha256"]))
    except Exception:
        write_json(dest / "failure.json", dict(status="failed", traceback=traceback.format_exc(),
            auto_retry=False, historical_inputs_preserved=True))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "replay", "worker", "summarize"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--index", type=int)
    parser.add_argument("--fold0-only", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        plan = build_plan(args.output)
        print("Prepared", len(plan["jobs"]), "models; best/last; inference only")
        return
    plan = verify_plan(args.output)
    if args.action == "worker":
        if args.index is None:
            raise ValueError("Worker requires an explicit job index")
        import fcntl
        with open("/tmp/mando_stage_i_gpu.lock", "w") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another Stage I GPU worker is active; refusing concurrency")
            replay(args.output, plan["jobs"][args.index], plan)
    elif args.action == "replay":
        for i, job in enumerate(plan["jobs"]):
            if args.fold0_only and job["fold"] != 0:
                continue
            if verified_success(job_output(args.output, job), file_sha(args.output / "plan.json"), job):
                print("Verified reuse", key(job), flush=True)
                continue
            # A fresh child releases all GPU allocations before the next model.
            result = subprocess.run([sys.executable, "-B", "-m", __package__ + ".run", "worker",
                                     "--output", str(args.output), "--index", str(i)], cwd=str(REPO))
            if result.returncode:
                raise SystemExit("Replay stopped; failed artifacts retained; no automatic retry")
    else:
        from .aggregate import summarize
        print(json.dumps(summarize(args.output, plan["jobs"]), default=str)[:3000])

if __name__ == "__main__":
    main()
