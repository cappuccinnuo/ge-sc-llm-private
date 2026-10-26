"""V2 adaptation of experiments/paper_run.py::fit_variant.
Frozen source SHA256: babbc0fb0f3c040bcee1282973a01745d183a5fc47ffe650077d51daed20d3e0
Adam/OneCycle/single-step/post-update-eval/CE/StopMonitor numerical rules retained.
Only nested supervision roles, binding, relation audits, resources and export differ.
Full fixed graph is forwarded; outer-test supervision is accessed only after fitting.
"""
import json
import time
from pathlib import Path
import torch
from scripts.DFG.experiments.common import write_json,tensor_digest,metrics,scheduler_metadata
from scripts.DFG.dfg_v2 import AUX_NODE_TYPES, FORWARD_RELATIONS, REVERSE_OF
from .protocol import PROTOCOL_NAME,PROTOCOL_VERSION,FORWARD_SCOPE,SCORE_ROLE,SELECTION_ROLE
from .support import gradient_audit
from .checkpoint import StopMonitor,snapshot_input,save_checkpoint,restore_checkpoint
from .resources import Resources
V2_RELATIONS = set(FORWARD_RELATIONS) | set(REVERSE_OF.values())


_ENGINE_PURPOSE = "engine_equivalence_only_repeated_val_export_not_outer_test"


def _validate_fit_inputs(model, parts, task, labels, config, binding, original_ids, registration_support):
    """Refuse config/supervision drift before the first optimization step."""
    from scripts.DFG.experiments.common import digest
    from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
    from scripts.DFG.dfg_v2.tasks import read_labels
    from .protocol import PARTS, validate_parts

    if task != model.dfg_task or binding.get("task") != task:
        raise ValueError("Fit task differs from model/binding")
    if config.get("layer_impl", "original") != model.dfg_layer_impl:
        raise ValueError("Fit config layer_impl differs from model")
    if binding.get("effective_config_sha256") != digest(config):
        raise ValueError("Effective config differs from checkpoint binding")
    if binding.get("support_sha256") != digest(registration_support):
        raise ValueError("Relation support differs from checkpoint binding")
    if set(parts) != set(PARTS):
        raise ValueError("Fit requires exactly the three nested supervision roles")
    population = sorted({d["source_file"] for _, d in model.nx_graph.nodes(data=True)})
    bound_labels = read_labels(binding["labels"])
    if (not isinstance(labels, dict) or not set(population) <= set(labels)
            or any(type(y) is not int or y not in (0, 1) or f not in bound_labels
                   or bound_labels[f] != y for f, y in labels.items())):
        raise ValueError("Passed target labels differ from bound label file")
    if not isinstance(original_ids, list) or original_ids != model.original_graph_node_ids:
        raise ValueError("Prediction export original IDs differ from fixed model input")
    actual = {role: list(parts[role].files) for role in PARTS}
    if binding.get("purpose") == _ENGINE_PURPOSE:
        if (config.get("mode") != "engine_equivalence" or model.dfg_profile != "G0"
                or registration_support.get("purpose") != "engine_equivalence_only"):
            raise ValueError("Repeated validation is confined to the G0 engine diagnostic")
        split = binding["split"]
        train, val = split["train_files"], split["val_files"]
        if (not train or not val or len(train) != len(set(train)) or len(val) != len(set(val))
                or set(train) & set(val) or set(train) | set(val) != set(population)):
            raise ValueError("Invalid engine-diagnostic train/val partition")
        expected = dict(inner_train=sorted(train), inner_val=sorted(val), outer_test=sorted(val))
    else:
        expected = validate_parts(binding["split"], population)
        validate_parts(actual, population)
        if registration_support.get("parts_sha256") != digest(expected):
            raise ValueError("Relation-support partition differs from bound split")
    if actual != expected:
        raise ValueError("Supervised files differ from bound split")
    for role in PARTS:
        expected_part = DfgV2Supervision(model, task, expected[role])
        part = parts[role]
        if (part.task != task or part.full_ids != expected_part.full_ids
                or not torch.equal(part.mask, expected_part.mask)
                or part.manifest != expected_part.manifest):
            raise ValueError("Supervision mask/row binding mismatch: " + role)
    expected_initial = binding.get("initial_state_sha256")
    if expected_initial is not None and tensor_digest(model.state_dict()) != expected_initial:
        raise ValueError("Initial model tensor digest differs from bound untrained state")


