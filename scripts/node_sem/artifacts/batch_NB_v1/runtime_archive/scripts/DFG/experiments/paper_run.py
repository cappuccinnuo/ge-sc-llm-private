"""Single-level file CV: full-graph forward, train supervision, CV val selection/scoring."""
import gc
import json
from pathlib import Path
import numpy as np
import torch
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.graph_audit import assert_augmented
from .common import (read_json, write_json, sha256, digest, seed_all, tensor_digest,
                     metrics, code_hashes, utc, scheduler_metadata)
from .runtime import make_model
from .run_pair import checked_path, effective_config as nested_config
from .paper_protocol import (NAME, VERSION, INITIALIZATION_VERSION, FORWARD_SCOPE,
                             SCORE_ROLE, SCHEMA_POLICY, protocol_output,
                             validate_document, initialize_pair)
from .paper_runtime import Supervision, graph_schema_and_support, validate_registration, gradient_audit
from .paper_checkpoint import StopMonitor, snapshot_input, save_checkpoint, restore_checkpoint


def effective_config(task, args):
    config = nested_config(task, args)
    config.update(protocol=NAME, protocol_version=VERSION,
                  initialization_version=INITIALIZATION_VERSION,
                  forward_scope=FORWARD_SCOPE, score_role=SCORE_ROLE,
                  selection="strict minimum CV validation loss, post-update eval forward",
                  batch="all train files (contract) or train node mask (node) per optimizer step",
                  schema_policy=SCHEMA_POLICY, partition_policy="full_fixed_graph_with_file_supervision")
    return config


def fit_variant(model, parts, task, labels, config, dest, binding, original_ids, support):
    dest.mkdir()
    manifest = snapshot_input(model, binding)
    write_json(dest / "model_input.json", manifest)
    write_json(dest / "binding.json", binding)
    for name, part in parts.items():
        write_json(dest / (name + "_supervision.json"), part.manifest)
    train, valid = parts["train"], parts["val"]
    ytrain, yvalid = train.targets(model, labels), valid.targets(model, labels)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["initial_lr"], weight_decay=config["weight_decay"])
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=config["max_lr"], total_steps=config["schedule_epochs"],
        div_factor=config["div_factor"], final_div_factor=config["final_div_factor"],
        cycle_momentum=config["cycle_momentum"])
    write_json(dest / "optimizer_schedule.json", {
        "optimizer": optimizer.__class__.__name__, "defaults": optimizer.defaults,
        "initial_groups": [{k: v for k, v in g.items() if k != "params"} for g in optimizer.param_groups],
        "scheduler": scheduler.__class__.__name__, "initial_state": scheduler_metadata(scheduler.state_dict())})
    stop, criterion = StopMonitor(config["patience"], config["delta"]), torch.nn.CrossEntropyLoss()
    initial = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    registered_parameters = {n: id(p) for n, p in model.named_parameters()}
    saved, history, gradient_history, best_epoch = {}, [], [], None
    for epoch in range(config["maximum_training_epochs"]):
        model.train()
        optimizer.zero_grad()
        loss = criterion(train.forward(model), ytrain)
        if not torch.isfinite(loss):
            raise ValueError("Nonfinite training loss")
        loss.backward()
        gradient_history.append(dict(gradient_audit(model, support), epoch=epoch))
        lr, beta1 = optimizer.param_groups[0]["lr"], optimizer.param_groups[0]["betas"][0]
        optimizer.step()
        scheduler.step()
        model.eval()
        with torch.no_grad():
            logits = valid.forward(model)
            val_loss = float(criterion(logits, yvalid))
        save_best, stop_now = stop.step(val_loss)
        if save_best:
            best_epoch = epoch
            saved["best"] = save_checkpoint(dest / "best.pt", model, manifest, binding,
                                            epoch, stop, optimizer, scheduler)
        row = {"epoch": epoch, "lr": lr, "adam_beta1": beta1, "train_loss": float(loss.detach()),
               "cv_validation_loss": val_loss,
               "cv_validation": metrics(yvalid.cpu().tolist(), logits.argmax(1).cpu().tolist()),
               "patience_counter": stop.counter, "saved_best": save_best}
        history.append(row)
        with (dest / "history.jsonl").open("a", encoding="utf8") as handle:
            handle.write(json.dumps(row) + "\n")
        print("{} epoch {}/{} train={:.5f} CV_validation={:.5f} BF1={:.3f} patience={}/{}{}".format(
            dest.name, epoch + 1, config["maximum_training_epochs"], row["train_loss"], val_loss,
            row["cv_validation"]["buggy_f1"], stop.counter, stop.patience, " BEST" if save_best else ""), flush=True)
        if stop_now:
            break
    saved["last"] = save_checkpoint(dest / "last.pt", model, manifest, binding, epoch, stop, optimizer, scheduler)
    audit = {"epochs": gradient_history,
             "backbone_update_l1": sum(float((v.detach().cpu() - initial[k]).abs().sum())
                                       for k, v in model.state_dict().items() if not k.startswith("classify.")),
             "ddg_message_update_l1": sum(float((layer.relation_msg.detach().cpu()[idx] -
                                         initial["gcs.{}.relation_msg".format(i)][idx]).abs().sum())
                                         for i, layer in enumerate(model.gcs)
                                         for c, idx in model.etypes_dict.items() if c[1] == "DATA_DEF_USE"),
             "updates_may_include_weight_decay": config["weight_decay"] != 0}
    write_json(dest / "gradient_audit.json", audit)
    # Deliberately score the same CV validation partition that selected best.
    # This is NOT an independent held-out test estimate.
    rows, scores, roundtrips = [], {}, {}
    truth = yvalid.cpu().tolist()
    for ck in ("best", "last"):
        restore_checkpoint(dest / (ck + ".pt"), model, binding, saved[ck])
        model.eval()
        with torch.no_grad():
            logits = valid.forward(model)
            expected = logits.detach().clone()
            pred, probabilities = logits.argmax(1).cpu().tolist(), logits.softmax(1)[:, 1].cpu().tolist()
        restore_checkpoint(dest / (ck + ".pt"), model, binding, saved[ck])
        with torch.no_grad():
            roundtrips[ck] = bool(torch.equal(expected, valid.forward(model)))
        if not roundtrips[ck]:
            raise AssertionError("Checkpoint reload changed CV predictions")
        scores[ck] = metrics(truth, pred)
        for i, (y, prediction, probability) in enumerate(zip(truth, pred, probabilities)):
            if ck == "best":
                if task == "node":
                    idx = valid.full_ids[i]
                    data = model.nx_graph.nodes[idx]
                    row = {"model_node_id": idx, "original_graph_node_id": original_ids[idx],
                           "file": data["source_file"], "node_type": data["node_type"],
                           "graph_stored_source_lines": data.get("node_source_code_lines"),
                           "graph_label_anchor": data.get("label"), "target": y, "score_role": SCORE_ROLE}
                else:
                    row = {"file": valid.files[i], "target": y, "score_role": SCORE_ROLE}
                rows.append(row)
            rows[i][ck], rows[i][ck + "_positive_probability"] = prediction, probability
    if registered_parameters != {n: id(p) for n, p in model.named_parameters()}:
        raise AssertionError("Parameter creation/replacement during fitting/scoring")
    write_json(dest / "cv_validation_predictions.json", rows)
    result = {"status": "complete", "protocol": NAME, "protocol_version": VERSION, "score_role": SCORE_ROLE,
              "interpretation": "smoke only; not an efficacy result" if config["mode"] == "smoke" else "CV validation fold",
              "best_epoch": best_epoch, "last_epoch": epoch, "best_cv_validation_loss": stop.best,
              "cv_validation": scores, "checkpoint_sha256": saved,
              "gradient_audit": audit, "checkpoint_roundtrip_exact": roundtrips,
              "no_parameters_created_during_training_or_scoring": True,
              "initial_sha256": tensor_digest(initial), "history_rows": len(history)}
    write_json(dest / "result.json", result)
    return result


