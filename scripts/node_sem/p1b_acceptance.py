"""NS-P1b CPU acceptance only; never a formal training entry.

r4 adapter reference: scripts/node_sem/adapter.py at 792ebeed.
Source SHA256: 1a434bb9048c2bb5dba7d54ca5638555ab8d4a6f0346b234dc99240b77a9895e
r4 initialization reference: scripts/node_sem/init.py at 792ebeed.
Source SHA256: 72a21d088308ca05d9765d50bc1387e2746a6d67f435237136d2123e4105c0d6
The historical algorithm is reconstructed ONLY for the requested pre-fit
scale diagnostic: no token norm and seeded normal_(0, .02). r5 is production.
All fits import the frozen trainer; S0 reuses the approved equivalence helper.
"""
import argparse
import copy
import gc
import json
from pathlib import Path
import time
import traceback
import numpy as np
import torch
from torch import nn

from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from scripts.DFG.dfg_v2.benchmark_v2.input_guard import FitInputGuard
from scripts.DFG.dfg_v2.benchmark_v2.trainer import fit
from scripts.DFG.dfg_v2.experiment.init import parameter_seed
from scripts.DFG.dfg_v2.attention_probe import _relation, _attention_summary
from scripts.DFG.dfg_v2.tasks import read_labels
from scripts.DFG.experiments.common import seed_all, tensor_digest
from scripts.labeling_v2.safe_graph import read_graph
from . import execution, init
from .adapter import NodeSemAdapter
from .carrier import write_carrier
from .checkpoint_io import load_checked
from .feature_spec import FeatureSpec
from .model import make_nodesem_model
from .equivalence import _one_fit, compare_fits

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scripts/node_sem/artifacts/ns_p1b"
OLD = ROOT / "scripts/node_sem/artifacts/ns_p1_equivalence/acceptance_revision1/batch/plan.json"


class R4Adapter(NodeSemAdapter):
    """Diagnostic-only old forward, with no norm registered on its owner."""
    def forward(self, inp):
        return self.token_projection(self.pooled_tokens(inp))


def save_initial(model, spec, job, out, historical_r4=False):
    state, sha = init.initial_state(model, spec, job["task_id"], 0, "G3R", job["initial"])
    if historical_r4:
        name = "nodesem_shared.token_bag.weight"
        generator = torch.Generator(device="cpu")
        generator.manual_seed(parameter_seed(job["seeds"]["constructor"], name,
            [job["task_id"], 0, "G3R", spec.digest()]))
        state[name].normal_(0, .02, generator=generator)
        state[name][0].zero_()
        sha = tensor_digest(state)
    payload = dict(kind="untrained_initial", optimizer_steps=0,
        task_id=job["task_id"], fold=0, seed=1, profile="G3R",
        constructor_seed=job["seeds"]["constructor"], fit_seed=job["seeds"]["fit"],
        feature_spec_sha256=spec.digest(), state_dict=state, state_sha256=sha,
        initialization_version="nodesem-semantic-initialization-v1" if historical_r4 else init.VERSION,
        diagnostic_only=historical_r4)
    if out.exists():
        raise FileExistsError("Never overwrite an initial state")
    with out.open("xb") as stream:
        torch.save(payload, stream)
    reference = dict(ref(out), state_sha256=sha)
    write(out.with_suffix(".json"), dict(reference=reference,
        kind="untrained_initial", optimizer_steps=0,
        initialization_version=payload["initialization_version"],
        diagnostic_only=historical_r4, source=job["initial"]))
    return reference


def r4_model(job, spec):
    seed_all(job["seeds"]["constructor"])
    model = make_nodesem_model("node", job["graph"], "G3R", spec, job["config"],
                               device="cpu", task_id=job["task_id"])
    model.adapt_ws = nn.ModuleList([
        R4Adapter(spec, ntype, model.nodesem_shared, model.hidden_size)
        for ntype, idx in sorted(model.ntypes_dict.items(), key=lambda item: item[1])])
    del model.nodesem_shared["token_norm"]
    return model


