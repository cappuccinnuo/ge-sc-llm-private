"""Fail-closed acceptance and paired CV summaries for full formal folds."""
import math
import statistics
from pathlib import Path
import torch
from .common import read_json, write_json, sha256, digest, tensor_digest, metrics
from .checkpoint import StopMonitor
from .paper_protocol import NAME, VERSION, SCORE_ROLE, INITIALIZATION_VERSION, FORWARD_SCOPE
from .paper_run import effective_config
from .run_pair import checked_path
from scripts.labeling_v2.safe_graph import read_graph
from argparse import Namespace

METRICS = ("buggy_f1", "macro_f1", "precision", "recall")


def history_check(history, result, config):
    if not history or len(history) > 50:
        raise ValueError("Missing or excessive epochs")
    stop = StopMonitor(7, 0.001)
    best_epoch = None
    dummy = torch.nn.Parameter(torch.zeros(1))
    optimizer = torch.optim.Adam([dummy], lr=config["initial_lr"], weight_decay=config["weight_decay"])
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=config["max_lr"], total_steps=50,
                div_factor=config["div_factor"], final_div_factor=1, cycle_momentum=True)
    for i, row in enumerate(history):
        if row["epoch"] != i or not math.isfinite(row["train_loss"]):
            raise ValueError("Invalid epoch history")
        if not math.isclose(row["lr"], optimizer.param_groups[0]["lr"], rel_tol=1e-12, abs_tol=1e-15):
            raise ValueError("Learning-rate history mismatch")
        if not math.isclose(row["adam_beta1"], optimizer.param_groups[0]["betas"][0], rel_tol=1e-12):
            raise ValueError("Adam momentum schedule mismatch")
        save, stopped = stop.step(row["cv_validation_loss"])
        if save:
            best_epoch = i
        if save != row["saved_best"] or stop.counter != row["patience_counter"]:
            raise ValueError("Best/early-stop history mismatch")
        if stopped and i != len(history) - 1:
            raise ValueError("Training continued after early stopping")
        optimizer.step()
        scheduler.step()
    if len(history) < 50 and not stopped:
        raise ValueError("Truncated training masquerading as full")
    if result["best_epoch"] != best_epoch or result["last_epoch"] != len(history)-1:
        raise ValueError("Best/last epoch mismatch")
    if result["best_cv_validation_loss"] != stop.best or result["history_rows"] != len(history):
        raise ValueError("Best loss/history count mismatch")
    return {"epochs": len(history), "best_epoch": best_epoch, "last_epoch": len(history)-1,
            "stop_reason": "patience" if stopped else "epoch_cap", "lr_verified": True}


