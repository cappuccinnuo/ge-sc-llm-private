"""CPU-only A/B/C message mechanism probe; never a detection accuracy experiment.

A = original HCG with saved untrained shared parameters.
B = enhanced schema, same initial, only added relation_msg slices set to zero.
C = enhanced schema and full saved untrained parameters.
B-A first-layer aggregates isolate the cross-relation mean denominator effect.
Later layers also propagate earlier changes. C-B is a fixed-initial-state
intervention, not evidence of trained utility or semantic causal benefit.
"""
import argparse
import collections
import csv
import gc
import json
import time
from pathlib import Path
import numpy as np
import torch
from scripts.DFG.experiments.common import sha256, tensor_digest, read_json, write_json
from scripts.DFG.experiments.guard_extension.model import make_model, semantic_state, FORWARD_RELATIONS
from scripts.DFG.experiments.runtime import assert_disconnected_files
from scripts.DFG.graph_audit import frozen

ROOT = Path(__file__).resolve().parents[4]
DEFAULT = ROOT / "scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1"
OUTPUT = ROOT / "scripts/DFG/experiments/artifacts/integration_release_v1/diagnostics"
TASKS = ("reentrancy_author_contract", "access_control_author_contract",
         "reentrancy_author_node", "access_control_author_node")
VERSION = "untrained-canonical-message-probe-v1"


def checked(path, expected, protected):
    path = Path(path).resolve()
    actual = sha256(path)
    if actual != expected:
        raise ValueError("Frozen file changed: " + str(path))
    protected[str(path)] = actual
    return path


def load_initial(info, variant, protected):
    ref = info["initialization"][variant]
    path = checked(ref["path"], ref["sha256"], protected)
    record = torch.load(str(path), map_location="cpu")
    expected = dict(kind="untrained_initial", optimizer_steps=0, task_id=info["task_id"],
                    fold=0, variant=variant, fit_seed=info["fit_seed"],
                    graph_sha256=info["graphs"][variant]["sha256"])
    if any(record.get(k) != v for k, v in expected.items()):
        raise ValueError("Untrained initial identity mismatch")
    actual = tensor_digest(record["state_dict"])
    if actual != record["state_sha256"] or actual != ref["state_sha256"]:
        raise ValueError("Untrained tensor digest mismatch")
    return record["state_dict"]


def silence_added_messages(model):
    """In-memory intervention only. Do not alter graph/schema/attention banks."""
    with torch.no_grad():
        for canonical, idx in model.etypes_dict.items():
            if canonical[1] in FORWARD_RELATIONS:
                for layer in model.gcs:
                    layer.relation_msg[idx].zero_()


def capture_forward(model, task):
    """Observe original HGT a_linear input (= aggregate t), without replacing it."""
    model.eval()
    captures, handles = {}, []
    before = tensor_digest(model.state_dict())
    for layer_index, layer in enumerate(model.gcs):
        for typ, idx in model.ntypes_dict.items():
            def capture(_module, args, layer_index=layer_index, typ=typ):
                captures[(layer_index, typ)] = args[0].detach().cpu().clone()
            handles.append(layer.a_linears[idx].register_forward_pre_hook(capture))
        def hidden(_module, _args, result, layer_index=layer_index):
            for typ, value in result.items():
                captures[("hidden", layer_index, typ)] = value.detach().cpu().clone()
        handles.append(layer.register_forward_hook(hidden))
    try:
        files = sorted({d["source_file"] for _, d in model.nx_graph.nodes(data=True)})
        with torch.no_grad():
            output = model() if task == "node" else model(files)[0]
    finally:
        for handle in handles:
            handle.remove()
    if tensor_digest(model.state_dict()) != before or any(p.grad is not None for p in model.parameters()):
        raise AssertionError("Read-only forward altered weights or produced gradients")
    result = {"logits": output.detach().cpu().numpy(), "files": files}
    for layer_index in range(model.num_layers):
        agg = torch.zeros(len(model.nx_graph), model.hidden_size)
        hidden_rows = torch.zeros_like(agg)
        for typ, rows in model.node_ids_dict.items():
            agg[rows] = captures[(layer_index, typ)]
            hidden_rows[rows] = captures[("hidden", layer_index, typ)]
        result["aggregate_" + str(layer_index)] = agg.numpy()
        result["hidden_" + str(layer_index)] = hidden_rows.numpy()
    return result