def prepare():
    old = execution.load(OLD, mode="verify")
    matches = [j for j in old["jobs"] if (j["task_id"], j["fold"], j["seed"], j["profile"])
               == ("reentrancy_node", 0, 1, "G3R")]
    if len(matches) != 1:
        raise ValueError("Required source job missing")
    job = copy.deepcopy(matches[0])
    spec_value = read(checked(job["spec"]))
    spec_value.update(name="S1", token_mode="embed_pool", fusion="concat")
    spec = FeatureSpec.from_json(spec_value)
    write(OUT / "S1.json", spec.to_json())
    carried = write_carrier(spec, job["task_id"], read_graph(checked(job["graph"])),
                            OUT / "s1_carrier")
    seed_all(job["seeds"]["constructor"])
    model = make_nodesem_model("node", job["graph"], "G3R", spec, job["config"],
                               "cpu", job["task_id"])
    initial = save_initial(model, spec, job, OUT / "s1_r5_initial.pt")
    state = load_checked(initial)
    model.load_state_dict(state["state_dict"])
    del model, state
    gc.collect()
    historical = r4_model(job, spec)
    r4 = save_initial(historical, spec, job, OUT / "s1_r4_initial.pt", True)
    del historical
    gc.collect()
    s1 = copy.deepcopy(job)
    s1.update(spec=ref(OUT / "S1.json"), spec_sha256=spec.digest(), reuse_8h=False,
        feature_view=carried["manifest"], feature_npz=carried["data"],
        h8_initial=job["initial"], initial=initial)
    s1.pop("receipt")
    plan = execution.create(OUT / "batch", dict(
        source_h8_plan=old["source_h8_plan"], jobs=[job, s1],
        final_server_intent=old["final_server_intent"]), dict(
        execution_authorized=False, scope="cpu_equivalence",
        user_request="NS-P1b: CPU scale-only diagnostics; S0 old/new two epochs; S1 one-epoch smoke. No formal or GPU fits.",
        checked_checkpoint_authorization=ref(ROOT / "scripts/node_sem/artifacts/ns_p1_initial_digests/authorization.json")))
    write(OUT / "acceptance_plan.json", dict(
        batch=ref(OUT / "batch/plan.json"), old_plan=ref(OLD),
        r4_initial=r4, r5_initial=initial,
        scripts={name: ref(ROOT / name)["sha256"] for name in (
            "scripts/node_sem/p1b_acceptance.py", "scripts/node_sem/equivalence.py")},
        formal_fits=0, cpu_fits=3, epochs=[2, 2, 1], gpu=False,
        scale_uses_labels_or_metrics=False, r5_decision_predates_all_measurements=True))
    write(OUT / "acceptance_plan.seal.json", dict(plan=ref(OUT / "acceptance_plan.json")))
    return plan


def context():
    seal = read(OUT / "acceptance_plan.seal.json")
    accepted = read(checked(seal["plan"]))
    for name, sha in accepted["scripts"].items():
        checked(dict(path=str(ROOT / name), sha256=sha))
    plan_path = checked(accepted["batch"])
    plan = execution.load(plan_path, mode="execute")
    return accepted, plan_path, plan


def distribution(value):
    value = value.detach().cpu().float().reshape(-1)
    if not torch.isfinite(value).all():
        raise ValueError("Nonfinite scale diagnostic")
    return dict(count=value.numel(), mean=float(value.mean()),
                std=float(value.std(unbiased=False)),
                abs_p99=float(np.quantile(value.abs().numpy(), .99)))


def probe(model):
    model.eval()
    before = tensor_digest(model.state_dict())
    layer = model.gcs[0]
    summary = dict(h0={}, first_layer_before_norm={}, first_layer_after_norm={},
                   attention=[], score_or_label_access=False)
    handles = []
    def at_layer(module, args):
        graph, h = args
        summary["h0"] = {ntype: distribution(value) for ntype, value in h.items()}
        summary["h0_global"] = distribution(torch.cat(list(h.values()), dim=0))
        with graph.local_scope():
            for canonical in graph.canonical_etypes:
                trace = _relation(module, graph, h, canonical)
                item = _attention_summary(trace, None)
                item.pop("targets")  # retain aggregate evidence, not huge per-edge logs
                summary["attention"].append(item)
    handles.append(layer.register_forward_pre_hook(at_layer))
    for ntype, index in model.ntypes_dict.items():
        def norm_hook(module, args, output, ntype=ntype):
            summary["first_layer_before_norm"][ntype] = distribution(args[0])
            summary["first_layer_after_norm"][ntype] = distribution(output)
        handles.append(layer.norms[index].register_forward_hook(norm_hook))
    try:
        with torch.no_grad():
            output = model()
            if not torch.isfinite(output).all():
                raise ValueError("Nonfinite eval output")
    finally:
        for handle in handles:
            handle.remove()
    assert tensor_digest(model.state_dict()) == before
    summary.update(state_sha256=before, parameters=sum(p.numel() for p in model.parameters()),
                   no_optimizer=True, actual_device="cpu")
    return summary


def scale():
    accepted, path, plan = context()
    report = dict(passed=False, decision_fixed_before_measurement=True,
                  labels_read=False, metrics_read=False, profiles={})
    for mode in ("S0", "S1_r4", "S1_r5"):
        job = plan["jobs"][0 if mode == "S0" else 1]
        if mode == "S1_r4":
            model = r4_model(plan["jobs"][0], execution._spec(job))
            initial = accepted["r4_initial"]
            model.load_state_dict(load_checked(initial)["state_dict"], strict=True)
        else:
            model = execution.construct(plan, job, "cpu")
            initial = job["initial"]
        report["profiles"][mode] = dict(probe(model), initial=initial)
        print("Scale probe complete: " + mode, flush=True)
        del model
        gc.collect()
    r5 = report["profiles"]["S1_r5"]
    report["r5_h0_range_passed"] = all(
        .05 <= item["std"] <= 5 for item in r5["h0"].values())
    report["passed"] = report["r5_h0_range_passed"]
    write(OUT / "init_scale.json", report)
    if not report["passed"]:
        raise RuntimeError("r5 h0 standard deviation outside [0.05, 5]; stop")
    return report