def prediction_check(rows, scores, expected_files, task):
    if not rows or {r["file"] for r in rows} != set(expected_files):
        raise ValueError("Prediction file coverage mismatch")
    keys = [(r["file"], r.get("original_graph_node_id") if task == "node" else None) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate scored samples")
    for r in rows:
        if r["score_role"] != SCORE_ROLE or r["target"] not in (0, 1):
            raise ValueError("Wrong prediction role or labels")
        for ck in ("best", "last"):
            if r[ck] not in (0, 1) or not 0 <= r[ck+"_positive_probability"] <= 1:
                raise ValueError("Invalid prediction")
    for ck in ("best", "last"):
        if metrics([r["target"] for r in rows], [r[ck] for r in rows]) != scores[ck]:
            raise ValueError("Exported prediction metrics mismatch")


def paired_errors(left, right, checkpoint):
    def key(row):
        return (row["file"], row.get("original_graph_node_id"))
    a, b = {key(r): r for r in left}, {key(r): r for r in right}
    if set(a) != set(b):
        raise ValueError("Paired prediction identities differ")
    transitions = {"both_correct": 0, "e0_wrong_e1_correct": 0, "e0_correct_e1_wrong": 0, "both_wrong": 0}
    changed = []
    for k in a:
        x, y = a[k], b[k]
        if x["target"] != y["target"]:
            raise ValueError("Paired truth differs")
        c0, c1 = x[checkpoint] == x["target"], y[checkpoint] == y["target"]
        name = ("both_correct" if c0 and c1 else "e0_wrong_e1_correct" if c1 else
                "e0_correct_e1_wrong" if c0 else "both_wrong")
        transitions[name] += 1
        if x[checkpoint] != y[checkpoint]:
            changed.append({"file": x["file"], "original_graph_node_id": x.get("original_graph_node_id"),
                "node_type": x.get("node_type"), "target": x["target"],
                "E0": x[checkpoint], "E1": y[checkpoint], "transition": name})
    return {"counts": transitions, "changed": changed}


def verify_fold(folder, job, plan):
    folder = Path(folder)
    result = read_json(folder/"result.json")
    config = read_json(folder/"effective_config.json")
    if (result.get("protocol"), result.get("protocol_version"), result.get("score_role"), result.get("mode")) != (NAME, VERSION, SCORE_ROLE, "full"):
        raise ValueError("Wrong formal protocol or smoke result")
    if result["cohort"] != job["cohort"] or result["task"] != job["task"] or result["completed_folds"] != 1 or result["requested_folds"] != 1:
        raise ValueError("Wrong formal job")
    if len(result["folds"]) != 1 or result["folds"][0]["fold"] != job["fold"]:
        raise ValueError("Wrong fold")
    expected_config = effective_config(job["task"], Namespace(mode="full", seed=1, epochs=50,
                                      smoke_epochs=3, device=plan["device"], threads=plan["threads"]))
    for k, v in expected_config.items():
        if config.get(k) != v:
            raise ValueError("Changed formal configuration: " + k)
    if config["code_sha256"] != plan["runner_code_sha256"]:
        raise ValueError("Runner code differs from plan")
    for key, path in (("prepared_manifest_sha256", Path(job["prepared"])/"manifest.json"),
                      ("split_manifest_sha256", Path(job["splits"]))):
        if config[key] != sha256(path):
            raise ValueError("Frozen input configuration mismatch")
    splitdoc = read_json(job["splits"])
    if read_json(folder/"splits.json") != splitdoc:
        raise ValueError("Run split differs from frozen split")
    split = next(f for f in splitdoc["folds"] if f["fold"] == job["fold"])
    fold_dir = folder/("fold_"+str(job["fold"]))
    fold = result["folds"][0]
    if fold["status"] != "complete":
        raise ValueError("Incomplete fold")
    prepared = Path(job["prepared"])
    manifest = read_json(prepared/"manifest.json")
    label_path = checked_path(prepared, manifest["graph_labels"])
    if read_json(fold_dir/"result.json") != fold or set(fold["variants"]) != {"E0", "E1"}:
        raise ValueError("Missing paired result")
    support = read_json(fold_dir/"schema_support_audit.json")
    pairing = read_json(fold_dir/"initialization_audit.json")
    if pairing["initialization_version"] != INITIALIZATION_VERSION:
        raise ValueError("Wrong initialization algorithm")
    acceptance, predictions = {}, {}
    import json
    for variant in ("E0", "E1"):
        dest, r = fold_dir/variant, fold["variants"][variant]
        if read_json(dest/"result.json") != r or r["score_role"] != SCORE_ROLE or r["status"] != "complete":
            raise ValueError("Variant result mismatch")
        if r["checkpoint_roundtrip_exact"] != {"best": True, "last": True} or not r["no_parameters_created_during_training_or_scoring"]:
            raise ValueError("Runtime reload/parameter audit failed")
        history = [json.loads(s) for s in (dest/"history.jsonl").read_text().splitlines()]
        h = history_check(history, r, config)
        binding = read_json(dest/"binding.json")
        graph_path = checked_path(prepared, manifest["graphs"][variant][job["task"]])
        for k, v in {"protocol":NAME, "protocol_version":VERSION, "score_role":SCORE_ROLE,
                     "forward_scope":FORWARD_SCOPE, "initialization_version":INITIALIZATION_VERSION,
                     "variant":variant, "task":job["task"], "cohort":job["cohort"],
                     "split":split, "effective_config_sha256":digest(config),
                     "registered_schema":support[variant]["schema"],
                     "pairing_audit_sha256":digest(pairing),
                     "support_audit_sha256":digest(support[variant]),
                     "graph_sha256":sha256(graph_path), "graph_labels_sha256":sha256(label_path),
                     "prepared_manifest_sha256":config["prepared_manifest_sha256"],
                     "split_manifest_sha256":config["split_manifest_sha256"]}.items():
            if binding.get(k) != v:
                raise ValueError("Checkpoint binding mismatch: " + k)
        if sha256(fold_dir/(variant+"_initial.pt")) != binding["initial_weights_sha256"]:
            raise ValueError("Initial weights changed")
        initial = torch.load(str(fold_dir/(variant+"_initial.pt")), map_location="cpu")
        if tensor_digest(initial) != r["initial_sha256"]:
            raise ValueError("Initialization fingerprint mismatch")
        del initial
        telemetry = read_json(dest/"telemetry.json")
        if telemetry["simultaneously_loaded_model_count"] != 2:
            raise ValueError("Pair not simultaneously constructed")
        if telemetry["fit_eval_checkpoint_wall_seconds"] <= 0:
            raise ValueError("Invalid timing")
        for ck in ("best", "last"):
            path = dest/(ck+".pt")
            if sha256(path) != r["checkpoint_sha256"][ck]:
                raise ValueError("Checkpoint file changed")
            obj = torch.load(str(path), map_location="cpu")
            if obj["format"] != "ddg-paper-cv-checkpoint-v1" or obj["binding"] != binding or obj["binding_sha256"] != digest(binding):
                raise ValueError("Checkpoint binding differs")
            if obj["epoch"] != r[ck+"_epoch"] or tensor_digest(obj["state_dict"]) != obj["state_sha256"]:
                raise ValueError("Checkpoint state/epoch differs")
            if obj["model_input"] != read_json(dest/"model_input.json"):
                raise ValueError("Checkpoint model input differs")
            sidecar = read_json(dest/(ck+".json"))
            if any(sidecar[k] != obj[k] for k in sidecar):
                raise ValueError("Checkpoint sidecar differs")
            shapes = telemetry["parameters"]["shapes"]
            if any(list(obj["state_dict"][k].shape) != s for k,s in shapes.items()):
                raise ValueError("Parameter shape telemetry mismatch")
            if sum(obj["state_dict"][k].numel() for k in shapes) != telemetry["parameters"]["total"]:
                raise ValueError("Parameter count mismatch")
            del obj
        predictions[variant] = read_json(dest/"cv_validation_predictions.json")
        prediction_check(predictions[variant], r["cv_validation"], split["val_files"], job["task"])
        graph = read_graph(graph_path)
        expected_node_ids = [i for i,(_,d) in enumerate(graph.nodes(data=True)) if d["source_file"] in split["val_files"]]
        for role in ("train","val"):
            supervision = read_json(dest/(role+"_supervision.json"))
            expected_ids = [i for i,(_,d) in enumerate(graph.nodes(data=True)) if d["source_file"] in split[role+"_files"]]
            if (supervision["files"] != sorted(split[role+"_files"]) or
                supervision["model_node_ids"] != expected_ids or
                supervision["sha256"] != digest({k:v for k,v in supervision.items() if k!="sha256"}) or
                binding["supervision_sha256"][role] != supervision["sha256"]):
                raise ValueError("Wrong train/validation supervision")
        if job["task"] == "node":
            if [row["model_node_id"] for row in predictions[variant]] != expected_node_ids:
                raise ValueError("Node mask prediction coverage differs")
            ids = list(graph)
            for row in predictions[variant]:
                original = ids[row["model_node_id"]]
                if row["original_graph_node_id"] != original or row["file"] != graph.nodes[original]["source_file"]:
                    raise ValueError("Prediction original-node mapping differs")
                if row["target"] != int(graph.nodes[original].get("node_info_vulnerabilities") is not None):
                    raise ValueError("Prediction truth differs from frozen graph")
        else:
            truth = {row["contract_name"]:row["targets"] for row in read_json(label_path)}
            if any(row["target"] != truth[row["file"]] for row in predictions[variant]):
                raise ValueError("Prediction truth differs from frozen file labels")
        del graph
        gradient = r["gradient_audit"]
        if read_json(dest/"gradient_audit.json") != gradient or len(gradient["epochs"]) != len(history):
            raise ValueError("Gradient audit incomplete")
        if gradient["backbone_update_l1"] <= 0 or not any(x["backbone_gradient_l1"] > 0 for x in gradient["epochs"]):
            raise ValueError("Backbone not trained")
        for epoch in gradient["epochs"]:
            for relation in epoch["ddg_relations"]:
                if relation["train_edges"] == 0 and relation["message_gradient_l1"] != 0:
                    raise ValueError("Unexpected validation-only supervised gradient")
        supported_gradients = [x["message_gradient_l1"] for ep in gradient["epochs"]
                               for x in ep["ddg_relations"] if x["train_edges"] > 0]
        if supported_gradients and not any(value > 0 for value in supported_gradients):
            raise ValueError("DDG has train instances but no observed supervised gradient; investigate before continuing")
        acceptance[variant] = dict(h, parameter_count=telemetry["parameters"]["total"],
            fit_eval_checkpoint_wall_seconds=telemetry["fit_eval_checkpoint_wall_seconds"],
            ddg_train_edges=support[variant]["ddg_training_edges"],
            ddg_gradient_l1_sum=sum(x["message_gradient_l1"] for ep in gradient["epochs"] for x in ep["ddg_relations"]),
            ddg_message_update_l1=gradient["ddg_message_update_l1"],
            validation_only_relations=support[variant]["registered_without_train_relations"])
    for ck in ("best","last"):
        expected = {m:fold["variants"]["E1"]["cv_validation"][ck][m]-fold["variants"]["E0"]["cv_validation"][ck][m] for m in METRICS}
        if fold["paired_cv_validation_delta"][ck] != expected:
            raise ValueError("Paired delta mismatch")
    return {"status":"passed","score_role":SCORE_ROLE,"job":job["id"],"variants":acceptance,
            "paired_errors":{ck:paired_errors(predictions["E0"],predictions["E1"],ck) for ck in ("best","last")}}


def metric_summary(rows, expected_folds):
    folds = {r["fold"] for r in rows}
    if folds != set(range(expected_folds)) or len(rows) != expected_folds*4:
        raise ValueError("Incomplete or duplicate task folds")
    by = {(r["fold"],r["variant"],r["checkpoint"]):r for r in rows}
    if len(by) != len(rows):
        raise ValueError("Duplicate task result")
    output = {}
    for ck in ("best","last"):
        output[ck] = {}
        for v in ("E0","E1","E1-E0"):
            stats = {}
            for m in METRICS:
                values = [(by[f,"E1",ck][m]-by[f,"E0",ck][m]) if v=="E1-E0" else by[f,v,ck][m] for f in range(expected_folds)]
                stats[m] = {"mean":statistics.mean(values),"sample_std":statistics.stdev(values),
                            "fold_values":values}
            output[ck][v] = stats
    return {"score_role":SCORE_ROLE,"aggregation":"unweighted fold mean; sample std ddof=1, not a confidence interval",
            "folds":expected_folds,"metrics":output}