def topology(model):
    schema = list(model.etypes_dict)
    counts = collections.Counter(c[2] for c in schema)
    new_incident, old_incident = set(), set()
    for c in schema:
        _, targets = model.symmetrical_global_graph.edges(etype=c)
        target_rows = model.node_ids_dict[c[2]]
        store = new_incident if c[1] in FORWARD_RELATIONS else old_incident
        store.update(target_rows[i] for i in targets.tolist())
    return dict(schema=[list(c) for c in schema], incoming_canonical=dict(counts),
                added_target_nodes=sorted(new_incident), old_target_nodes=sorted(old_incident))


def verify_common(a, b):
    if not set(a) <= set(b) or any(not torch.equal(a[k], b[k]) for k in a):
        raise ValueError("Shared semantic initial tensors differ")
    return dict(shared_tensors=len(a), shared_digest=tensor_digest(a), exact=True)


def first_layer_scaling(a, b, rows, top_a, top_b):
    def ratio(typ):
        old = top_a["incoming_canonical"].get(typ, 0)
        new = top_b["incoming_canonical"].get(typ, 0)
        if not new:
            if old:
                raise ValueError("Enhanced schema lost an incoming canonical relation")
            return 1.0  # both have no aggregate; no denominator was changed
        return old / new
    ratios = np.array([ratio(d["node_type"]) for d in rows], dtype=np.float32)
    expected = a["aggregate_0"] * ratios[:, None]
    actual = b["aggregate_0"]
    error = np.abs(actual - expected)
    valid = np.allclose(actual, expected, atol=2e-4, rtol=2e-5)
    if not valid:
        raise AssertionError("B-A first-layer change is not the expected canonical mean scaling")
    return dict(verified=True, max_abs_error=float(error.max()), atol=2e-4, rtol=2e-5,
                ratios=ratios.tolist(), explanation="only first-layer aggregate has this isolated scaling identity")


def write_csv(path, rows):
    with Path(path).open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader(); writer.writerows(rows)


def summarize_nodes(rows, data, top_a, top_c, ratios, split):
    incoming = set(top_c["added_target_nodes"])
    old_incoming = set(top_c["old_target_nodes"])
    records = []
    for idx, d in enumerate(rows):
        row = dict(node_id=idx, original_graph_node_id=d["original_graph_node_id"], file=d["source_file"],
                   node_type=d["node_type"], partition="train" if d["source_file"] in split["train_files"] else "val",
                   has_new_incoming=idx in incoming, has_old_incoming=idx in old_incoming,
                   denominator_changed=ratios[idx] != 1.0,
                   no_new_incoming_denominator_changed=idx not in incoming and ratios[idx] != 1.0,
                   old_message_ratio=ratios[idx])
        for name, x, y in (("B_minus_A", data["B"], data["A"]), ("C_minus_B", data["C"], data["B"]),
                           ("C_minus_A", data["C"], data["A"])):
            for layer in range(len([k for k in x if k.startswith("aggregate_")])):
                for kind in ("aggregate", "hidden"):
                    delta = x[kind + "_" + str(layer)][idx] - y[kind + "_" + str(layer)][idx]
                    row[name + "_" + kind + str(layer) + "_l2"] = float(np.linalg.norm(delta))
        records.append(row)
    grouped = collections.defaultdict(list)
    for row in records:
        grouped[(row["file"], row["node_type"], row["partition"])].append(row)
    summary = []
    for key, values in sorted(grouped.items()):
        row = dict(file=key[0], node_type=key[1], partition=key[2], nodes=len(values))
        for name in ("has_new_incoming", "has_old_incoming", "denominator_changed", "no_new_incoming_denominator_changed"):
            row[name] = sum(int(x[name]) for x in values)
        row["old_message_ratio"] = values[0]["old_message_ratio"]
        for name in values[0]:
            if name.endswith("_l2"):
                row[name + "_mean"] = float(np.mean([x[name] for x in values]))
                row[name + "_max"] = max(x[name] for x in values)
        summary.append(row)
    return records, summary


