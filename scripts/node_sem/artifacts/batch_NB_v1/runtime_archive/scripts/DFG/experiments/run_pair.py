"""Run paired E0/E1 on fixed nested folds; smoke is the default.

No original trainers are modified. This standalone loop shares the current
corrected model, loss, optimizer/schedule and early-stop rules across E0/E1.
"""
import argparse
import gc
import time
from pathlib import Path

import numpy as np
import torch

from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.graph_audit import assert_augmented
from .common import (new_output, read_json, write_json, sha256, digest, seed_all,
                     tensor_digest, metrics, code_hashes, utc, scheduler_metadata)
from .runtime import make_model, GraphView, schema_report, assert_disconnected_files
from .checkpoint import StopMonitor, snapshot_input, save_checkpoint, restore_checkpoint
from .protocol import paired_initialize, validate_fold_document


def checked_path(prepared, record):
    path = (prepared / record["path"]).resolve()
    if prepared not in path.parents:
        raise ValueError("Artifact path escapes prepared directory")
    if sha256(path) != record["sha256"]:
        raise ValueError("Frozen artifact changed: " + str(path))
    return path


def effective_config(task, args):
    return {
        "mode": args.mode, "task": task, "seed": args.seed,
        "schedule_epochs": args.epochs,
        "maximum_training_epochs": min(args.smoke_epochs, args.epochs) if args.mode == "smoke" else args.epochs,
        "hidden_size": 128, "layers": 2, "heads": 8, "use_norm": True, "dropout": 0.2,
        "feature": "inside_token", "optimizer": "Adam",
        "initial_lr": 0.0002 if task == "node" else 0.0005,
        "max_lr": 0.005 if task == "node" else 0.01,
        "div_factor": 25 if task == "node" else 20, "final_div_factor": 1,
        "cycle_momentum": True, "weight_decay": 0.0 if task == "node" else 5e-6,
        "loss": "unweighted_cross_entropy", "patience": 7, "delta": 0.001,
        "selection": "strict minimum inner_val loss, post-update eval forward",
        "primary_checkpoint": "best", "secondary_checkpoint": "last",
        "batch": "one full inner-training partition per optimizer step",
        "schema_policy": "fail_closed", "partition_policy": "isolated_file_subgraphs",
        "device": args.device, "threads": args.threads,
        "metric_unit": "HCG node" if task == "node" else "source file",
    }


def target_for(model, view, task, graph_labels):
    if task == "node":
        return torch.tensor([model.node_labels[n] for n in view.full_ids],
                            dtype=torch.long, device=model.device)
    return torch.tensor([graph_labels[f] for f in view.files], dtype=torch.long, device=model.device)


def forward(model, view, task):
    with view.bind(model):
        return model() if task == "node" else model(view.files)[0]


def relation_gradient(model):
    result = {}
    for canonical, index in model.etypes_dict.items():
        if canonical[1] != "DATA_DEF_USE":
            continue
        result["|".join(canonical)] = {
            "message_gradient_l1": sum(float(layer.relation_msg.grad[index].abs().sum())
                for layer in model.gcs if layer.relation_msg.grad is not None)}
    return result