def _fit(model, parts, task, labels, config, dest, binding, original_ids, support, memory_guard):
    dest = Path(dest)
    dest.mkdir()
    started = time.monotonic()
    _validate_fit_inputs(model, parts, task, labels, config, binding, original_ids, support)
    manifest = snapshot_input(model, binding)
    write_json(dest / "model_input.json", manifest)
    write_json(dest / "binding.json", binding)
    for name, part in parts.items():
        write_json(dest / (name + "_supervision.json"), part.manifest)
    train, valid = parts["inner_train"], parts["inner_val"]
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
        epoch_started = time.monotonic()
        memory_guard.check()
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
               "inner_val_loss": val_loss,
               "inner_val": metrics(yvalid.cpu().tolist(), logits.argmax(1).cpu().tolist()),
               "patience_counter": stop.counter, "saved_best": save_best,
               "seconds": time.monotonic()-epoch_started}
        history.append(row)
        with (dest / "history.jsonl").open("a", encoding="utf8") as handle:
            handle.write(json.dumps(row) + "\n")
        print("{} epoch {}/{} train={:.5f} inner_val={:.5f} BF1={:.3f} patience={}/{}{}".format(
            dest.name, epoch + 1, config["maximum_training_epochs"], row["train_loss"], val_loss,
            row["inner_val"]["buggy_f1"], stop.counter, stop.patience, " BEST" if save_best else ""), flush=True)
        memory_guard.check()
        if stop_now:
            break
    saved["last"] = save_checkpoint(dest / "last.pt", model, manifest, binding, epoch, stop, optimizer, scheduler)
    audit = {"epochs": gradient_history,
        "backbone_update_l1": sum(float((v.detach().cpu()-initial[k]).abs().sum())
            for k,v in model.state_dict().items() if not k.startswith("classify.")),
        "v2_message_update_l1": {
            "|".join(c): sum(float((layer.relation_msg.detach().cpu()[idx] -
                initial["gcs.{}.relation_msg".format(i)][idx]).abs().sum())
                for i,layer in enumerate(model.gcs))
            for c,idx in model.etypes_dict.items() if c[1] in V2_RELATIONS},
        "updates_may_include_weight_decay": config["weight_decay"] != 0}
    write_json(dest/"gradient_audit.json", audit)
    # First access to outer-test targets and supervised forward: optimization ended.
    scores, roundtrips = {}, {}
    for role in ("inner_val", "outer_test"):
        part = parts[role]
        truth = part.targets(model, labels).cpu().tolist()
        rows, scores[role], roundtrips[role] = [], {}, {}
        for ck in ("best","last"):
            restore_checkpoint(dest/(ck+".pt"), model, binding, saved[ck])
            model.eval()
            with torch.no_grad():
                logits = part.forward(model)
                expected = logits.detach().clone()
                pred = logits.argmax(1).cpu().tolist()
                probabilities = logits.softmax(1)[:,1].cpu().tolist()
            restore_checkpoint(dest/(ck+".pt"), model, binding, saved[ck])
            with torch.no_grad():
                roundtrips[role][ck] = bool(torch.equal(expected, part.forward(model)))
            if not roundtrips[role][ck]:
                raise AssertionError("Checkpoint reload changed "+role+" predictions")
            scores[role][ck] = metrics(truth,pred)
            for i,(y,prediction,probability) in enumerate(zip(truth,pred,probabilities)):
                if ck == "best":
                    if task == "node":
                        idx = part.full_ids[i]
                        data = model.nx_graph.nodes[idx]
                        if data["node_type"] in AUX_NODE_TYPES:
                            raise AssertionError("Auxiliary node leaked to predictions")
                        row = dict(model_node_id=idx, original_graph_node_id=original_ids[idx],
                            file=data["source_file"], node_type=data["node_type"],
                            graph_stored_source_lines=data.get("node_source_code_lines"),
                            graph_label_anchor=data.get("label"), target=y, score_role=role)
                    else:
                        row = dict(file=part.files[i], target=y, score_role=role)
                    rows.append(row)
                rows[i][ck], rows[i][ck+"_positive_probability"] = prediction, probability
        write_json(dest/(role+"_predictions.json"),rows)
    if registered_parameters != {n:id(p) for n,p in model.named_parameters()}:
        raise AssertionError("Parameter creation/replacement during fitting/scoring")
    memory_guard.check()
    result = dict(status="complete", layer_impl=model.dfg_layer_impl,
        protocol=PROTOCOL_NAME,protocol_version=PROTOCOL_VERSION,
        score_role=SCORE_ROLE,selection_role=SELECTION_ROLE,forward_scope=FORWARD_SCOPE,
        interpretation="nested outer test; inner validation selects best",
        best_epoch=best_epoch,last_epoch=epoch,best_inner_val_loss=stop.best,
        inner_val=scores["inner_val"],outer_test=scores["outer_test"],
        checkpoint_sha256=saved,gradient_audit=audit,
        checkpoint_roundtrip_exact=roundtrips,
        no_parameters_created_during_training_or_scoring=True,
        initial_sha256=tensor_digest(initial),history_rows=len(history),
        parameter_count=sum(p.numel() for p in model.parameters()),
        resources=memory_guard.summary(),seconds=time.monotonic()-started,
        outer_supervision_used_in_optimization=False)
    return result


def fit(model, parts, task, labels, config, dest, binding, original_ids, support, memory_guard=None):
    """Run the frozen numeric loop and always stop any owned resource watcher.

    A caller-owned guard remains under that caller's context/lifetime. For an
    owned guard, context-manager cleanup runs on nonfinite loss, checkpoint
    rejection, OOM, or any other exception, as well as on successful completion.
    """
    if memory_guard is None:
        guard = Resources(model.device)
        with guard:
            result = _fit(model, parts, task, labels, config, dest, binding,
                          original_ids, support, guard)
        result["resources"] = guard.summary()
    else:
        result = _fit(model, parts, task, labels, config, dest, binding,
                      original_ids, support, memory_guard)
    write_json(Path(dest) / "result.json", result)
    return result