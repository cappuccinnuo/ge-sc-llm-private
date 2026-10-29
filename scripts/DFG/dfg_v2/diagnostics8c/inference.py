"""Prompt 8C identifier intervention: frozen best checkpoints, no fitting.

Only DGL input rows for renamed outer-test HCG nodes are replaced in memory.
The graph, targets, NX attributes, parameter values and all other features stay
frozen. Every worker is a fresh process. No optimizer or training API is used.
"""
import argparse
import hashlib
import re
import time
from pathlib import Path

from .common import read, write_new, attempt_for, indexed, row_identity, checked_plan

IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
LEXEMES = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_$][A-Za-z0-9_$]*')
MARKERS = ("txorigin", "re_ent")


def identifiers(source):
    """Solidity ASCII identifiers outside strings/comments, in byte order."""
    for match in LEXEMES.finditer(source):
        token = match.group()
        if IDENTIFIER.fullmatch(token):
            yield token, match.start(), match.end()


def replacement_map(source):
    tokens = list(identifiers(source))
    used = {word for word, _, _ in tokens}
    mapping, number = {}, 0
    for word, _, _ in tokens:
        if word in mapping or not any(marker in word for marker in MARKERS):
            continue
        while "id%d" % number in used:
            number += 1
        mapping[word] = "id%d" % number
        used.add(mapping[word])
        number += 1
    return mapping


def serialized_view(code):
    """Logical view with exact offsets into pydot-quoted original code.

    Decode one serialization layer for lexical recognition only. Replacement
    patches original identifier spans, leaving every other byte unchanged.
    Unknown escapes remain literal; malformed Solidity is not repaired.
    """
    wrapped = len(code) >= 2 and code[0] == code[-1] == '"'
    start, stop = (1, len(code) - 1) if wrapped else (0, len(code))
    chars, offsets = [], []
    escapes = {"n": "\n", "r": "\r", '"': '"'}
    i = start
    while i < stop:
        if wrapped and code[i] == "\\" and i + 1 < stop and code[i + 1] in escapes:
            chars.append(escapes[code[i + 1]])
            offsets.append((i, i + 2))
            i += 2
        else:
            chars.append(code[i])
            offsets.append((i, i + 1))
            i += 1
    return "".join(chars), offsets


def rewrite_code(code, mapping):
    text, offsets = serialized_view(code)
    edits = []
    for word, a, b in identifiers(text):
        if any(marker in word for marker in MARKERS) and word not in mapping:
            raise ValueError("Node identifier absent from bound source: " + word)
        if word in mapping:
            lo, hi = offsets[a][0], offsets[b - 1][1]
            if code[lo:hi] != word:
                raise ValueError("Identifier serialization is not an exact lexical span")
            edits.append((lo, hi, word, mapping[word]))
    output, end = [], 0
    for lo, hi, old, new in edits:
        output.extend((code[end:lo], new))
        end = hi
    output.append(code[end:])
    return "".join(output), edits


def assert_archive_equal(rows, predictions, probabilities, original_ids, files):
    """Archive has probabilities, not logits: require float32 bitwise equality."""
    import numpy as np
    if len(rows) != len(predictions) or len(rows) != len(original_ids):
        raise ValueError("Archive size differs")
    lookup = indexed(rows)
    expected = [(file, node) for file, node in zip(files, original_ids)]
    if set(lookup) != set(expected) or len(set(expected)) != len(expected):
        raise ValueError("Archive identities differ")
    saved = [lookup[key] for key in expected]
    exact_predictions = predictions == [r["best"] for r in saved]
    observed = np.asarray(probabilities, dtype=np.float32)
    archived = np.asarray([r["best_positive_probability"] for r in saved], dtype=np.float32)
    exact_probabilities = bool(np.array_equal(observed.view(np.uint32), archived.view(np.uint32)))
    return dict(passed=bool(exact_predictions and exact_probabilities),
                argmax_bitwise=bool(exact_predictions),
                probability_float32_bitwise=exact_probabilities,
                maximum_probability_difference=float(np.max(np.abs(observed - archived))),
                comparison="archived argmax and float32 positive probabilities; logits not archived")


def run_worker(plan_path, task_id, fold, profile, output, gate_path=None, gate_only=False):
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

    encoder = TokenEncoder(task["record"]["feature"])
    mappings, source_refs = {}, {}
    for file in part.files:
        ref = task["record"]["sources"][file]
        source = checked_ref(ref).read_text(encoding="utf-8")
        mappings[file] = replacement_map(source)
        source_refs[file] = ref
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
        new_code, edits = rewrite_code(code, mappings[attrs["source_file"]])
        if not edits:
            continue
        local = attrs["node_hetero_id"]
        if code not in cache:
            cache[code] = encoder(code)
        expected = torch.from_numpy(cache[code]).to(features[typ].device)
        if not torch.equal(expected, features[typ][local]):
            raise ValueError("Re-encoded unchanged node differs from frozen feature recipe")
        if new_code not in cache:
            cache[new_code] = encoder(new_code)
        vector = torch.from_numpy(cache[new_code]).to(features[typ].device)
        graph.nodes[typ].data["inp"][local] = vector
        allowed_rows[typ].add(local)
        changed.append(dict(file=attrs["source_file"],
            source_sha256=source_refs[attrs["source_file"]]["sha256"],
            original_graph_node_id=model.original_graph_node_ids[n],
            code_before_sha256=hashlib.sha256(code.encode()).hexdigest(),
            code_after_sha256=hashlib.sha256(new_code.encode()).hexdigest(),
            replacements=len(edits), feature_changed=not torch.equal(vector, features[typ][local])))
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
        mappings=mappings,source_refs=source_refs,tokenizer=encoder.provenance,
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
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan",required=True)
    parser.add_argument("--task",required=True)
    parser.add_argument("--fold",required=True,type=int)
    parser.add_argument("--profile",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--gate")
    parser.add_argument("--gate-only",action="store_true")
    args=parser.parse_args()
    run_worker(args.plan,args.task,args.fold,args.profile,args.out,args.gate,args.gate_only)
