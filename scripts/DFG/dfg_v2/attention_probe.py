"""Prompt 5.0: read-only attention diagnostics for the frozen G3R HGT.

Formula source: sco_models/model_hgt.py::HGTLayer.forward
SHA256: 4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947
The hook recomputes selected relation attention/messages with the original
parameters and DGL operators. It does not replace the model forward, mutate
parameters, normalize features, calculate a loss or construct an optimizer.
"""
import argparse
import hashlib
import math
import resource
import time
from pathlib import Path

import numpy as np
import torch
import dgl.function as fn
from dgl.nn.functional import edge_softmax

from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from scripts.labeling_v2.safe_graph import read_graph
from . import ENV_SOURCE
from .model import make_model, validate_registration


HGT_SHA256 = "4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947"
SOURCE_ROOT = Path(__file__).resolve().parents[3]
REPRODUCTION_TOLERANCE = 1e-6
RECOMPUTE_TOLERANCE = 1e-5
CONTROLS = frozenset(("READS_STATE", "next_line"))


def tensor_hash(value):
    array = value.detach().cpu().contiguous().numpy()
    return hashlib.sha256(array.tobytes()).hexdigest()


def _distribution(values):
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    return dict(samples=int(values.size),
        fraction_ge_099=float(np.mean(values >= .99)) if values.size else None,
        median=float(np.median(values)) if values.size else None,
        minimum=float(values.min()) if values.size else None,
        maximum=float(values.max()) if values.size else None)


def _relation(layer, graph, h, canonical):
    """Exact frozen k/q/v, relation transforms, dst softmax and sum."""
    src_type, _, dst_type = canonical
    sub = graph[canonical]
    eid = layer.edge_dict[canonical]
    k = layer.k_linears[layer.node_dict[src_type]](h[src_type]).view(
        -1, layer.n_heads, layer.d_k)
    v = layer.v_linears[layer.node_dict[src_type]](h[src_type]).view(
        -1, layer.n_heads, layer.d_k)
    q = layer.q_linears[layer.node_dict[dst_type]](h[dst_type]).view(
        -1, layer.n_heads, layer.d_k)
    k = torch.einsum("bij,ijk->bik", k, layer.relation_att[eid])
    v = torch.einsum("bij,ijk->bik", v, layer.relation_msg[eid])
    value_field = "v_%d" % eid
    sub.srcdata["k"], sub.dstdata["q"], sub.srcdata[value_field] = k, q, v
    sub.apply_edges(fn.v_dot_u("q", "k", "t"))
    logits = sub.edata.pop("t").sum(-1) * layer.relation_pri[eid] / layer.sqrt_dk
    attention = edge_softmax(sub, logits, norm_by="dst")
    sub.edata["t"] = attention.unsqueeze(-1)
    sub.update_all(fn.u_mul_e(value_field, "t", "m"), fn.sum("m", "_probe_message"))
    messages = sub.dstdata["_probe_message"].clone()
    src, dst = sub.edges(order="eid")
    return dict(canonical=canonical, source_rows=src, target_rows=dst,
                logits=logits, attention=attention, values=v, messages=messages)


def _attention_summary(trace, row_identity):
    src, dst, attention = (trace[k] for k in ("source_rows", "target_rows", "attention"))
    targets, all_values, multiple_values = [], [], []
    # A destination with one incoming edge has max weight one by definition.
    # Report it separately from evidence of attention concentration.
    grouped = {}
    for edge, target in enumerate(dst.tolist()):
        grouped.setdefault(target, []).append(edge)
    for target, edges in sorted(grouped.items()):
        maximum = attention[edges].max(dim=0).values.detach().cpu().tolist()
        item = dict(target_row=target, in_degree=len(edges), max_weight_by_head=maximum)
        if row_identity is not None:
            item.update(row_identity[target])
        targets.append(item)
        all_values.extend(maximum)
        if len(edges) >= 2:
            multiple_values.extend(maximum)
    logits = trace["logits"]
    return dict(canonical=list(trace["canonical"]), edges=int(src.numel()),
        active_targets=len(targets), targets=targets,
        max_weight_distribution=_distribution(all_values),
        multi_neighbor_max_weight_distribution=_distribution(multiple_values),
        logits_abs_mean=float(logits.abs().mean()) if logits.numel() else None,
        logits_abs_max=float(logits.abs().max()) if logits.numel() else None)


