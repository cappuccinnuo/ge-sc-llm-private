"""Read-only final receipt/input verification; no model construction or inference."""
import csv
import hashlib
import json
from pathlib import Path
from scripts.DFG.experiments.stage_i_diagnostics.common import (
    verify_plan, verified_success, job_output,
)

BASE = Path(__file__).resolve().parent
plan = verify_plan(BASE)
plan_sha = hashlib.sha256((BASE / "plan.json").read_bytes()).hexdigest()
assert len(plan["jobs"]) == 60
resources = []
max_probability_error = 0.0
exact_archive_probabilities = 0
for job in plan["jobs"]:
    dest = job_output(BASE, job)
    assert verified_success(dest, plan_sha, job)
    meta = json.loads((dest / "metadata.json").read_text())
    for ck in ("best", "last"):
        audit = json.loads((dest / ck / "audit.json").read_text())
        assert audit["score_role"] == plan["score_role"]
        gate = audit["gates"]
        assert gate == meta["checks"][ck]
        for key in ("wrapper_exact", "restored_native_exact", "weights_unchanged",
                    "parameter_objects_unchanged", "input_unchanged", "no_gradients"):
            assert gate[key] is True, (job, ck, key)
        assert gate["optimizer_steps"] == 0
        assert gate["archive_replay"]["predictions_exact"] is True
        assert gate["archive_replay"]["metrics_match"] is True
        max_probability_error = max(max_probability_error, gate["archive_replay"]["probability_abs_max"])
        exact_archive_probabilities += bool(gate["archive_replay"]["probability_exact"])
        scores = json.loads((dest / ck / "scores.json").read_text())
        assert {x["condition"] for x in scores} == set(plan["conditions"])
        assert len(scores) == len(plan["conditions"])
        assert all(x["score_role"] == plan["score_role"] for x in scores)
        assert set(audit["messages"]) == set(plan["conditions"])
    resource = meta["resource"]
    resources.append(dict(task_id=job["task_id"], fold=job["fold"], variant=job["variant"],
        parameters=resource["parameters"], wall_seconds=resource["wall_seconds"],
        peak_allocated_mib=resource["peak_allocated_bytes"] / 1048576.,
        peak_reserved_mib=resource["peak_reserved_bytes"] / 1048576.,
        minimum_whole_card_free_mib=resource["card"]["minimum_whole_card_free_mib"],
        memory_sampling_errors=len(resource["card"]["errors"])))
assert len(list((BASE / "replays").glob("*/fold_*/*/receipt.json"))) == 60
summary = dict(status="passed", models=60, checkpoints=120, scored_conditions=720,
    optimizer_steps=0, score_role=plan["score_role"],
    exact_archived_probability_checkpoints=exact_archive_probabilities,
    archived_probability_abs_max=max_probability_error,
    sealed_runtime_inputs_and_static_hashes_unchanged=True,
    all_receipts_and_job_identities_verified=True,
    native_and_restored_bitwise_equal=True,
    weights_parameter_objects_graph_labels_features_schema_unchanged=True,
    replay_wall_seconds_sum=sum(x["wall_seconds"] for x in resources),
    peak_allocated_mib=max(x["peak_allocated_mib"] for x in resources),
    peak_reserved_mib=max(x["peak_reserved_mib"] for x in resources),
    minimum_sampled_whole_card_free_mib=min(x["minimum_whole_card_free_mib"] for x in resources),
    memory_sampling_errors=sum(x["memory_sampling_errors"] for x in resources),
    resource_interpretation="Inference plus loading, hashing and audit synchronization; not training runtime or continuous-memory minimum.")
p = BASE / "replay_verification.json"
text = json.dumps(summary, indent=2) + "\n"
if p.exists():
    assert p.read_text() == text
else:
    p.write_text(text)
p = BASE / "replay_resources.csv"
if not p.exists():
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(resources[0]))
        writer.writeheader()
        writer.writerows(resources)
print(json.dumps(summary, indent=2))
