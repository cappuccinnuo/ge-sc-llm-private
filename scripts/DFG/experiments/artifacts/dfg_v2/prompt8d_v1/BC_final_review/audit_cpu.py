"""Read-only CPU acceptance of Prompt8D B/C preparation and completed jobs."""
import collections
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
os.environ.update(CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
                  TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
import numpy as np
import torch
from scripts.DFG.dfg_v2.diagnostics8c.common import read, write_new, attempt_for, indexed
from scripts.DFG.integration.io import checked, sha256
from scripts.DFG.dfg_v2.tasks import checked_ref
from scripts.DFG.dfg_v2.tokens import TokenEncoder
from scripts.DFG.dfg_v2.diagnostics8d.renaming import (
    position_audit, token_ids, token_count, rewrite_node, marker_names,
    matched_selection, identifiers, EXCLUDED_NAMES)
from scripts.labeling_v2.safe_graph import read_graph

OUT = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1"
DEST = OUT / "BC_final_review"
CODE = ROOT / "scripts/DFG/dfg_v2/diagnostics8d"
started = time.monotonic()
refs = {}
def bind(path):
    path = Path(path).resolve()
    value = dict(path=str(path), sha256=sha256(path))
    if str(path) in refs and refs[str(path)] != value:
        raise AssertionError("Previously checked bytes changed: " + str(path))
    refs[str(path)] = value
    return value
def read_bound(path):
    bind(path)
    return read(path)
def read_ref(ref):
    checked_ref(ref)
    return read_bound(ref["path"])
def h(text):
    return hashlib.sha256(text.encode()).hexdigest()
def vh(vector):
    return hashlib.sha256(np.asarray(vector, dtype=np.float32).tobytes()).hexdigest()
def encode_full(encoder, code):
    ids = token_ids(encoder, code)
    value = np.zeros(512, dtype=np.float32)
    value[:min(512, len(ids))] = ids[:512]
    return ids, value

record = read_bound(OUT / "BC_run/execution_plan.json")
seal = read_bound(OUT / "BC_run/execution_plan.seal.json")
assert seal["sha256"] == sha256(OUT / "BC_run/execution_plan.json")
assert record["training_count"] == record["optimizer_steps"] == 0
assert len(record["jobs"]) == 300
for name, expected in record["code"].items():
    assert bind(CODE / name)["sha256"] == expected
for key in ("source_plan", "prepared", "gate", "verification", "approval",
            "old_worker", "current_environment_gate"):
    checked_ref(record[key])
    bind(record[key]["path"])
plan = read_ref(record["source_plan"])
prepared = read_ref(record["prepared"])
bundle_summary = read_ref(prepared["bundles"])
view_cache = {}
preparation_counts = collections.Counter()
preparation_task = {}
for task_id, entry in prepared["tasks"].items():
    task = plan["tasks"][task_id]
    info = read_ref(task["prepared"]["0/1"])
    graph = read_graph(checked_ref(info["profiles"]["G0"]["graph"]))
    bind(info["profiles"]["G0"]["graph"]["path"])
    encoder = TokenEncoder(task["record"]["feature"])
    sources = {}
    bundles = {}
    for file, source_ref in task["record"]["sources"].items():
        source_path = checked_ref(source_ref)
        bind(source_path)
        sources[file] = source_path.read_text(encoding="utf8")
    for file, bundle_ref in bundle_summary["tasks"][task_id]["files"].items():
        bundle = read_ref(bundle_ref)
        assert bundle["source_sha256"] == h(sources[file])
        selection = matched_selection(sources[file], encoder)
        assert selection == bundle["matching"]
        bundles[file] = bundle
        original_names = {name for name, _, _ in identifiers(sources[file])}
        for mode, view in bundle["views"].items():
            mapping = view["mapping"]
            assert len(mapping.values()) == len(set(mapping.values()))
            assert not original_names.intersection(mapping.values())
            assert not EXCLUDED_NAMES.intersection(mapping.values())
            if mode == "B_full":
                assert list(mapping) == marker_names(sources[file])
            elif mode == "B_matched":
                assert list(mapping) == selection["marker_names"]
            else:
                assert list(mapping) == selection["nonmarker_names"]
            for name, candidate in mapping.items():
                assert token_count(encoder, name) == token_count(encoder, candidate)
        preparation_counts["checked_file_bundles"] += 1
    counts = collections.Counter()
    for mode, view_ref in entry["views"].items():
        view = read_ref(view_ref["manifest"])
        checked_ref(view_ref["data"])
        bind(view_ref["data"]["path"])
        vectors = np.load(view_ref["data"]["path"], allow_pickle=False)["vectors"]
        assert vectors.dtype == np.float32 and vectors.shape == (len(view["rows"]), 512)
        rows = {(row["file"], row["original_graph_node_id"]): row for row in view["rows"]}
        assert len(rows) == len(view["rows"])
        assert set(view["mappings"]) == set(task["record"]["sources"])
        for n, attrs in graph.nodes(data=True):
            file, code = attrs["source_file"], attrs["code"]
            mapping = view["mappings"][file]
            if file not in bundles:
                assert mapping == {}
            else:
                assert mapping == bundles[file]["views"][mode]["mapping"]
            new, edits = rewrite_node(code, mapping)
            identity = (file, n)
            assert bool(edits) == (identity in rows)
            if not edits:
                continue
            row = rows[identity]
            before_ids, before = encode_full(encoder, code)
            after_ids, after = encode_full(encoder, new)
            assert np.array_equal(before, np.asarray(attrs["token"], dtype=np.float32))
            assert row["code_before_sha256"] == h(code)
            assert row["code_after_sha256"] == h(new)
            assert len(before_ids) == len(after_ids) == row["before_token_length"] == row["after_token_length"]
            assert position_audit(code, mapping, encoder) == row["position_proof"]
            assert row["original_vector_sha256"] == vh(before)
            assert row["renamed_vector_sha256"] == vh(after)
            assert np.array_equal(after, vectors[row["vector_row"]])
            counts[mode + "_independently_reencoded_rows"] += 1
            counts[mode + "_unchanged_after_512_clipping"] += int(np.array_equal(before, after))
            counts[mode + "_beyond512_rows"] += len(before_ids) > 512
        view_cache[(task_id, mode)] = (view, rows, vectors)
    preparation_task[task_id] = dict(counts)
    print("CPU preparation rechecked", task_id, dict(counts), flush=True)

# Freeze the completed-status snapshot; running jobs without success receipts are not evidence.
statuses = sorted((OUT / "BC_run").glob("*/status/*.json"))
checked_jobs = []
non_solidifi = collections.Counter()
for status_path in statuses:
    status = read_bound(status_path)
    if status["returncode"] != 0:
        raise AssertionError("Failed inference status: " + str(status_path))
    report = read_ref(status["result"])
    job, mode = status["job"], status["mode"]
    assert report["job"] == job and report["intervention"] == mode
    assert report["implementation_sha256"] == record["code"]["inference.py"]
    assert report["plan_sha256"] == record["source_plan"]["sha256"]
    assert report["prepared"]["manifest"] == record["prepared"]
    assert report["optimizer_steps"] == 0
    assert all(report[k] is True for k in (
        "unchanged_features_verified", "graph_edges_unchanged",
        "frozen_nx_attributes_untouched", "weights_unchanged"))
    task = plan["tasks"][job["task_id"]]
    info = read_ref(task["prepared"]["%d/%d" % (job["fold"], job["seed"])])
    outer = set(info["split"]["outer_test_files"])
    assert set(report["mappings"]) == set(report["source_refs"]) == outer
    view, prepared_rows, vectors = view_cache[(job["task_id"], mode)]
    assert report["mappings"] == {file: view["mappings"][file] for file in outer}
    attempt = attempt_for(record["source_plan"]["path"], job)
    receipt = read_bound(attempt / "receipt.json")
    archived = read_bound(attempt / "outer_test_predictions.json")
    assert sha256(attempt / "outer_test_predictions.json") == receipt["artifacts"]["outer_test_predictions.json"]
    binding = read_bound(attempt / "binding.json")
    checkpoint = attempt / "best.pt"
    assert bind(checkpoint)["sha256"] == report["checkpoint_sha256"] == receipt["artifacts"]["best.pt"]
    payload = torch.load(str(checkpoint), map_location="cpu")
    assert payload["state_sha256"] == report["checkpoint_state_sha256"]
    assert payload["binding"] == binding
    del payload
    assert report["graph"] == info["profiles"][job["profile"]]["graph"]
    old_rows = indexed(archived)
    result_rows = indexed(report["predictions"])
    assert set(old_rows) == set(result_rows)
    expected_changed = {identity: row for identity, row in prepared_rows.items() if identity[0] in outer}
    changed = {(r["file"], r["original_graph_node_id"]): r for r in report["changed_nodes"]}
    assert set(changed) == set(expected_changed)
    assert report["changed_code_count"] == len(changed)
    for identity, expected in expected_changed.items():
        assert {k:v for k,v in changed[identity].items() if k != "feature_changed"} == expected
        assert changed[identity]["feature_changed"] == (expected["original_vector_sha256"] != expected["renamed_vector_sha256"])
    assert report["changed_feature_count"] == sum(r["feature_changed"] for r in changed.values())
    for identity, old in old_rows.items():
        current = result_rows[identity]
        assert current["target"] == old["target"]
        assert current["original_best"] == old["best"]
        assert current["original_probability"] == old["best_positive_probability"]
        assert current["source_sha256"] == task["record"]["sources"][identity[0]]["sha256"]
        if not view["mappings"][identity[0]]:
            # No renamed input in this file; graph constructor forbids cross-file edges.
            assert current["renamed_best"] == current["original_best"]
            assert current["renamed_probability"] == current["original_probability"]
            non_solidifi[mode + "_unchanged_no_mapping_rows"] += 1
    checked_jobs.append(dict(job=job, mode=mode, report=status["result"],
                             status=bind(status_path),
                             checkpoint_state_sha256=report["checkpoint_state_sha256"]))
print("CPU completed report checks", len(checked_jobs), flush=True)
result = dict(
    status="passed_for_completed_snapshot", blockers=[],
    checked_preparation=dict(preparation_counts), per_task=preparation_task,
    completed_jobs=len(checked_jobs), jobs=checked_jobs,
    unchanged_no_mapping_rows=dict(non_solidifi),
    live_batch_not_claimed_complete=True, model_forwards=0, training_count=0,
    seconds=time.monotonic() - started,
    checked_refs=list(refs.values()),
    review_findings=[
        "Interventions are correctly named and SHA-bound; B_full uses all markers; matched views use approved source-order token-length matched subsets.",
        "CPU reencoding independently agrees with prepared 512-float rows; full token lengths and per-occurrence token positions are invariant, with all outside-token IDs unchanged.",
        "Frozen graph construction rejects cross-file edges. Worker changes only original HCG outer-test input rows; env_source and all other rows are equality-checked unchanged.",
        "Archived best checkpoint file hash, receipt, binding, graph identity and state digest agree for every completed snapshot report; no optimizer or backward path is called.",
        "Completed report no-mapping files retain exact predictions and probabilities.",
    ],
    limitations=[
        "B_full versus old idN changes both neutral lexical values and positional preservation; their difference is not a pure causal estimate of positional effects.",
        "B_matched and C_matched match unique identifier count and isolated token-length histograms, not occurrences, affected nodes, semantic roles or perturbed feature dose.",
        "Neutral candidates are fixed and deterministic but lexical token-ID numeric values still change. Inputs are 512 float tokenizer IDs, not CodeT5 hidden embeddings.",
        "Testing-only renamed inputs are distribution-shift diagnostics, not retraining, independent test generalization, or proofs of semantic vulnerability understanding.",
        "C eligibility is explicit declaration-backed with conservative builtin exclusions; rewrites are filewise lexical spellings, not a compiler-verified alpha conversion.",
        "The runtime boolean frozen_nx_attributes_untouched is supported by code ownership/deepcopy and absence of NX mutations, not a separate post-forward NX digest in the worker.",
        "No runtime files or existing artifacts were modified; this review snapshot does not claim remaining running jobs are complete."
    ],
)
# Also verify all bound files remained stable during this read-only audit.
for item in result["checked_refs"]:
    assert sha256(item["path"]) == item["sha256"], item["path"]
write_new(DEST / "audit.json", result)