def run_task(info, base_info, protected, destination):
    started = time.monotonic()
    if info["fold"] != 0 or base_info["fold"] != 0 or info["task_id"] != base_info["task_id"]:
        raise ValueError("Only matching frozen fold0 is allowed")
    for key in ("config", "split", "feature", "label_version", "labels_sha256", "fit_seed"):
        if info[key] != base_info[key]:
            raise ValueError("Frozen task inputs differ: " + key)
    checked(info["labels_path"], info["labels_sha256"], protected)
    labels = read_json(info["labels_path"])
    label_inventory = dict(records=len(labels), used_for_forward=False)
    config = info["config"]
    data, states, tops, semantics, attrs = {}, {}, {}, {}, {}
    identities = {}
    for mode in ("A", "B", "C"):
        owner, variant = (base_info, "HCG") if mode == "A" else (info, "HCG_DDG_GUARD")
        graph = checked(owner["graphs"][variant]["path"], owner["graphs"][variant]["sha256"], protected)
        state = load_initial(owner, variant, protected)
        with torch.random.fork_rng(devices=[]):
            model = make_model(info["task"], graph, "cpu", hidden_size=config["hidden_size"],
                               layers=config["layers"], heads=config["heads"])
        model.load_state_dict(state, strict=True)
        assert_disconnected_files(model.nx_graph)
        attrs[mode] = frozen(list(model.nx_graph.nodes(data=True)))
        if mode != "A" and attrs[mode] != attrs["A"]:
            raise ValueError("Node order/attributes/labels/features changed")
        semantic = {k: v.detach().cpu().clone() for k, v in semantic_state(model).items()}
        if mode == "A":
            semantics["A"] = semantic
            rows = [dict(d, original_graph_node_id=model.original_graph_node_ids[n]) for n, d in model.nx_graph.nodes(data=True)]
        else:
            identities[mode] = verify_common(semantics["A"], semantic)
        states[mode] = dict(saved_untrained_tensor_sha256=tensor_digest(state), optimizer_steps=0)
        if mode == "B":
            silence_added_messages(model)
        states[mode]["forward_tensor_sha256"] = tensor_digest(model.state_dict())
        states[mode]["intervention"] = "zero new relation_msg slices, same schema" if mode == "B" else "none"
        tops[mode] = topology(model)
        data[mode] = capture_forward(model, info["task"])
        del model, state, semantic
        gc.collect()
    if tops["B"] != tops["C"] or states["B"]["saved_untrained_tensor_sha256"] != states["C"]["saved_untrained_tensor_sha256"]:
        raise AssertionError("B and C do not share schema/initial")
    scaling = first_layer_scaling(data["A"], data["B"], rows, tops["A"], tops["C"])
    records, groups = summarize_nodes(rows, data, tops["A"], tops["C"], scaling["ratios"], info["split"])
    destination.mkdir()
    write_csv(destination / "node_changes.csv", records)
    write_csv(destination / "file_type_changes.csv", groups)
    logit_rows = []
    for i in range(len(data["A"]["logits"])):
        row = dict(file=data["A"]["files"][i] if info["task"] == "contract" else rows[i]["source_file"],
                   node_id="" if info["task"] == "contract" else i,
                   original_graph_node_id="" if info["task"] == "contract" else rows[i]["original_graph_node_id"])
        for mode in ("A", "B", "C"):
            row[mode + "_logit0"] = float(data[mode]["logits"][i,0])
            row[mode + "_logit1"] = float(data[mode]["logits"][i,1])
            row[mode + "_margin"] = float(data[mode]["logits"][i,1] - data[mode]["logits"][i,0])
        logit_rows.append(row)
    write_csv(destination / "logits_no_accuracy.csv", logit_rows)
    arrays = {mode + "_" + k: v for mode, d in data.items() for k, v in d.items() if isinstance(v, np.ndarray)}
    np.savez_compressed(str(destination / "observations.npz"), **arrays)
    result = dict(task_id=info["task_id"], fold=0, source="saved untrained initial states", device="cpu",
                  optimizer_steps=0, model_eval=True, new_training=False, labels=label_inventory,
                  common_initial=identities, state_digests=states, topology=tops, first_layer_scaling=scaling,
                  nodes=len(rows), new_incoming_nodes=sum(x["has_new_incoming"] for x in records),
                  no_new_incoming_denominator_changed=sum(x["no_new_incoming_denominator_changed"] for x in records),
                  no_new_incoming_aggregate_changed=sum(x["no_new_incoming_denominator_changed"] and x["B_minus_A_aggregate0_l2"]>1e-6 for x in records),
                  seconds=time.monotonic()-started, config_source=info["config"],
                  interpretation="not accuracy, not trained reliance; second-layer deltas include propagation; no label used by probe")
    write_json(destination / "report.json", result)
    return {k:v for k,v in result.items() if k not in ("topology", "config_source", "first_layer_scaling")}