def load_inputs(prepared, splits_path, task):
    prepared, splits_path = Path(prepared).resolve(), Path(splits_path).resolve()
    manifest, splits = read_json(prepared / "manifest.json"), read_json(splits_path)
    validate_document(splits)
    if splits["task"] != task or splits["prepared_manifest_sha256"] != sha256(prepared / "manifest.json"):
        raise ValueError("Split task/prepared binding mismatch")
    paths = {v: checked_path(prepared, manifest["graphs"][v][task]) for v in ("E0", "E1")}
    label_path = checked_path(prepared, manifest["graph_labels"])
    records = read_json(label_path)
    labels = {r["contract_name"]: int(r["targets"]) for r in records}
    if len(labels) != len(records) or any(y not in (0, 1) for y in labels.values()):
        raise ValueError("Duplicate or nonbinary file labels")
    graphs = {v: read_graph(path) for v, path in paths.items()}
    invariants = assert_augmented(graphs["E0"], graphs["E1"])
    if list(graphs["E0"]) != list(graphs["E1"]):
        raise ValueError("Paired model row order differs")
    population = {d["source_file"] for _, d in graphs["E0"].nodes(data=True)}
    if sorted(population) != splits["files"] or not population <= set(labels):
        raise ValueError("Frozen graph/split/file labels mismatch")
    if splits["file_labels"] != {f: labels[f] for f in sorted(population)}:
        raise ValueError("Frozen split label mismatch")
    if any(d["edge_type"] == "DATA_DEF_USE" for _, _, d in graphs["E0"].edges(data=True)):
        raise ValueError("E0 must not register DDG")
    if not invariants["ddg_edges"]:
        raise ValueError("E1 has no DDG intervention")
    return manifest, splits, paths, label_path, labels, graphs, invariants