def fit_variant(model, views, task, labels, config, dest, binding, original_ids):
    dest.mkdir()
    manifest = snapshot_input(model, binding)
    write_json(dest / "model_input.json", manifest)
    write_json(dest / "binding.json", binding)
    for name, view in views.items():
        write_json(dest / (name + "_view.json"), view.manifest)
    train, valid = views["inner_train"], views["inner_val"]
    ytrain, yvalid = (target_for(model, v, task, labels) for v in (train, valid))
    optimizer = torch.optim.Adam(model.parameters(), lr=config["initial_lr"],
                                 weight_decay=config["weight_decay"])
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=config["max_lr"], total_steps=config["schedule_epochs"],
        div_factor=config["div_factor"], final_div_factor=config["final_div_factor"],
        cycle_momentum=config["cycle_momentum"])
    write_json(dest / "optimizer_schedule.json", {
        "optimizer": optimizer.__class__.__name__,
        "defaults": optimizer.defaults,
        "initial_groups": [{k: v for k, v in group.items() if k != "params"}
                           for group in optimizer.param_groups],
        "scheduler": scheduler.__class__.__name__, "initial_state": scheduler_metadata(scheduler.state_dict())})
    stop = StopMonitor(config["patience"], config["delta"])
    criterion = torch.nn.CrossEntropyLoss()
    initial = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    gradients, best_epoch, saved_hashes, history = None, None, {}, []
    # No outer-test targets or predictions are accessed during optimization.
    for epoch in range(config["maximum_training_epochs"]):
        model.train()
        optimizer.zero_grad()
        logits = forward(model, train, task)
        loss = criterion(logits, ytrain)
        if not torch.isfinite(loss):
            raise ValueError("Nonfinite training loss")
        loss.backward()
        if epoch == 0:
            gradients = {
                "backbone_gradient_l1": sum(float(p.grad.abs().sum()) for n, p in model.named_parameters()
                    if not n.startswith("classify.") and p.grad is not None),
                "classifier_gradient_l1": sum(float(p.grad.abs().sum()) for n, p in model.named_parameters()
                    if n.startswith("classify.") and p.grad is not None),
                "ddg_relations": relation_gradient(model)}
            if gradients["backbone_gradient_l1"] <= 0:
                raise AssertionError("HGT backbone gradient did not flow")
            if gradients["ddg_relations"] and not any(
                    v["message_gradient_l1"] > 0 for v in gradients["ddg_relations"].values()):
                raise AssertionError("DDG relations received no nonzero message gradient")
        lr = optimizer.param_groups[0]["lr"]
        beta1 = optimizer.param_groups[0]["betas"][0]
        optimizer.step()
        scheduler.step()
        model.eval()
        with torch.no_grad():
            val_logits = forward(model, valid, task)
            val_loss = float(criterion(val_logits, yvalid))
        save_best, stop_now = stop.step(val_loss)
        if save_best:
            best_epoch = epoch
            saved_hashes["best"] = save_checkpoint(
                dest / "best.pt", model, manifest, binding, epoch, stop, optimizer, scheduler)
        row = {"epoch": epoch, "lr": lr, "adam_beta1": beta1, "train_loss": float(loss.detach()),
               "inner_val_loss": val_loss, "inner_val": metrics(yvalid.cpu().tolist(), val_logits.argmax(1).cpu().tolist()),
               "patience_counter": stop.counter, "saved_best": save_best}
        history.append(row)
        with (dest / "history.jsonl").open("a", encoding="utf8") as handle:
            import json
            handle.write(json.dumps(row) + "\n")
        print("{} epoch {}/{} train={:.5f} inner_val={:.5f} BF1={:.3f} patience={}/{}{}".format(
            dest.name, epoch + 1, config["maximum_training_epochs"], row["train_loss"], val_loss,
            row["inner_val"]["buggy_f1"], stop.counter, stop.patience, " BEST" if save_best else ""), flush=True)
        if stop_now:
            break
    saved_hashes["last"] = save_checkpoint(
        dest / "last.pt", model, manifest, binding, epoch, stop, optimizer, scheduler)
    updated = model.state_dict()
    gradients["backbone_update_l1"] = sum(float((v.detach().cpu() - initial[k]).abs().sum())
        for k, v in updated.items() if not k.startswith("classify."))
    gradients["ddg_message_update_l1"] = sum(
        float((layer.relation_msg.detach().cpu()[idx] -
               initial["gcs.{}.relation_msg".format(i)][idx]).abs().sum())
        for i, layer in enumerate(model.gcs) for c, idx in model.etypes_dict.items()
        if c[1] == "DATA_DEF_USE")
    if gradients["ddg_relations"] and gradients["ddg_message_update_l1"] <= 0:
        raise AssertionError("DDG message weights did not update")
    write_json(dest / "gradient_audit.json", gradients)

    # Both checkpoints have been irrevocably selected/saved from inner val.
    # Only now read outer labels and evaluate. Never feed these scores to stop.
    outer = views["outer_test"]
    ytest = target_for(model, outer, task, labels).cpu().tolist()
    rows, scores, roundtrips = [], {}, {}
    for checkpoint in ("best", "last"):
        obj = restore_checkpoint(dest / (checkpoint + ".pt"), model, binding, saved_hashes[checkpoint])
        model.eval()
        with torch.no_grad():
            logits = forward(model, outer, task)
            probs = logits.softmax(1)[:, 1].cpu().tolist()
            pred = logits.argmax(1).cpu().tolist()
            # Deterministic reload repeat on the actual partition.
            expected = logits.detach().clone()
        restore_checkpoint(dest / (checkpoint + ".pt"), model, binding, saved_hashes[checkpoint])
        with torch.no_grad():
            roundtrips[checkpoint] = bool(torch.equal(expected, forward(model, outer, task)))
        if not roundtrips[checkpoint]:
            raise AssertionError("Checkpoint reload changed eval predictions")
        scores[checkpoint] = metrics(ytest, pred)
        for i, (y, prediction, probability) in enumerate(zip(ytest, pred, probs)):
            if checkpoint == "best":
                if task == "node":
                    full_id = outer.full_ids[i]
                    data = model.nx_graph.nodes[full_id]
                    row = {"model_node_id": full_id, "original_graph_node_id": original_ids[full_id],
                           "file": data["source_file"], "node_type": data["node_type"],
                           "graph_stored_source_lines": data.get("node_source_code_lines"),
                           "graph_label_anchor": data.get("label"), "target": y}
                else:
                    row = {"file": outer.files[i], "target": y}
                rows.append(row)
            rows[i][checkpoint] = prediction
            rows[i][checkpoint + "_positive_probability"] = probability
    write_json(dest / "outer_predictions.json", rows)
    result = {"status": "complete", "interpretation": "smoke only; not an efficacy result" if config["mode"] == "smoke" else "outer-test fold",
              "best_epoch": best_epoch, "last_epoch": epoch, "best_inner_val_loss": stop.best,
              "outer_test": scores, "checkpoint_sha256": saved_hashes,
              "gradient_audit": gradients, "checkpoint_roundtrip_exact": roundtrips,
              "initial_sha256": tensor_digest(initial), "history_rows": len(history)}
    write_json(dest / "result.json", result)
    return result