def s0():
    accepted, path, plan = context()
    if not read(OUT / "init_scale.json")["passed"]:
        raise ValueError("Scale gate not passed")
    source = h8.load(checked(plan["source_h8_plan"]))
    job = plan["jobs"][0]
    old_job = execution.historical_job(source, job)
    folder = OUT / "s0_cpu"
    folder.mkdir(exist_ok=False)
    old = _one_fit("historical", source, plan, old_job, job, folder / "historical")
    new = _one_fit("nodesem", source, plan, old_job, job, folder / "nodesem")
    report = compare_fits(old, new)
    report.update(cpu_fits=2, epochs_per_fit=2, actual_device="cpu", formal_fit=False)
    write(OUT / "s0_equivalence.json", report)
    print("S0 CPU equivalence PASS", flush=True)
    return report


def smoke():
    accepted, path, plan = context()
    if not read(OUT / "s0_equivalence.json")["passed"]:
        raise ValueError("S0 gate not passed")
    job = plan["jobs"][1]
    model = execution.construct(plan, job, "cpu")
    common = load_checked(job["h8_initial"])["state_dict"]
    assert all(torch.equal(value, common[key]) for key, value in model.state_dict().items()
               if key.startswith(("gcs.", "classify.")))
    del common
    gradients = {}
    handles = []
    def record_gradient(name):
        def hook(grad):
            gradients[name] = dict(finite=bool(torch.isfinite(grad).all()),
                                   l1=float(grad.abs().sum()), nonzero=int(torch.count_nonzero(grad)))
        return hook
    for name, parameter in model.named_parameters():
        if name.startswith(("adapt_ws.", "nodesem_shared.")):
            handles.append(parameter.register_hook(record_gradient(name)))
    cfg = copy.deepcopy(job["config"])
    cfg["maximum_training_epochs"] = 1
    binding, parts = execution.binding_parts(plan, job, model, config=cfg)
    labels = read_labels(job["labels"])
    seed_all(job["seeds"]["fit"])
    folder = OUT / "s1_cpu_smoke"
    try:
        with FitInputGuard(model, binding, parts, labels) as guard:
            result = fit(model, guard.wrap_parts(), "node", labels, cfg, folder, binding,
                         model.original_graph_node_ids, job["support"])
            guard.finish()
            write(folder / "validation_performance.json", guard.summary())
    finally:
        for handle in handles:
            handle.remove()
    expected = [name for name, _ in model.named_parameters()
                if name.startswith(("adapt_ws.", "nodesem_shared."))]
    passed = set(gradients) == set(expected) and all(
        x["finite"] and x["l1"] > 0 for x in gradients.values())
    history = [json.loads(line) for line in (folder / "history.jsonl").read_text().splitlines()]
    assert len(history) == 1 and all(np.isfinite(history[0][k]) for k in ("train_loss", "inner_val_loss"))
    report = dict(passed=passed, formal_fit=False, actual_device="cpu",
        epochs=1, effective_config=cfg, only_override="maximum_training_epochs",
        common_initial_exact=True, gradients=gradients,
        finite_loss=True, train_loss=history[0]["train_loss"],
        val_loss=history[0]["inner_val_loss"], initialization_version=init.VERSION,
        checkpoint_roundtrip_exact=result["checkpoint_roundtrip_exact"])
    write(OUT / "s1_smoke.json", report)
    if not passed:
        raise RuntimeError("S1 train gradients missing/zero/nonfinite; stop")
    print("S1 one-epoch CPU smoke PASS", flush=True)
    return report


def archive():
    plan = execution.load(OLD, mode="verify")
    checks = []
    for index, job in enumerate(plan["jobs"], 1):
        accepted = execution.verify_one(OLD, plan, job)
        checks.append(dict(job_id=execution.job_id(job), passed=accepted["audit"]["passed"],
                           current_code_equality=accepted["current_code_equality"],
                           receipt=job["receipt"]))
        if index % 10 == 0:
            print("Historical read-only {}/60".format(index), flush=True)
    write(OUT / "historical_verify.json", dict(
        passed=True, old_plan=ref(OLD), jobs=checks, count=len(checks),
        current_code_equality="not_required", source_h8_runtime_checked=True))
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "scale", "s0", "smoke", "archive"))
    args = parser.parse_args()
    torch.set_num_threads(2)
    if torch.cuda.is_initialized():
        raise RuntimeError("CPU-only acceptance")
    failed = OUT / (args.stage + ".failure.json")
    started = OUT / (args.stage + ".started.json")
    if failed.exists() or started.exists():
        raise FileExistsError("Stage already attempted; no automatic retry")
    write(started, dict(stage=args.stage, started_unix=time.time(), driver=ref(Path(__file__)),
                        actual_device="cpu"))
    try:
        globals()[args.stage]()
    except Exception as error:
        write(failed, dict(error=repr(error), traceback=traceback.format_exc(), automatic_retry=False))
        raise


if __name__ == "__main__":
    main()
