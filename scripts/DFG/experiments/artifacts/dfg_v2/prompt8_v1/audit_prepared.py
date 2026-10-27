"""Read-only acceptance of the freshly sealed Prompt 8 plan; no training."""
import csv
import gc
import json
import sys
from pathlib import Path

import torch
from scripts.DFG.dfg_v2.experiment import run
from scripts.DFG.dfg_v2.experiment.init import _semantic
from scripts.DFG.dfg_v2.experiment.support import V2_RELATIONS
from scripts.DFG.integration.io import read_json, sha256
from scripts.DFG.dfg_v2.tasks import checked_ref

root = Path(__file__).resolve().parent
path = root / "batch1/plan.json"
plan = run._load_plan(path)
assert len(plan["jobs"]) == 150
assert {s: len(x["jobs"]) for s, x in plan["batch_registration"]["stages"].items()} == {"A": 60, "B": 90}
assert not (path.parent / "runs").exists()
rows, families, support_rows = [], [], []
for task_id, task in plan["tasks"].items():
    for fold in task["folds"]:
        common = None
        records = []
        for profile in plan["profiles"]:
            job = next(j for j in plan["jobs"] if j["task_id"] == task_id and j["fold"] == fold and j["profile"] == profile)
            unused, info, entry = run._prepared(plan, job)
            initial = run._initial(entry, info, job)
            schema = entry["support"]["schema"]
            nodes = {r["name"]: r["index"] for r in schema["node_types"]}
            edges = {tuple(r["canonical"]): r["index"] for r in schema["canonical_relations"]}
            semantic = _semantic(initial["state_dict"], nodes, edges)
            if profile == "G0":
                common = semantic
            else:
                assert set(common) <= set(semantic)
                assert all(torch.equal(value, semantic[key]) for key, value in common.items())
            n_parameters = sum(v.numel() for v in initial["state_dict"].values())
            assert n_parameters == entry["parameter_count"]
            row = dict(job, initial=entry["initial"], optimizer_steps=initial["optimizer_steps"],
                       fit_seed=initial["fit_seed"], parameter_count=n_parameters,
                       common_G0_tensors=len(common), common_exact=True,
                       train_v2_edges=entry["support"]["v2_training_edges"])
            rows.append(row)
            records.append(dict(profile=profile, parameter_count=n_parameters,
                                common_G0_tensors=len(common), common_exact=True))
            for relation in entry["support"]["relations"]:
                if relation["canonical"][1] in V2_RELATIONS:
                    support_rows.append(dict(job, canonical=json.dumps(relation["canonical"]),
                        inner_train_edges=relation["inner_train_edges"],
                        inner_val_edges=relation["inner_val_edges"],
                        outer_test_edges=relation["outer_test_edges"]))
            del initial, semantic
        families.append(dict(task_id=task_id, fold=fold, profiles=records))
        del common
        gc.collect()
        print(task_id, fold, "5 initial states verified", flush=True)
for role in ["A", "B"]:
    assert plan["batch_registration"]["stages"][role]["execution_authorized"] is False
answer = dict(status="prepared_not_executed", plan_sha256=sha256(path),
    runtime_matches=True, jobs=150, fresh_initials=150, independent_families=30,
    stages=dict(A=60, B=90), optimizer_steps_zero=True, common_G0_tensors_exact=True,
    checkpoints_or_fit_results_created=False, source_plan_head=plan["git_head"],
    storage_preflight=plan["batch_registration"]["storage_preflight"],
    configs={k:v["config"] for k,v in plan["tasks"].items()}, families=families, initials=rows)
with (root / "prepared_acceptance.json").open("x", encoding="utf8") as f:
    json.dump(answer, f, indent=2, ensure_ascii=False)
with (root / "prepared_relation_support.csv").open("x", encoding="utf8", newline="") as f:
    writer=csv.DictWriter(f, fieldnames=list(support_rows[0]))
    writer.writeheader()
    writer.writerows(support_rows)
print(json.dumps({k:answer[k] for k in ["status","plan_sha256","jobs","fresh_initials","independent_families","stages"]}),flush=True)
