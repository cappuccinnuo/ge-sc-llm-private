"""Prompt8D intervention worker; frozen inference path, no optimizer.
Adapted from diagnostics8c/inference.py::run_worker, SHA256 9966835bd8f4eb705def78be530a4083d21f26c1ee38007f58e3fac15b990172.
Only token-view assembly differs: sealed precomputed vectors, exact source/node
identities, and only outer-test rows. Model assembly/restore/eval stay unchanged.
"""
import argparse
import hashlib
import time
from pathlib import Path
from scripts.DFG.dfg_v2.diagnostics8c.common import read, write_new, attempt_for, indexed, checked_plan
from scripts.DFG.dfg_v2.diagnostics8c.inference import assert_archive_equal

def run_worker(plan_path, task_id, fold, profile, output, prepared_path, mode, gate_path=None, gate_only=False):
    import torch
    from scripts.DFG.experiments.common import seed_all, tensor_digest
    from scripts.DFG.integration.io import sha256, checked
    from scripts.DFG.dfg_v2.experiment.run import _prepared, _move_model
    from scripts.DFG.dfg_v2.experiment.checkpoint import restore_checkpoint
    from scripts.DFG.dfg_v2.model import make_model
    from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
    from scripts.DFG.dfg_v2.tasks import checked_ref
    from scripts.DFG.dfg_v2.tokens import TokenEncoder
    from scripts.DFG.dfg_v2 import AUX_NODE_TYPES

    if gate_only:
        raise ValueError("Use the frozen 8C unmodified gate; this worker is intervention-only")
    started = time.monotonic()
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    plan = checked_plan(plan_path)
    job = dict(task_id=task_id, fold=fold, seed=1, profile=profile,
               layer_impl=plan["layer_impl"])
    if job not in plan["jobs"] or plan["tasks"][task_id]["record"]["task"] != "node":
        raise ValueError("Unknown frozen node job")
    if not gate_only:
        if gate_path is None:
            raise ValueError("Unmodified archive parity gate required")
        gate = read(gate_path)
        if not gate.get("gate_only") or not gate.get("archive_parity", {}).get("passed"):
            raise ValueError("Unmodified archive parity gate failed")
        if gate["plan_sha256"] != sha256(plan_path):
            raise ValueError("Gate plan differs")
    task, info, entry = _prepared(plan, job)
    config = task["config"]
    torch.set_num_threads(config["threads"])
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; no silent CPU fallback")
    seed_all(info["seeds"]["constructor"])
    model = make_model("node", checked_ref(entry["graph"]), profile, "cpu",
        hidden_size=config["hidden_size"], layers=config["layers"], heads=config["heads"],
        reducer=plan["reducer"], layer_impl=plan["layer_impl"])
    _move_model(model, "cuda:0")
    attempt = attempt_for(plan_path, job)
    receipt = read(attempt / "receipt.json")
    if (receipt.get("status") != "complete" or receipt.get("job") != job
            or receipt.get("plan_sha256") != sha256(plan_path)):
        raise ValueError("Checkpoint receipt identity differs")
    for name in ("binding.json", "outer_test_predictions.json"):
        checked(attempt / name, receipt["artifacts"][name])
    binding = read(attempt / "binding.json")
    payload = restore_checkpoint(attempt / "best.pt", model, binding, receipt["artifacts"]["best.pt"])
    state_digest = tensor_digest(model.state_dict())
    del payload
    model.eval()
    part = DfgV2Supervision(model, "node", info["split"]["outer_test_files"])
    archived = read(attempt / "outer_test_predictions.json")
    identities = [(model.nx_graph.nodes[n]["source_file"], model.original_graph_node_ids[n])
                  for n in part.full_ids]
    if set(identities) != set(indexed(archived)):
        raise ValueError("Prediction sample identities differ")
    report = dict(job=job, plan_sha256=sha256(plan_path),
                  graph=entry["graph"], checkpoint_sha256=receipt["artifacts"]["best.pt"],
                  checkpoint_state_sha256=state_digest, optimizer_steps=0,
                  gate_only=gate_only,
                  implementation_sha256=sha256(Path(__file__)),
                  feature_recipe=task["record"]["feature"],
                  gate_sha256=sha256(gate_path) if gate_path else None, task="diagnostic identifier intervention, not retraining")
    if gate_only:
        with torch.no_grad():
            logits = part.forward(model)
            pred = logits.argmax(1).cpu().tolist()
            prob = logits.softmax(1)[:, 1].cpu().tolist()
        report["archive_parity"] = assert_archive_equal(
            archived, pred, prob, [i[1] for i in identities], [i[0] for i in identities])
        report["seconds"] = time.monotonic() - started
        write_new(output, report)
        if not report["archive_parity"]["passed"]:
            raise AssertionError("Unmodified archived predictions are not bitwise equal")
        return report

    from .prepared import load_view, vector_sha256
    import numpy as np
    view, vectors, prepared_ref = load_view(prepared_path, task_id, mode, plan_path)
    prepared_rows = {(row["file"], row["original_graph_node_id"]): row for row in view["rows"]}
    mappings = {file: view["mappings"][file] for file in part.files}
    source_refs = {file: task["record"]["sources"][file] for file in part.files}
    for ref in source_refs.values():
        checked_ref(ref)
    report.update(intervention=mode, prepared=prepared_ref)
    unused_mappings, unused_source_refs = {}, {}
    graph = model.symmetrical_global_graph
    features = {typ: graph.nodes[typ].data["inp"].detach().clone() for typ in graph.ntypes}
    edges = {c: tuple(t.detach().clone() for t in graph.edges(etype=c, order="eid"))
             for c in graph.canonical_etypes}
    changed, allowed_rows, cache = [], {typ:set() for typ in graph.ntypes}, {}
    for n in part.full_ids:
        attrs = model.nx_graph.nodes[n]
        typ = attrs["node_type"]
        if typ in AUX_NODE_TYPES:
            raise AssertionError("Auxiliary node in supervision")
        code = attrs["code"]
        identity = (attrs["source_file"], model.original_graph_node_ids[n])
        from .renaming import rewrite_node
        new_code, edits = rewrite_node(code, mappings[identity[0]])
        row = prepared_rows.get(identity)
        if bool(edits) != (row is not None):
            raise ValueError("Prepared view omitted/added an expected rewritten node")
        if row is None:
            continue
        if (row["code_after_sha256"] != hashlib.sha256(new_code.encode()).hexdigest()
                or row["replacements"] != len(edits)):
            raise ValueError("Prepared rewritten code differs from bound mapping")
        if row["code_before_sha256"] != hashlib.sha256(code.encode()).hexdigest():
            raise ValueError("Prepared node code identity differs")
        if row["node_type"] != typ or row["source_sha256"] != source_refs[identity[0]]["sha256"]:
            raise ValueError("Prepared node type/source identity differs")
        local = attrs["node_hetero_id"]
        if vector_sha256(features[typ][local].cpu().numpy()) != row["original_vector_sha256"]:
            raise ValueError("Original token vector differs from prepared frozen input")
        vector = torch.from_numpy(vectors[row["vector_row"]].copy()).to(features[typ].device)
        graph.nodes[typ].data["inp"][local] = vector
        allowed_rows[typ].add(local)
        changed.append(dict(row, feature_changed=not torch.equal(vector, features[typ][local])))
    for typ in graph.ntypes:
        mask = torch.ones(graph.num_nodes(typ),dtype=torch.bool,device=model.device)
        if allowed_rows[typ]:
            mask[list(allowed_rows[typ])] = False
        if not torch.equal(features[typ][mask], graph.nodes[typ].data["inp"][mask]):
            raise AssertionError("Unmodified node features changed")
    with torch.no_grad():
        logits = part.forward(model)
        if not bool(torch.isfinite(logits).all()):
            raise ValueError("Nonfinite inference logits")
        pred = logits.argmax(1).cpu().tolist()
        prob = logits.softmax(1)[:, 1].cpu().tolist()
    if tensor_digest(model.state_dict()) != state_digest:
        raise AssertionError("Inference changed model weights")
    for canonical, before in edges.items():
        if not all(torch.equal(a,b) for a,b in zip(before,graph.edges(etype=canonical, order="eid"))):
            raise AssertionError("Inference changed graph edges")
    lookup = indexed(archived)
    rows = []
    for identity, prediction, probability in zip(identities, pred, prob):
        original = lookup[identity]
        rows.append(dict(file=identity[0],original_graph_node_id=identity[1],
            source_sha256=source_refs[identity[0]]["sha256"],target=original["target"],
            original_best=original["best"],original_probability=original["best_positive_probability"],
            renamed_best=prediction,renamed_probability=probability))
    report.update(changed_nodes=changed, changed_code_count=len(changed),
        changed_feature_count=sum(x["feature_changed"] for x in changed),
        changed_predictions=sum(r["original_best"] != r["renamed_best"] for r in rows),
        changed_probabilities=sum(r["original_probability"] != r["renamed_probability"] for r in rows),
        mappings=mappings,source_refs=source_refs,tokenizer=view["tokenizer"],
        unchanged_features_verified=True,graph_edges_unchanged=True,
        frozen_nx_attributes_untouched=True,weights_unchanged=True,
        predictions=rows,seconds=time.monotonic()-started,
        peak_allocated_bytes=torch.cuda.max_memory_allocated(),
        peak_reserved_bytes=torch.cuda.max_memory_reserved())
    write_new(output, report)
    print("%s/%d/%s: renamed %d nodes, changed %d predictions" %
          (task_id,fold,profile,len(changed),report["changed_predictions"]), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("plan", "task", "profile", "out", "prepared", "gate"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--fold", type=int, required=True)
    parser.add_argument("--mode", choices=("B_full", "B_matched", "C_matched"), required=True)
    a = parser.parse_args()
    run_worker(a.plan, a.task, a.fold, a.profile, a.out, a.prepared, a.mode, a.gate)