def run(args):
    if args.epochs < 4 or args.smoke_epochs < 1 or args.threads < 1:
        raise ValueError("Invalid schedule/smoke/thread configuration")
    loaded = load_inputs(args.prepared, args.splits, args.task)
    manifest, splits, paths, label_path, labels, graphs, invariants = loaded
    if args.seed != splits["seed"]:
        raise ValueError("Seed must match frozen split; do not reseed/select favorable folds")
    selected = [f for f in splits["folds"] if args.fold is None or f["fold"] == args.fold]
    if not selected or (args.mode == "smoke" and len(selected) != 1):
        raise ValueError("Smoke requires exactly one existing fold")
    import sys, dgl, sklearn, networkx
    config = effective_config(args.task, args)
    config["environment"] = {"python": sys.version, "torch": torch.__version__, "dgl": dgl.__version__,
                             "sklearn": sklearn.__version__, "numpy": np.__version__, "networkx": networkx.__version__}
    config.update(prepared_manifest_sha256=sha256(Path(args.prepared) / "manifest.json"),
                  split_manifest_sha256=sha256(args.splits), code_sha256=code_hashes(),
                  cohort=manifest["cohort"], created_utc=utc())
    out = protocol_output(args.output)
    out.mkdir(parents=True)
    write_json(out / "effective_config.json", config)
    write_json(out / "splits.json", splits)
    write_json(out / "input_invariants.json", invariants)
    torch.set_num_threads(args.threads)
    results = []
    for split in selected:
        dest = out / ("fold_" + str(split["fold"]))
        dest.mkdir()
        seed = args.seed * 10000 + split["fold"] + (1000 if args.task == "contract" else 0)
        models, parts, supports = {}, {}, {}
        for v in ("E0", "E1"):
            supports[v] = graph_schema_and_support(graphs[v], split)
            seed_all(seed)
            models[v] = make_model(args.task, paths[v], args.device)
            validate_registration(models[v], supports[v]["schema"])
            parts[v] = {n: Supervision(models[v], args.task, split[n + "_files"]) for n in ("train", "val")}
        write_json(dest / "schema_support_audit.json", supports)
        pairing = initialize_pair(models["E0"], models["E1"], seed=seed + 77)
        write_json(dest / "initialization_audit.json", pairing)
        initial_hashes = {}
        for v, model in models.items():
            torch.save({k: value.detach().cpu().clone() for k, value in model.state_dict().items()},
                       str(dest / (v + "_initial.pt")))
            initial_hashes[v] = sha256(dest / (v + "_initial.pt"))
        result = {"fold": split["fold"], "status": "complete", "score_role": SCORE_ROLE, "variants": {}}
        for v in ("E0", "E1"):
            binding = {"protocol": NAME, "protocol_version": VERSION,
                       "initialization_version": INITIALIZATION_VERSION, "forward_scope": FORWARD_SCOPE,
                       "score_role": SCORE_ROLE, "schema_policy": SCHEMA_POLICY,
                       "registered_schema": supports[v]["schema"],
                       "supervision_sha256": {n: part.manifest["sha256"] for n, part in parts[v].items()},
                       "support_audit_sha256": digest(supports[v]),
                       "cohort": manifest["cohort"], "variant": v, "task": args.task,
                       "prepared_manifest_sha256": config["prepared_manifest_sha256"],
                       "graph_sha256": sha256(paths[v]), "graph_labels_sha256": sha256(label_path),
                       "split_manifest_sha256": config["split_manifest_sha256"], "split": split,
                       "effective_config_sha256": digest(config), "initial_weights_sha256": initial_hashes[v],
                       "pairing_audit_sha256": digest(pairing)}
            seed_all(seed + 1000000)
            result["variants"][v] = fit_variant(models[v], parts[v], args.task, labels, config,
                                                dest / v, binding, list(graphs[v]), supports[v])
        result["paired_cv_validation_delta"] = {
            ck: {key: result["variants"]["E1"]["cv_validation"][ck][key] -
                      result["variants"]["E0"]["cv_validation"][ck][key]
                 for key in ("buggy_f1", "macro_f1", "precision", "recall")} for ck in ("best", "last")}
        write_json(dest / "result.json", result)
        results.append(result)
        del models, parts
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    summary = {"protocol": NAME, "protocol_version": VERSION, "score_role": SCORE_ROLE,
               "mode": args.mode, "cohort": manifest["cohort"], "task": args.task,
               "requested_folds": len(selected), "completed_folds": len(results), "folds": results,
               "complete_cv_validation": args.mode == "full" and len(selected) == len(splits["folds"]),
               "note": "Same CV validation fold selects and scores best; not independent test. Smoke is not efficacy evidence."}
    write_json(out / "result.json", summary)
    print("FINISHED {} {} CV validation {}/{}; mode={}".format(
        manifest["cohort"], args.task, len(results), len(selected), args.mode), flush=True)
    return summary