def recompute(layer, graph, h, target_type=ENV_SOURCE):
    """Return reconstructed target rows and selected relation evidence.

    All incoming canonicals to target_type are included in cross-relation mean,
    including a registered relation with zero degree for a particular row.
    The graph, h and layer parameters remain unchanged.
    """
    if layer.training or torch.is_grad_enabled():
        raise ValueError("Attention diagnostic requires eval and torch.no_grad")
    if target_type not in graph.ntypes:
        raise ValueError("Diagnostic target node type is absent")
    selected = [c for c in graph.canonical_etypes
                if c[2] == target_type or c[1] in CONTROLS]
    traces = {}
    with graph.local_scope():
        for canonical in selected:
            traces[canonical] = _relation(layer, graph, h, canonical)
        incoming = [c for c in selected if c[2] == target_type]
        if incoming:
            graph.multi_update_all({
                c: (fn.u_mul_e("v_%d" % layer.edge_dict[c], "t", "m"), fn.sum("m", "t"))
                for c in incoming}, cross_reducer="mean")
            message = graph.nodes[target_type].data["t"].view(-1, layer.out_dim)
        else:
            message = torch.zeros(graph.num_nodes(target_type), layer.out_dim,
                                  device=h[target_type].device, dtype=h[target_type].dtype)
        index = layer.node_dict[target_type]
        alpha = torch.sigmoid(layer.skip[index])
        pre_norm = layer.drop(layer.a_linears[index](message))
        pre_norm = pre_norm * alpha + h[target_type] * (1 - alpha)
        reconstructed = layer.norms[index](pre_norm) if layer.use_norm else pre_norm
    return reconstructed, traces


def assert_reconstruction(reconstructed, actual, tolerance=RECOMPUTE_TOLERANCE):
    if reconstructed.shape != actual.shape or not torch.isfinite(reconstructed).all():
        raise AssertionError("Invalid reconstructed HGT output")
    maximum = float((reconstructed - actual).abs().max()) if actual.numel() else 0.0
    if not math.isfinite(maximum) or maximum > tolerance:
        raise AssertionError("HGT reconstruction differs: %r > %r" % (maximum, tolerance))
    return maximum


def _winner(trace, row, head, previous):
    cache = trace.setdefault("_winner_cache", {})
    if (row, head) in cache:
        return dict(cache[(row, head)]) if cache[(row, head)] is not None else None
    edges = (trace["target_rows"] == row).nonzero(as_tuple=False).view(-1)
    if not edges.numel():
        cache[(row, head)] = None
        return None
    weights = trace["attention"][edges, head]
    maximum = weights.max()
    tied = edges[weights == maximum]
    # First edge is only a deterministic representative of all exact ties.
    edge = int(tied[0])
    source = int(trace["source_rows"][edge])
    tied_sources = trace["source_rows"][tied].tolist()
    hashes = [tensor_hash(previous[int(v)]) for v in tied_sources]
    chosen_h = tensor_hash(previous[source])
    chosen_value = tensor_hash(trace["values"][source, head])
    all_sources = trace["source_rows"][edges].tolist()
    same_h = [tensor_hash(previous[int(v)]) == chosen_h for v in all_sources]
    same_value = [tensor_hash(trace["values"][int(v), head]) == chosen_value for v in all_sources]
    record = dict(source_row=source, max_weight=float(maximum),
        tied_edges=int(tied.numel()), tie_source_rows=tied_sources,
        all_tie_source_h_identical=len(set(hashes)) == 1,
        source_h_sha256=chosen_h, value_head_sha256=chosen_value,
        top_equivalent_h_group_edges=sum(same_h),
        top_equivalent_value_group_edges=sum(same_value),
        top_equivalent_h_group_attention_mass=float(weights[torch.tensor(same_h, dtype=torch.bool)].sum()),
        top_equivalent_value_group_attention_mass=float(weights[torch.tensor(same_value, dtype=torch.bool)].sum()))
    cache[(row, head)] = record
    return dict(record)