def run(guard_batch=DEFAULT, output=OUTPUT):
    output, guard_batch = Path(output).resolve(), Path(guard_batch).resolve()
    allowed = ROOT / "scripts/DFG/experiments/artifacts"
    if allowed not in output.parents or output.exists():
        raise ValueError("Output must be a new diagnostic directory below experiment artifacts")
    protected = {}
    plan_path = guard_batch / "plan.json"
    seal_path = guard_batch / "plan.seal.json"
    seal = read_json(seal_path)
    checked(seal_path, sha256(seal_path), protected)
    plan = read_json(checked(plan_path, seal["sha256"], protected))
    refs = [r for r in plan["tasks"] if r["fold"] == 0]
    if len(refs) != 4 or {r["task_id"] for r in refs} != set(TASKS):
        raise ValueError("Expected exactly four frozen fold0 tasks")
    output.mkdir(parents=True)
    torch.set_num_threads(2)
    summary = []
    for task in TASKS:
        ref = next(r for r in refs if r["task_id"] == task)
        info = read_json(checked(ref["manifest"], ref["sha256"], protected))
        base = read_json(checked(info["baseline_task_manifest"], info["baseline_task_sha256"], protected))
        checked(info["source_guard_manifest"], info["source_guard_manifest_sha256"], protected)
        summary.append(run_task(info, base, protected, output/task))
        print("VERIFIED", task, "no-training A/B/C", flush=True)
    for path, digest in protected.items():
        checked(path, digest, {})
    result = dict(version=VERSION, status="complete", scope="four task fold0 saved untrained states only",
                  tasks=summary, protected_files=protected, old_files_unchanged=True,
                  no_gpu=True, no_training=True, no_accuracy_claim=True,
                  normalized_graph_rebuild_equivalence="verified separately by integration release; this probe uses old frozen graphs",
                  limitations=["Untrained message mechanism does not quantify trained predictive benefit", "No inference edge-deletion accuracy test", "B-A layer0 isolates denominator; later layers include propagation", "New relation parameter counts remain a separate experimental confound"])
    write_json(output/"summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guard-batch", type=Path, default=DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.guard_batch, args.output)

if __name__ == "__main__":
    main()
