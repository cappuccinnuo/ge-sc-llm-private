"""One isolated CPU/eval/no_grad forward per profile; no loss or optimizer."""
import argparse
import hashlib
import itertools
import resource
import time
from pathlib import Path

import torch
from scripts.DFG.integration.io import checked, sha256, write_json
from scripts.labeling_v2.safe_graph import read_graph
from . import ENV_SOURCE, ENV_FLOW
from .model import make_model, validate_registration


def tensor_hash(value):
    array = value.detach().cpu().contiguous().numpy()
    return hashlib.sha256(array.tobytes()).hexdigest()


def compare_rows(rows, captured, signatures, tolerance=1e-6):
    result = {}
    for key in sorted({r["key"] for r in rows}):
        members = [r for r in rows if r["key"] == key]
        pairs, zeros, maximum = 0, [], 0.0
        for a, b in itertools.combinations(members, 2):
            difference = float((captured[a["row"]] - captured[b["row"]]).abs().max())
            maximum = max(maximum, difference)
            pairs += 1
            if difference <= tolerance:
                same = signatures.get(a["row"]) == signatures.get(b["row"])
                zeros.append(dict(files=[a["file"], b["file"]], max_abs_diff=difference,
                    reason="identical_incoming_relation_source_representations" if same else
                           "equal_within_tolerance_despite_distinct_inputs; aggregate_collision_or_symmetry_not_resolved"))
        result[key] = dict(files=len(members), pairs=pairs, max_abs_diff=maximum,
                           zero_or_within_tolerance_pairs=zeros,
                           no_comparison_reason="single_file_only" if len(members) < 2 else None)
    return result


def run(graph_path, expected_sha, task, profile, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    if profile not in ("G3", "G3R"):
        raise ValueError("Expected G3 or G3R")
    start = time.monotonic()
    torch.set_num_threads(2)
    torch.manual_seed(1)
    path = checked(graph_path, expected_sha)
    graph = read_graph(path)
    model = make_model(task, graph, profile, device="cpu")
    model.eval()
    schema = validate_registration(model)
    rows = [dict(file=d["source_file"], key=d["code"], row=d["node_hetero_id"])
            for _, d in model.nx_graph.nodes(data=True) if d["node_type"] == ENV_SOURCE]
    layers = []
    handles = []
    def hook(module, args, result):
        if ENV_SOURCE not in result:
            layers.append(dict(env_rows=0, keys={}))
            return
        state = result[ENV_SOURCE].detach().cpu()
        if not bool(torch.isfinite(state).all()):
            raise AssertionError("Nonfinite environment layer")
        previous = args[1]
        signatures = {}
        for row in rows:
            incoming = []
            for canonical in model.symmetrical_global_graph.canonical_etypes:
                if canonical[2] != ENV_SOURCE:
                    continue
                src, _ = model.symmetrical_global_graph.in_edges(row["row"], etype=canonical)
                values = sorted(tensor_hash(previous[canonical[0]][int(i)]) for i in src)
                incoming.append((canonical, values))
            signatures[row["row"]] = repr(incoming)
        compared = compare_rows(rows, state, signatures)
        if profile == "G3" and any(x["max_abs_diff"] > 1e-6 for x in compared.values()):
            raise AssertionError("G3 same-key environment differs across files")
        layers.append(dict(env_rows=len(rows), all_finite=True, keys=compared))
    for layer in model.gcs:
        handles.append(layer.register_forward_hook(hook))
    forward_start = time.monotonic()
    try:
        with torch.no_grad():
            output_tensor = model() if task == "node" else model(sorted(
                {d["source_file"] for _,d in graph.nodes(data=True)}))[0]
    finally:
        for handle in handles:
            handle.remove()
    forward_seconds = time.monotonic() - forward_start
    if not bool(torch.isfinite(output_tensor).all()):
        raise AssertionError("Nonfinite model output")
    if any(p.grad is not None for p in model.parameters()):
        raise AssertionError("Unexpected gradient in real-data forward")
    canonical = [dict(canonical=list(c),edges=model.symmetrical_global_graph.num_edges(c))
                 for c in sorted(model.etypes_dict) if c[1] in (ENV_FLOW,"REV_ENV_FLOW")]
    if sha256(path) != expected_sha:
        raise AssertionError("Input graph changed")
    result = dict(status="accepted", profile=profile, task=task, graph_sha256=expected_sha,
        schema=schema, canonical=canonical, input_width=model.in_size,
        parameters=sum(p.numel() for p in model.parameters()),
        output_shape=list(output_tensor.shape), output_all_finite=True,
        layers=layers, forward_seconds=forward_seconds,
        process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0,
        total_seconds=time.monotonic()-start, device="cpu", seed=1, eval=True,
        no_grad=True, loss_computed=False, backward_executed=False, optimizer_steps=0,
        training_executed=False, tolerance=1e-6,
        comparison="within profile, same key across files; no cross-profile causal score comparison")
    write_json(output,result)
    print(profile,task,result["output_shape"],"finite",round(forward_seconds,3),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph",required=True)
    p.add_argument("--sha256",required=True)
    p.add_argument("--task",choices=("node","contract"),required=True)
    p.add_argument("--profile",choices=("G3","G3R"),required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    run(a.graph,a.sha256,a.task,a.profile,a.output)


if __name__=="__main__":
    main()