def compare_pair(pair, traces, h, actual, hub_rows, node_rows, heads):
    key = pair["key"]
    files = pair["files"]
    a, b = [hub_rows[(f, key)] for f in files]
    difference = float((actual[a] - actual[b]).abs().max())
    reproduced = difference <= REPRODUCTION_TOLERANCE
    relations = []
    all_h_equal, all_v_equal, saturated = True, True, True
    h_group_concentrated = v_group_concentrated = True
    for canonical, trace in sorted(traces.items()):
        if canonical[2] != ENV_SOURCE:
            continue
        left_present = bool((trace["target_rows"] == a).any())
        right_present = bool((trace["target_rows"] == b).any())
        record = dict(canonical=list(canonical), left_support=left_present,
                      right_support=right_present, heads=[])
        if not left_present and not right_present:
            record["status"] = "neither_has_support"
            relations.append(record)
            continue
        if left_present != right_present:
            all_h_equal = all_v_equal = saturated = False
            h_group_concentrated = v_group_concentrated = False
        for head in range(heads):
            winners = [_winner(trace, row, head, h[canonical[0]]) for row in (a, b)]
            same_h = all(winners) and winners[0]["source_h_sha256"] == winners[1]["source_h_sha256"]
            same_v = all(winners) and winners[0]["value_head_sha256"] == winners[1]["value_head_sha256"]
            concentrated = all(winners) and all(w["max_weight"] >= .99 for w in winners)
            all_h_equal &= bool(same_h)
            all_v_equal &= bool(same_v)
            saturated &= bool(concentrated)
            h_group_concentrated &= bool(all(winners) and all(
                w["top_equivalent_h_group_attention_mass"] >= .99 for w in winners))
            v_group_concentrated &= bool(all(winners) and all(
                w["top_equivalent_value_group_attention_mass"] >= .99 for w in winners))
            for winner in winners:
                if winner is not None:
                    winner["source_identity"] = node_rows[canonical[0]][winner["source_row"]]
            msg_diff = float((trace["messages"][a, head] - trace["messages"][b, head]).abs().max())
            record["heads"].append(dict(head=head, winners=winners,
                highest_neighbor_h_exact=bool(same_h), highest_value_head_exact=bool(same_v),
                both_max_weight_ge_099=bool(concentrated),
                actual_relation_message_max_abs_diff=msg_diff))
        relations.append(record)
    return dict(layer_index=pair["layer_index"], key=key, files=files,
        previous_measured_max_abs_diff=pair["measured_max_abs_diff"],
        measured_max_abs_diff=difference, original_zero_reproduced=reproduced,
        analysis_valid_for_original_pair=reproduced,
        own_previous_h_max_abs_diff=float((h[ENV_SOURCE][a] - h[ENV_SOURCE][b]).abs().max()),
        every_supported_head_highest_neighbor_h_exact=all_h_equal,
        every_supported_head_highest_value_exact=all_v_equal,
        every_supported_head_both_max_weight_ge_099=saturated,
        every_supported_head_equivalent_h_group_mass_ge_099=h_group_concentrated,
        every_supported_head_equivalent_value_group_mass_ge_099=v_group_concentrated,
        relations=relations,
        interpretation=("reproduced_observation; highest_neighbor_and_attention_evidence_not_a_complete_causal_proof"
                        if reproduced else "original_zero_not_reproduced; do_not_attribute_previous_pair"))


