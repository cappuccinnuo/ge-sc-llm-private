"""Post-fit read-only audit and compact resource/support export; no training."""
import csv, json, math
from collections import Counter, defaultdict
from pathlib import Path
B = Path(__file__).resolve().parent
summary = json.loads((B/"summary.json").read_text())
assert summary["status"] == "complete" and summary["formal_fits"] == 4
support, gradients, resources, changes = [], [], [], []
for task in ("reentrancy_author_node", "access_control_author_node"):
    for variant in ("B0", "B1"):
        p = B/"runs"/task/variant/"attempt_001"
        d = json.loads((p/"result.json").read_text())
        hist = [json.loads(x) for x in (p/"history.jsonl").read_text().splitlines()]
        assert d["status"] == "complete"
        assert d["checkpoint_roundtrip_exact"] == {"best": True, "last": True}
        assert d["no_parameters_created_during_training_or_scoring"]
        assert all(math.isfinite(x[k]) for x in hist for k in ("train_loss","cv_validation_loss","lr"))
        epochs = d["gradient_audit"]["epochs"]
        records = defaultdict(list)
        for epoch in epochs:
            for rec in epoch["enhancement_relations"]:
                records[tuple(rec["canonical"])].append(rec)
        grouped = defaultdict(lambda: dict(train_edges=0, val_edges=0, canonical_count=0,
                            train_supported_canonical=0, no_train_support_canonical=0,
                            supported_with_nonzero_message_gradient=0))
        for canonical, seq in sorted(records.items()):
            first = seq[0]
            assert all((x["train_edges"], x["val_edges"]) == (first["train_edges"], first["val_edges"]) for x in seq)
            vals = [x["message_gradient_l1"] for x in seq]
            assert all(math.isfinite(x) for x in vals)
            g = grouped[canonical[1]]
            g["train_edges"] += first["train_edges"]; g["val_edges"] += first["val_edges"]
            g["canonical_count"] += 1
            train_seen = first["train_edges"] > 0
            g["train_supported_canonical"] += train_seen
            g["no_train_support_canonical"] += not train_seen
            g["supported_with_nonzero_message_gradient"] += train_seen and max(vals) > 0
            gradients.append(dict(task=task,variant=variant,canonical=list(canonical),
                  train_edges=first["train_edges"],val_edges=first["val_edges"],
                  epochs=len(seq),max_message_gradient_l1=max(vals),
                  statuses=dict(Counter(x["status"] for x in seq))))
        for rel, stats in sorted(grouped.items()):
            support.append(dict(task=task,variant=variant,relation=rel,**stats))
        resources.append(dict(task=task,variant=variant,epochs=len(hist),
           best_epoch_zero_based=d["best_epoch"],last_epoch_zero_based=d["last_epoch"],
           parameters=d["parameters"],seconds=d["wall_seconds_monotonic"],
           peak_allocated_mib=d["resource"]["peak_allocated_bytes"]/1048576,
           peak_reserved_mib=d["resource"]["peak_reserved_bytes"]/1048576,
           minimum_card_free_mib=d["resource"]["card"]["minimum_whole_card_free_mib"],
           checkpoint_reload_exact=True,nonfinite_loss=False,
           new_parameters_during_scoring=False,attempt=1))
with (B/"prediction_changes.csv").open() as f:
    allchanges = list(csv.DictReader(f))
for task in ("reentrancy_author_node", "access_control_author_node"):
    for ck in ("best", "last"):
        selected = [x for x in allchanges if x["task_id"]==task and x["checkpoint"]==ck]
        changes.append(dict(task=task,checkpoint=ck,
          mean_absolute_probability_delta=sum(abs(float(x["probability_delta"])) for x in selected)/len(selected),
          max_absolute_probability_delta=max(abs(float(x["probability_delta"])) for x in selected),
          changed_predictions=[x for x in selected if x["status"] in ("corrected","regressed")]))
for name, rows in (("training_support.csv", support), ("resource_summary.csv", resources)):
    with (B/name).open("w", newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
payload=dict(complete_fits=4,roundtrip_checkpoints=8,nonfinite_losses=0,failures=0,retries=0,
             support=support,gradients=gradients,resources=resources,prediction_changes=changes)
(B/"training_audit.json").write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps(dict(resources=resources,support=support,changes=changes),indent=2))
