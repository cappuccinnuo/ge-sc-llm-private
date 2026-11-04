"""One-epoch identity feature-view parity using the unchanged v2 trainer.

This is a CPU interface acceptance run, not a benchmark fit, model selection,
or permission to execute the 170-fit benchmark plan. Both branches start from
the same frozen zero-step G0 initialization and restore the same fit RNG.
"""
import argparse
import copy
import gc
from pathlib import Path
import torch
from scripts.DFG.dfg_v2.diagnostics8c.common import read, write_new, checked_plan
from scripts.DFG.dfg_v2.tasks import checked_ref, read_labels
from scripts.DFG.dfg_v2.model import make_model
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
from scripts.DFG.dfg_v2.experiment.trainer import fit
from scripts.DFG.dfg_v2.experiment.checkpoint import build_binding
from scripts.DFG.experiments.common import seed_all, tensor_digest, scheduler_metadata
from scripts.DFG.integration.io import sha256
from .feature_view import assemble_feature_graph


def nested_equal(a, b):
    if torch.is_tensor(a) or torch.is_tensor(b):
        return torch.is_tensor(a) and torch.is_tensor(b) and a.dtype == b.dtype and torch.equal(a, b)
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(nested_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(nested_equal(x, y) for x, y in zip(a, b))
    return a == b



def scheduler_equal(a, b):
    """Compare numerical state and exact callable implementation, not instance IDs."""
    if set(a) != set(b):
        return False
    for key in a:
        if callable(a[key]) or callable(b[key]):
            if not (callable(a[key]) and callable(b[key])):
                return False
            if getattr(a[key], "__func__", a[key]) is not getattr(b[key], "__func__", b[key]):
                return False
    return nested_equal(scheduler_metadata(a), scheduler_metadata(b))


def run(plan_path, feature_manifest_path, output, task_id="reentrancy_node"):
    plan_path, feature_manifest_path, output = map(Path, (plan_path, feature_manifest_path, output))
    plan = checked_plan(plan_path)
    features = read(feature_manifest_path)
    task = plan["tasks"][task_id]
    info = read(checked_ref(task["prepared"]["0/1"]))
    entry = info["profiles"]["G0"]
    view_ref = features["task_views"][task_id]["original_manifest"]
    initial = torch.load(str(checked_ref(entry["initial"])), map_location="cpu")
    if initial.get("kind") != "untrained_initial" or initial.get("optimizer_steps") != 0:
        raise ValueError("Parity requires zero-step initial, never a trained checkpoint")
    if tensor_digest(initial["state_dict"]) != entry["initial"]["state_sha256"]:
        raise ValueError("Frozen initialization digest differs")
    config = copy.deepcopy(task["config"])
    config.update(device="cpu", maximum_training_epochs=1, mode="feature_view_equivalence")
    if config["schedule_epochs"] != 50:
        raise ValueError("Keep original fifty-step schedule for equivalence")
    torch.set_num_threads(config["threads"])
    labels = read_labels(task["record"]["labels"])
    output.mkdir(parents=True, exist_ok=False)
    forward_ref = None
    records = {}
    for name in ("original", "bound_original_view"):
        seed_all(info["seeds"]["constructor"])
        graph = checked_ref(entry["graph"])
        if name == "bound_original_view":
            graph = assemble_feature_graph(graph, view_ref)
        model = make_model(task["record"]["task"], graph, "G0", "cpu",
            hidden_size=config["hidden_size"], layers=config["layers"], heads=config["heads"],
            reducer=plan["reducer"], layer_impl=plan["layer_impl"])
        model.load_state_dict(initial["state_dict"])
        parts = {role:DfgV2Supervision(model, task["record"]["task"], files)
                 for role, files in ((k, info["split"][k + "_files"]) for k in
                                     ("inner_train", "inner_val", "outer_test"))}
        model.eval()
        with torch.no_grad():
            before = parts["inner_train"].forward(model).detach().clone()
        if forward_ref is None:
            forward_ref = before
        elif not torch.equal(forward_ref, before):
            raise AssertionError("Identity feature binding changed forward bits")
        binding = build_binding(model, task_id=task_id, fold=0, seed=1, profile="G0",
            reducer=plan["reducer"], graph_ref=entry["graph"],
            fold_ref=task["record"]["folds"], label_ref=task["record"]["labels"],
            initial_sha256=entry["initial"]["sha256"], config=config,
            split=info["split"], support=entry["support"])
        binding["initial_state_sha256"] = entry["initial"]["state_sha256"]
        binding["purpose"] = "feature-view-interface-equivalence-not-benchmark"
        if name == "bound_original_view":
            binding["feature_view"] = view_ref
        seed_all(info["seeds"]["fit"])
        result = fit(model, parts, task["record"]["task"], labels, config,
            output/name, binding, model.original_graph_node_ids, entry["support"])
        records[name] = result
        del model, parts, graph
        gc.collect()
    first = torch.load(str(output/"original/last.pt"), map_location="cpu")
    second = torch.load(str(output/"bound_original_view/last.pt"), map_location="cpu")
    history_a = [__import__("json").loads(s) for s in (output/"original/history.jsonl").read_text().splitlines()]
    history_b = [__import__("json").loads(s) for s in (output/"bound_original_view/history.jsonl").read_text().splitlines()]
    if len(history_a) != 1 or len(history_b) != 1:
        raise AssertionError("Expected exactly one epoch per acceptance branch")
    fields = ("epoch", "lr", "adam_beta1", "train_loss", "inner_val_loss", "inner_val",
              "patience_counter", "saved_best")
    checks = dict(forward_bitwise=True,
        epoch_loss_bitwise=all(history_a[0][k] == history_b[0][k] for k in fields),
        state_digest_equal=first["state_sha256"] == second["state_sha256"],
        model_state_equal=nested_equal(first["state_dict"], second["state_dict"]),
        optimizer_state_equal=nested_equal(first["optimizer"], second["optimizer"]),
        scheduler_state_equal=scheduler_equal(first["scheduler"], second["scheduler"]),
        best_last_scores_equal=records["original"]["outer_test"] == records["bound_original_view"]["outer_test"])
    report = dict(version="prompt8d-identity-feature-parity-v1", passed=all(checks.values()),
        task_id=task_id, source_plan=dict(path=str(plan_path.resolve()),sha256=sha256(plan_path)),
        feature_manifest=dict(path=str(feature_manifest_path.resolve()),sha256=sha256(feature_manifest_path)),
        identity_view=view_ref, device="cpu", epochs_per_branch=1, acceptance_optimizer_steps=2,
        formal_fits=0, schedule_epochs=50, effective_config=config, checks=checks,
        history={k:{f:v[0][f] for f in fields} for k,v in
                 (("original",history_a),("bound_original_view",history_b))}, **checks)
    write_new(output/"equivalence.json", report)
    if not report["passed"]:
        raise AssertionError("Feature-view identity parity failed")
    print("Identity view forward/one-epoch/model/Adam/scheduler bitwise equal", flush=True)
    return report


def review_existing(existing, output):
    """Recheck the two existing acceptance runs; perform zero optimizer steps."""
    existing, output = Path(existing), Path(output)
    original_report = read(existing / "equivalence.json")
    data = {}
    histories = {}
    for name in ("original", "bound_original_view"):
        result = read(existing / name / "result.json")
        path = existing / name / "last.pt"
        if sha256(path) != result["checkpoint_sha256"]["last"]:
            raise ValueError("Acceptance checkpoint changed")
        data[name] = torch.load(str(path), map_location="cpu")
        if tensor_digest(data[name]["state_dict"]) != data[name]["state_sha256"]:
            raise ValueError("Acceptance state digest differs")
        histories[name] = [__import__("json").loads(line) for line in
                          (existing / name / "history.jsonl").read_text().splitlines()]
        if len(histories[name]) != 1:
            raise ValueError("Acceptance is exactly one epoch")
    a, b = data["original"], data["bound_original_view"]
    fields = ("epoch", "lr", "adam_beta1", "train_loss", "inner_val_loss", "inner_val",
              "patience_counter", "saved_best")
    checks = dict(forward_bitwise=original_report["forward_bitwise"],
        epoch_loss_bitwise=all(histories["original"][0][k] == histories["bound_original_view"][0][k] for k in fields),
        state_digest_equal=a["state_sha256"] == b["state_sha256"],
        model_state_equal=nested_equal(a["state_dict"], b["state_dict"]),
        optimizer_state_equal=nested_equal(a["optimizer"], b["optimizer"]),
        scheduler_state_equal=scheduler_equal(a["scheduler"], b["scheduler"]),
        best_last_scores_equal=read(existing/"original/result.json")["outer_test"] ==
                               read(existing/"bound_original_view/result.json")["outer_test"])
    checked_ref(original_report["source_plan"])
    checked_ref(original_report["feature_manifest"])
    checked_ref(original_report["identity_view"])
    report = copy.deepcopy(original_report)
    report.update(checks=checks, **checks)
    report.update(passed=all(checks.values()), extra_optimizer_steps=0,
        review_of=dict(path=str((existing/"equivalence.json").resolve()), sha256=sha256(existing/"equivalence.json")),
        checker_sha256=sha256(Path(__file__)),
        scheduler_comparison="exact __func__ identity + every numeric state field; bound instance address is not numeric state",
        scheduler_states={name:scheduler_metadata(d["scheduler"]) for name,d in data.items()},
        original_failed_check_retained=True)
    output.mkdir(parents=True, exist_ok=False)
    write_new(output/"equivalence.json", report)
    if not report["passed"]:
        raise AssertionError("Existing numerical parity review failed")
    return report



if __name__ == "__main__":
    p=argparse.ArgumentParser()
    for name in ("plan","features","out"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--task", default="reentrancy_node")
    a=p.parse_args()
    run(a.plan,a.features,a.out,a.task)