def _inputs(bundle_dir, review_dir):
    bundle_dir, review_dir = Path(bundle_dir).resolve(), Path(review_dir).resolve()
    tid = bundle_dir.name
    receipt_path = bundle_dir.parent / "receipt.json"
    receipt = read_json(receipt_path)
    if receipt.get("status") != "accepted" or receipt.get("training_executed") is not False:
        raise ValueError("Expected accepted nontraining L3 receipt")
    bundle_path = checked(bundle_dir / "manifest.json", receipt["task_manifests"][tid])
    bundle = read_json(bundle_path)
    if bundle.get("layer") != "L3" or set(bundle.get("profiles", ())) != {"G3", "G3R"}:
        raise ValueError("Expected frozen L3 graph bundle")
    gp = checked(bundle["graph"]["path"], bundle["graph"]["sha256"])
    previous_path = checked(bundle_dir / "G3R_forward.json", bundle["files"]["G3R_forward"])
    previous = read_json(previous_path)
    if (previous.get("status") != "accepted" or previous.get("seed") != 1
            or previous.get("profile") != "G3R" or previous.get("device") != "cpu"
            or previous.get("eval") is not True or previous.get("no_grad") is not True
            or previous.get("graph_sha256") != bundle["graph"]["sha256"]):
        raise ValueError("Historical forward identity/configuration mismatch")
    code_inputs = {}
    for name in ("sco_models/model_hgt.py", "sco_models/graph_utils.py",
                 "scripts/DFG/dfg_v2/model.py", "scripts/DFG/dfg_v2/model_input.py",
                 "scripts/DFG/dfg_v2/hgt_layer.py"):
        checked(SOURCE_ROOT / name, receipt["runtime"][name])
        code_inputs[name] = receipt["runtime"][name]
    checked(SOURCE_ROOT / "sco_models/model_hgt.py", HGT_SHA256)
    review_receipt = read_json(review_dir / "receipt.json")
    if review_receipt.get("status") != "accepted_static_review_only":
        raise ValueError("Expected accepted Prompt 4 static review")
    review_path = checked(review_dir / (tid + ".json"), review_receipt["files"][tid + ".json"])
    review = read_json(review_path)
    if (review["graph"]["sha256"] != bundle["graph"]["sha256"]
            or review["forward_report"]["sha256"] != sha256(previous_path)):
        raise ValueError("Static review refers to another graph/forward")
    pairs = [p for p in review["previously_unresolved_pairs"]
             if p["classification"] == "distinct_static_inputs_cause_unresolved"]
    identities = {(p["layer_index"], p["key"], tuple(p["files"])) for p in pairs}
    if len(identities) != len(pairs):
        raise ValueError("Duplicate frozen pair identity")
    return gp, previous, pairs, dict(
        task_id=tid, graph_sha256=bundle["graph"]["sha256"],
        bundle_sha256=sha256(bundle_path), L3_receipt_sha256=sha256(receipt_path),
        previous_forward_sha256=sha256(previous_path), review_sha256=sha256(review_path),
        review_receipt_sha256=sha256(review_dir / "receipt.json"), frozen_code=code_inputs)


