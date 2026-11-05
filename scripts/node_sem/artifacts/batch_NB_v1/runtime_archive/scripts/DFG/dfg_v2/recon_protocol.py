"""Prompt 0 read-only frozen protocol and recorded resource reconnaissance.

Writes new evidence only; does not construct models or train, modify frozen
inputs, regenerate splits on disk, or execute a GPU operation.
"""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REFERENCE = ROOT / "scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1/build/manifest.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path, expected=None):
    path = Path(path)
    actual = sha(path)
    if expected is not None and actual != expected:
        raise ValueError("Frozen evidence hash mismatch: " + str(path))
    return json.loads(path.read_text()), {"path": str(path), "sha256": actual}


def collect(reference=DEFAULT_REFERENCE):
    from scripts.DFG.experiments.protocol import make_fold_document, validate_fold_document
    from scripts.DFG.experiments.paper_protocol import validate_document
    ref, ref_record = read(reference)
    read(reference, read(Path(reference).with_name("manifest.seal.json"))[0]["sha256"])
    tasks = []
    for entry in ref["tasks"]:
        task, task_record = read(entry["source_task_manifest"], entry["source_task_sha256"])
        split, split_record = read(task["source_splits_path"], task["source_splits_sha256"])
        labels, label_record = read(task["labels_path"], task["labels_sha256"])
        prepared, prepared_record = read(task["source_prepared_manifest"], task["source_prepared_manifest_sha256"])
        validate_document(split)
        nested = split["source_nested_document"]
        validate_fold_document(nested)
        recreated = make_fold_document(nested["file_labels"], nested["task"],
            nested["prepared_manifest_sha256"], nested["seed"], nested["inner_fraction"])
        if recreated != nested:
            raise AssertionError("Current split function did not reproduce frozen lists")
        nested_path = Path(task["source_prepared_manifest"]).parent.parent / "splits" / (task["task"] + "_folds.json")
        original_nested, nested_record = read(nested_path, split["source_nested_file_sha256"])
        if original_nested != nested:
            raise AssertionError("Embedded inner lists differ from original nested document")
        label_lookup = {x["contract_name"]: x["targets"] for x in labels}
        if {f: label_lookup[f] for f in split["files"]} != split["file_labels"]:
            raise AssertionError("Frozen file label mismatch")
        counts = []
        for nf, pf in zip(nested["folds"], split["folds"]):
            counts.append({"fold": nf["fold"], "inner_seed": nf["inner_seed"],
                "inner_train_files": len(nf["inner_train_files"]),
                "inner_val_files": len(nf["inner_val_files"]),
                "outer_test_files": len(nf["outer_test_files"]),
                "paper_train_files": len(pf["train_files"]), "paper_val_files": len(pf["val_files"])})
        tasks.append({"task_id":task["task_id"], "task":task["task"],
            "cohort":task["cohort"], "source_task_manifest":task_record,
            "config":task["config"], "labels_file":label_record,
            "label_version":task["label_version"], "node_labels_location":"frozen HCG node attributes, not graph_labels.json",
            "paper_splits":split_record, "paper_split_content_sha256":split["split_sha256"],
            "original_nested_splits":nested_record, "nested_split_content_sha256":nested["split_sha256"],
            "prepared_manifest":prepared_record, "inner_lists_already_available":True,
            "regenerated_in_memory_matches_frozen_document":True,
            "inner_fraction":nested["inner_fraction"], "seed":split["seed"],
            "k_folds":split["k_folds"], "files":len(split["files"]),
            "fold_file_counts":counts, "fold0_seeds":task["seeds"],
            "graph_labels_format":{"root":"list", "fields":sorted(labels[0]), "records":len(labels)},
            "fold_top_level_keys":sorted(split), "embedded_nested_keys":sorted(nested),
            "paper_fold_keys":sorted(split["folds"][0]), "nested_fold_keys":sorted(nested["folds"][0]),
            "graph_inputs":task["graphs"]})
    records, batches = [], []
    for batch_name in ("overall_cv_v1", "guard_extension_v1"):
        base = ROOT / "scripts/DFG/experiments/artifacts/paper_kfold" / batch_name
        seal, seal_record = read(base / "plan.seal.json")
        plan, plan_record = read(base / "plan.json", seal["sha256"])
        expected = {(j["task_id"], j["fold"], j["variant"]) for j in plan["jobs"]}
        batch_records = []
        for job in plan["jobs"]:
            dest = base / "runs" / job["task_id"] / ("fold_" + str(job["fold"])) / job["variant"]
            completed = []
            for receipt_path in sorted(dest.glob("attempt_*/receipt.json")):
                receipt, rr = read(receipt_path)
                if receipt.get("status") == "complete":
                    completed.append((receipt_path, receipt, rr))
            if len(completed) != 1:
                raise ValueError("Expected one successful receipt: " + str(dest))
            receipt_path, receipt, rr = completed[0]
            if receipt["plan_sha256"] != hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf8")).hexdigest():
                raise ValueError("Receipt plan mismatch")
            if tuple(receipt[k] for k in ("task_id","fold","variant")) != tuple(job[k] for k in ("task_id","fold","variant")):
                raise ValueError("Receipt identity mismatch")
            result, result_record = read(receipt_path.parent / "result.json", receipt["artifacts"]["result.json"])
            config, config_record = read(receipt_path.parent / "effective_config.json", receipt["artifacts"]["effective_config.json"])
            optimizer, optimizer_record = read(receipt_path.parent / "optimizer_schedule.json", receipt["artifacts"]["optimizer_schedule.json"])
            if result["status"] != "complete" or result["score_role"] != "cv_validation":
                raise ValueError("Unexpected historical score role")
            resource = result["resource"]
            row = dict(job, batch=batch_name, seconds=result["wall_seconds_monotonic"],
                epochs=result["history_rows"], best_epoch=result["best_epoch"], last_epoch=result["last_epoch"],
                peak_allocated_mib=resource["peak_allocated_bytes"]/(1024**2),
                peak_reserved_mib=resource["peak_reserved_bytes"]/(1024**2),
                minimum_card_free_mib=resource["card"]["minimum_whole_card_free_mib"],
                parameters=result["parameters"], receipt=rr, result=result_record,
                effective_config=config_record, optimizer_schedule=optimizer_record,
                optimizer=optimizer, numeric_config=config)
            batch_records.append(row)
        if {(x["task_id"],x["fold"],x["variant"]) for x in batch_records} != expected:
            raise AssertionError("Historical inventory changed")
        grouped=defaultdict(list)
        for row in batch_records: grouped[(row["task_id"],row["variant"])].append(row)
        summary=[]
        for (tid,variant), values in sorted(grouped.items()):
            summary.append({"task_id":tid,"variant":variant,"fits":len(values),
                "median_seconds":median(v["seconds"] for v in values),
                "total_seconds":sum(v["seconds"] for v in values),
                "maximum_seconds":max(v["seconds"] for v in values),
                "maximum_peak_allocated_mib":max(v["peak_allocated_mib"] for v in values),
                "maximum_peak_reserved_mib":max(v["peak_reserved_mib"] for v in values),
                "minimum_card_free_mib":min(v["minimum_card_free_mib"] for v in values),
                "median_epochs":median(v["epochs"] for v in values)})
        batches.append({"batch":batch_name,"plan":plan_record,"plan_seal":seal_record,
            "fits":len(batch_records),"sum_fit_seconds":sum(x["seconds"] for x in batch_records),
            "mean_fit_seconds":sum(x["seconds"] for x in batch_records)/len(batch_records),
            "maximum_peak_allocated_mib":max(x["peak_allocated_mib"] for x in batch_records),
            "maximum_peak_reserved_mib":max(x["peak_reserved_mib"] for x in batch_records),
            "by_task_variant":summary,
            "receipt_plan_hash_kind":"canonical JSON digest; plan.seal SHA is file bytes", "scope":"Successful fits executed in this batch only; historical references not counted twice."})
        records.extend(batch_records)
    source_names = ("paper_run.py","paper_runtime.py","protocol.py","paper_protocol.py",
        "freeze_splits.py","run_pair.py","checkpoint.py","paper_checkpoint.py","e23_cv/prepare.py","overall_cv/prepare.py")
    sources=[{"path":str(ROOT/"scripts/DFG/experiments"/name),"sha256":sha(ROOT/"scripts/DFG/experiments"/name)} for name in source_names]
    report={"scope":"Prompt 0 sections 5 and 7; read-only frozen inputs and recorded fitting metadata", "reference_manifest":ref_record,
        "source_files":sources,"tasks":tasks,"resource_batches":batches,
        "seed_formula":{"split":1,"inner":"seed*1009+fold+1", "constructor":"10000+fold+(1000 if contract else 0)","pair":"constructor+77","fit":"constructor+1000000"},
        "training_executed":False,"models_loaded":False,"checkpoint_tensors_loaded":False,
        "validation_scope":"Plan seals and referenced manifests/labels/folds/results/config/optimizer file hashes checked; no full checkpoint archive audit."}
    return report,records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    out=Path(args.output).resolve()
    allowed=ROOT/"scripts/DFG/experiments/artifacts/dfg_v2/recon"
    if allowed not in out.parents:
        raise ValueError("Recon output must remain in new recon evidence directory")
    if out.exists():raise FileExistsError(str(out))
    report,records=collect()
    out.mkdir(parents=True)
    for name,doc in (("protocol_resources.json",report),("fit_records.json",records)):
        (out/name).write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n")
    rows=[dict(batch=b["batch"],**x) for b in report["resource_batches"] for x in b["by_task_variant"]]
    with (out/"resource_summary.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps({"tasks":[{"task_id":t["task_id"],"files":t["files"],"folds":t["k_folds"],"nested_reproduced":t["regenerated_in_memory_matches_frozen_document"]} for t in report["tasks"]],"resources":rows},indent=2))

if __name__=="__main__":main()