def run(args):
    prepared = Path(args.prepared).resolve()
    folds_path = Path(args.splits).resolve()
    manifest = read_json(prepared / "manifest.json")
    splits = read_json(folds_path)
    validate_fold_document(splits)
    if splits["task"] != args.task:
        raise ValueError("Task does not match split manifest")
    if splits["prepared_manifest_sha256"] != sha256(prepared / "manifest.json"):
        raise ValueError("Split manifest belongs to another frozen dataset")
    if args.epochs < 4 or args.smoke_epochs < 1:
        raise ValueError("Schedule epochs must be >=4; smoke epochs must be positive")
    paths = {v: checked_path(prepared, manifest["graphs"][v][args.task]) for v in ("E0", "E1")}
    label_path = checked_path(prepared, manifest["graph_labels"])
    labels = {x["contract_name"]: int(x["targets"]) for x in read_json(label_path)}
    graphs = {v: read_graph(p) for v, p in paths.items()}
    invariants = assert_augmented(graphs["E0"], graphs["E1"])
    original_ids = list(graphs["E0"].nodes())
    population = {d["source_file"] for _, d in graphs["E0"].nodes(data=True)}
    if not population <= set(labels):
        raise ValueError("Missing contract labels")
    if splits["file_labels"] != {f: labels[f] for f in sorted(population)}:
        raise ValueError("Split graph labels differ from frozen graph-label JSON")
    for split in splits["folds"]:
        parts = [set(split[name + "_files"]) for name in ("inner_train", "inner_val", "outer_test")]
        if set.union(*parts) != population or any(parts[i] & parts[j] for i in range(3) for j in range(i)):
            raise ValueError("Split population differs from frozen graph")
    for graph in graphs.values():
        assert_disconnected_files(graph)
    if invariants["ddg_edges"] == 0:
        raise ValueError("E1 has zero DDG edges: no experimental intervention")
    import sys, dgl, sklearn, networkx
    config = effective_config(args.task, args)
    config["environment"] = {"python": sys.version, "torch": torch.__version__,
                             "dgl": dgl.__version__, "sklearn": sklearn.__version__,
                             "numpy": np.__version__, "networkx": networkx.__version__}
    config.update({"prepared_manifest_sha256": sha256(prepared / "manifest.json"),
                   "split_manifest_sha256": sha256(folds_path), "code_sha256": code_hashes(),
                   "cohort": manifest["cohort"], "created_utc": utc()})
    out = new_output(args.output)
    out.mkdir(parents=True)
    write_json(out / "effective_config.json", config)
    write_json(out / "splits.json", splits)
    write_json(out / "input_invariants.json", invariants)
    selected = [f for f in splits["folds"] if args.fold is None or f["fold"] == args.fold]
    if not selected:
        raise ValueError("Requested fold absent")
    if args.mode == "smoke" and len(selected) != 1:
        raise ValueError("Smoke must select exactly one fold")
    torch.set_num_threads(args.threads)
    results = []
    for split in selected:
        dest = out / ("fold_" + str(split["fold"]))
        dest.mkdir()
        seed = args.seed * 10000 + split["fold"] + (1000 if args.task == "contract" else 0)
        models, views, audits = {}, {}, {}
        for variant in ("E0", "E1"):
            seed_all(seed)
            models[variant] = make_model(args.task, paths[variant], args.device)
            views[variant] = {name: GraphView(models[variant], split[name + "_files"])
                              for name in ("inner_train", "inner_val", "outer_test")}
            audits[variant] = schema_report(views[variant])
        write_json(dest / "schema_audit.json", audits)
        if not all(a["supported"] for a in audits.values()):
            result = {"fold": split["fold"], "status": "blocked_unseen_training_schema",
                      "schema_audit": audits, "outer_scoring_performed": False}
            write_json(dest / "result.json", result)
            print("BLOCKED fold {}: types/relations absent in inner training; see schema_audit.json".format(split["fold"]), flush=True)
            results.append(result)
            del models, views
            gc.collect()
            continue
        # E0 is freshly initialized, untrained. Copy common weights by semantic IDs.
        pairing = paired_initialize(models["E0"], models["E1"], seed=seed + 77)
        write_json(dest / "initialization_audit.json", pairing)
        initial_hashes = {}
        for variant, model in models.items():
            state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            torch.save(state, str(dest / (variant + "_initial.pt")))
            initial_hashes[variant] = sha256(dest / (variant + "_initial.pt"))
        result = {"fold": split["fold"], "status": "complete", "variants": {}}
        for variant in ("E0", "E1"):
            binding = {
                "cohort": manifest["cohort"], "variant": variant, "task": args.task,
                "prepared_manifest_sha256": config["prepared_manifest_sha256"],
                "graph_sha256": sha256(paths[variant]), "graph_labels_sha256": sha256(label_path),
                "split_manifest_sha256": config["split_manifest_sha256"], "split": split,
                "effective_config_sha256": digest(config),
                "initial_weights_sha256": initial_hashes[variant],
                "pairing_audit_sha256": digest(pairing),
                "phase_view_sha256": {k: v.manifest["sha256"] for k, v in views[variant].items()},
            }
            seed_all(seed + 1000000)
            result["variants"][variant] = fit_variant(
                models[variant], views[variant], args.task, labels, config,
                dest / variant, binding, original_ids)
        result["paired_outer_delta"] = {
            ck: {key: result["variants"]["E1"]["outer_test"][ck][key] -
                      result["variants"]["E0"]["outer_test"][ck][key]
                 for key in ("buggy_f1", "macro_f1", "precision", "recall")}
            for ck in ("best", "last")}
        write_json(dest / "result.json", result)
        results.append(result)
        del models, views
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    summary = {"mode": args.mode, "cohort": manifest["cohort"], "task": args.task,
               "requested_folds": len(selected), "completed_folds": sum(r["status"] == "complete" for r in results),
               "folds": results, "complete_outer_cv": args.mode == "full" and len(selected) == len(splits["folds"])
               and all(r["status"] == "complete" for r in results),
               "note": "Smoke results cannot establish DDG efficacy; blocked folds are never omitted from the denominator."}
    write_json(out / "result.json", summary)
    print("FINISHED {} {} completed {}/{}; mode={}".format(
        manifest["cohort"], args.task, summary["completed_folds"], len(selected), args.mode), flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared", required=True)
    p.add_argument("--splits", required=True)
    p.add_argument("--task", choices=("node", "contract"), required=True)
    p.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    p.add_argument("--fold", type=int, default=0, help="One outer fold; use --all_folds for explicitly requested full CV")
    p.add_argument("--all_folds", action="store_true")
    p.add_argument("--epochs", type=int, default=50, help="OneCycle schedule and full-run cap")
    p.add_argument("--smoke_epochs", type=int, default=3)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--device", default="cpu")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    if args.all_folds:
        if args.mode != "full":
            p.error("--all_folds requires --mode full")
        args.fold = None
    run(args)


if __name__ == "__main__":
    main()