def run(bundle_dir, review_dir, output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing diagnostic output: " + str(output))
    gp, previous, pairs, inputs = _inputs(bundle_dir, review_dir)
    output.mkdir(parents=True)
    write_json(output / "inputs.json", inputs)
    started = time.monotonic()
    torch.set_num_threads(2)
    torch.manual_seed(previous["seed"])
    graph = read_graph(gp)
    model = make_model(previous["task"], graph, "G3R", device="cpu")
    model.eval()
    if (sum(p.numel() for p in model.parameters()) != previous["parameters"]
            or validate_registration(model) != previous["schema"]
            or model.in_size != previous["input_width"]):
        raise ValueError("Recreated model configuration differs from historical forward")
    node_rows = {typ: [] for typ in model.node_types}
    hub_rows = {}
    for node, attrs in model.nx_graph.nodes(data=True):
        record = dict(model_node_id=node, original_node_id=model.original_graph_node_ids[node],
                      source_file=attrs["source_file"], node_type=attrs["node_type"],
                      code_sha256=hashlib.sha256(attrs.get("code", "").encode("utf8")).hexdigest(),
                      code_preview=attrs.get("code", "")[:200])
        node_rows[attrs["node_type"]].append(record)
        if attrs["node_type"] == ENV_SOURCE:
            hub_rows[(attrs["source_file"], attrs["code"])] = attrs["node_hetero_id"]
    layer_results = []
    def hook(layer, args, actual):
        index = len(layer_results)
        h = args[1]
        reconstructed, traces = recompute(layer, args[0], h)
        error = assert_reconstruction(reconstructed, actual[ENV_SOURCE])
        relation_reports = [_attention_summary(trace, node_rows[canonical[2]])
                            for canonical, trace in sorted(traces.items())]
        selected_pairs = [p for p in pairs if p["layer_index"] == index]
        checked_pairs = [compare_pair(p, traces, h, actual[ENV_SOURCE],
                                      hub_rows, node_rows, layer.n_heads) for p in selected_pairs]
        layer_results.append(dict(layer_index=index,
            input_h_origin="adapt_ws followed by GELU, evaluated once before HGT stack" if index == 0
                           else "preceding HGT layer output; no additional adapt_ws",
            input_h={typ: dict(rows=int(value.shape[0]), width=int(value.shape[1]),
                              abs_mean=float(value.abs().mean()) if value.numel() else 0.0,
                              abs_max=float(value.abs().max()) if value.numel() else 0.0)
                     for typ, value in h.items()},
            reconstructed_output_max_abs_diff=error, relations=relation_reports,
            reviewed_pairs=checked_pairs))
    handles = [layer.register_forward_hook(hook) for layer in model.gcs]
    try:
        forward_start = time.monotonic()
        with torch.no_grad():
            logits = model() if previous["task"] == "node" else model(sorted(
                {d["source_file"] for _, d in graph.nodes(data=True)}))[0]
        elapsed = time.monotonic() - forward_start
    finally:
        for handle in handles:
            handle.remove()
    if list(logits.shape) != previous["output_shape"] or not bool(torch.isfinite(logits).all()):
        raise AssertionError("Output differs in shape or is nonfinite")
    if any(p.grad is not None for p in model.parameters()):
        raise AssertionError("Unexpected gradient")
    if sum(len(l["reviewed_pairs"]) for l in layer_results) != len(pairs):
        raise AssertionError("Frozen pair coverage differs")
    checked(gp, inputs["graph_sha256"])
    all_pairs = [p for layer in layer_results for p in layer["reviewed_pairs"]]
    result = dict(version="dfg-v2-p5-attention-probe-v1", status="accepted",
        inputs=inputs, profile="G3R", seed=1, task=previous["task"], device="cpu",
        effective_model=dict(input_width=model.in_size, hidden_size=model.hidden_size,
            layers=model.num_layers, heads=model.num_heads, reducer=model.dfg_reducer,
            parameters=sum(p.numel() for p in model.parameters())),
        layers=layer_results, frozen_pairs=len(pairs),
        pairs_reproduced=sum(p["original_zero_reproduced"] for p in all_pairs),
        pairs_not_reproduced=sum(not p["original_zero_reproduced"] for p in all_pairs),
        output_shape=list(logits.shape), output_all_finite=True,
        forward_seconds_including_hook=elapsed, total_seconds=time.monotonic()-started,
        process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0,
        model_forward_calls=1, eval=True, no_grad=True, loss_computed=False,
        backward_executed=False, optimizer_steps=0, training_executed=False,
        recompute_tolerance=RECOMPUTE_TOLERANCE, zero_pair_tolerance=REPRODUCTION_TOLERANCE,
        inference_limits=[
            "G0 was not forwarded; controls are READS_STATE and next_line inside G3R only.",
            "Equal highest neighbors alone are not a complete causal attribution.",
            "Duplicate equal representations can split attention across edges; equivalent-group mass is reported for reviewed pairs.",
            "Degree-one destinations have weight one trivially; multi-neighbor statistics are separate.",
            "Initialization diagnostics do not establish trained-model behavior or F1 improvement."],
        probe_source_sha256=sha256(Path(__file__).resolve()))
    write_json(output / "result.json", result)
    write_json(output / "receipt.json", dict(status="accepted", result_sha256=sha256(output/"result.json"),
        inputs_sha256=sha256(output/"inputs.json"), model_forward_calls=1, training_executed=False))
    print(inputs["task_id"], "pairs", len(pairs), "reproduced", result["pairs_reproduced"], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--static-review", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.bundle, args.static_review, args.output)


if __name__ == "__main__":
    main()
