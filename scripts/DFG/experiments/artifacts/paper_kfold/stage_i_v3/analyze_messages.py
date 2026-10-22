"""Postprocess sealed Stage I message audits; no model import or forward.

N and Z_ALL were explicitly recorded. Other conditions have no norm records by
configuration, which is not a failed diagnostic. Norms describe destination-SUM
aggregates, not edge norms, normalized contribution shares, or semantic causes.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "stage-i-message-audit-postprocess-v1.1"
SCORE_ROLE = "exploratory_cv_validation_fixed_checkpoint_sensitivity"
SOURCE_SCORE_ROLE = "cv_validation"
STATE = frozenset(("STATE_DEF_USE", "STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"))
CONDITIONS = frozenset(("N", "Z_D", "Z_S", "Z_C", "Z_SC", "Z_ALL"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def checked(path, expected, inputs):
    path = Path(path)
    actual = sha(path)
    if actual != expected:
        raise ValueError("Input SHA mismatch: " + str(path))
    inputs[str(path.resolve())] = actual
    return read(path)


def identity(job):
    return job["task_id"], job["fold"], job["variant"]


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    columns = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(stream, columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v,sort_keys=True) if isinstance(v,(list,dict,tuple)) else v for k,v in row.items()})
    return stream.getvalue().encode("utf8")


def validate_matrix(jobs):
    expected = {(cohort + "_" + task, fold, variant)
                for cohort in ("reentrancy_author", "access_control_author")
                for task in ("contract", "node")
                for fold in range(5 if task == "contract" else 10)
                for variant in ("E3a", "E3b")}
    keys = [identity(j) for j in jobs]
    if len(keys) != 60 or len(set(keys)) != 60 or set(keys) != expected:
        raise ValueError("Expected exact frozen 60-model matrix")
    for j in jobs:
        if j["task_id"] != j["cohort"] + "_" + j["task"]:
            raise ValueError("Task/cohort mismatch")


def finite_nonnegative(value, label):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid finite nonnegative " + label)


def layer_rows(normal, zero, support, job, checkpoint, layer):
    """Validate one canonical schema and return scalar rows, without model code."""
    schema = {tuple(r["canonical"]) for r in support["schema"]["canonical_relations"]}
    original = {tuple(r["canonical"]): r for r in normal["canonical"].values()}
    masked = {tuple(r["canonical"]): r for r in zero["canonical"].values()}
    if len(original) != len(normal["canonical"]) or len(masked) != len(zero["canonical"]):
        raise ValueError("Duplicate canonical norm row")
    if set(original) != schema or set(masked) != schema:
        raise ValueError("N/Z_ALL canonical schema mismatch")
    supports = {tuple(r["canonical"]):r for r in support["relations"]}
    if set(supports) != schema:
        raise ValueError("Support/schema mismatch")
    counts = Counter(c[2] for c in schema)
    if normal["forward_calls"] != 1 or zero["forward_calls"] != 1:
        raise ValueError("Expected one full-graph forward per condition")
    if set(normal["cross_mean"]) != set(counts) or set(zero["cross_mean"]) != set(counts):
        raise ValueError("Cross-mean destination schema mismatch")
    for typ, count in counts.items():
        for data in (normal, zero):
            if data["cross_mean"][typ]["cross_mean_relation_count"] != count:
                raise ValueError("Cross-mean denominator changed")
    rows = []
    for canonical in sorted(schema):
        n, z, s = original[canonical], masked[canonical], supports[canonical]
        selected = canonical[1] in STATE
        for data in (n, z):
            if data["observations"] != 1:
                raise ValueError("Unexpected norm observation count")
            for field in ("original_aggregate_l2_sum", "original_aggregate_l2_max",
                          "zeroed_aggregate_l2_sum", "effective_aggregate_l2_sum"):
                finite_nonnegative(data[field], field)
            if data["cross_mean_relation_count"] != counts[canonical[2]]:
                raise ValueError("Cross-mean denominator changed")
            if data["edge_count"] != s["train_edges"] + s["val_edges"]:
                raise ValueError("Model edge count and frozen split support differ")
        if n["edge_count"] != z["edge_count"] or n["destination_node_count"] != z["destination_node_count"]:
            raise ValueError("Intervention node/edge population changed")
        if n["masked"] is not False or z["masked"] is not selected:
            raise ValueError("Wrong canonical mask selection")
        if n["zeroed_aggregate_l2_sum"] != 0 or n["effective_aggregate_l2_sum"] != n["original_aggregate_l2_sum"]:
            raise ValueError("Normal canonical messages changed")
        if selected:
            if z["effective_aggregate_l2_sum"] != 0 or z["zeroed_aggregate_l2_sum"] != z["original_aggregate_l2_sum"]:
                raise ValueError("Selected message not completely zero")
        elif (z["zeroed_aggregate_l2_sum"] != 0 or z["effective_aggregate_l2_sum"] != z["original_aggregate_l2_sum"]):
            raise ValueError("Base/DATA_DEF_USE message was masked")
        if int(layer) == 0 and n["original_aggregate_l2_sum"] != z["original_aggregate_l2_sum"]:
            raise ValueError("First-layer native attention/SUM changed before masking")
        rows.append(dict(
            task_id=job["task_id"], task=job["task"], cohort=job["cohort"],fold=job["fold"],
            variant=job["variant"], checkpoint=checkpoint, layer=int(layer), canonical=list(canonical),
            relation=canonical[1], state_relation=selected, edge_count=n["edge_count"],
            train_edges=s["train_edges"],val_edges=s["val_edges"],
            has_training_support=s["train_edges"] > 0, has_validation_support=s["val_edges"] > 0,
            normal_aggregate_l2=n["original_aggregate_l2_sum"],
            zero_all_before_mask_aggregate_l2=z["original_aggregate_l2_sum"],
            zero_all_removed_aggregate_l2=z["zeroed_aggregate_l2_sum"],
            zero_all_effective_aggregate_l2=z["effective_aggregate_l2_sum"],
            normal_message_nonzero=n["original_aggregate_l2_sum"] > 0,
            zero_all_message_zero=z["effective_aggregate_l2_sum"] == 0,
            cross_mean_relation_count=counts[canonical[2]], cross_mean_denominator_preserved=True,
            first_layer_before_mask_equal=(int(layer)==0 and n["original_aggregate_l2_sum"]==z["original_aggregate_l2_sum"])))
    return rows


def analyze(output, allow_partial=False):
    output = Path(output).resolve()
    inputs = {}
    seal = read(output/"plan.seal.json")
    inputs[str(output/"plan.seal.json")] = sha(output/"plan.seal.json")
    plan = checked(output/"plan.json",seal["plan_sha256"],inputs)
    if plan.get("score_role") != SCORE_ROLE or plan.get("source_score_role") != SOURCE_SCORE_ROLE:
        raise ValueError("Unexpected sealed diagnostic/source scoring role")
    if plan.get("optimizer_steps") != 0 or plan.get("retraining") is not False or plan.get("inference_only") is not True:
        raise ValueError("Unexpected inference protocol")
    if plan["record_messages"] != "N and Z_ALL only; others sensitivity-only to avoid redundant reductions":
        raise ValueError("Unexpected recorded message conditions")
    validate_matrix(plan["jobs"])
    expected_paths={"{}/fold_{}/{}".format(*identity(j)) for j in plan["jobs"]}
    observed_paths={str(p.parent.relative_to(output/"replays")) for p in (output/"replays").glob("*/fold_*/*/receipt.json")}
    if observed_paths - expected_paths:raise ValueError("Unexpected replay receipt")
    rows, completed, missing, relation_presence = [], [], [], []
    for job in plan["jobs"]:
        folder=output/"replays"/job["task_id"]/("fold_"+str(job["fold"]))/job["variant"]
        receipt_path=folder/"receipt.json"
        if not receipt_path.exists():
            missing.append(list(identity(job)));continue
        receipt=read(receipt_path);inputs[str(receipt_path)]=sha(receipt_path)
        if receipt.get("status")!="passed" or receipt.get("plan_sha256")!=seal["plan_sha256"]:
            raise ValueError("Replay receipt is unpassed or from another plan")
        if receipt.get("source_receipt_sha256")!=job["receipt_sha256"]:
            raise ValueError("Historical fit receipt binding mismatch")
        required={ck+"/"+name for ck in ("best","last") for name in ("audit.json","scores.json","predictions.json")}
        if not required<=set(receipt["artifact_sha256"]):
            raise ValueError("Incomplete replay artifacts")
        for relative,digest in receipt["artifact_sha256"].items():
            file=(folder/relative).resolve()
            try:file.relative_to(folder)
            except ValueError:raise ValueError("Artifact outside replay directory")
            if sha(file)!=digest:raise ValueError("Replay artifact changed: "+str(file))
            inputs[str(file)]=digest
        info=checked(job["task_manifest"],job["task_manifest_sha256"],inputs)
        if any(info[k]!=job[k] for k in ("task_id","task","cohort","fold")):
            raise ValueError("Frozen task manifest identity mismatch")
        support=info["support"][job["variant"]]
        for checkpoint in ("best","last"):
            audit=read(folder/checkpoint/"audit.json")
            if audit["score_role"]!=plan["score_role"]:raise ValueError("Wrong scoring role")
            gates=audit["gates"]
            for k in ("wrapper_exact","restored_native_exact","weights_unchanged","parameter_objects_unchanged","input_unchanged","no_gradients"):
                if gates[k] is not True:raise ValueError("Failed replay gate "+k)
            if gates["optimizer_steps"]!=0:raise ValueError("Unexpected optimization")
            if gates["archive_replay"]["predictions_exact"] is not True or gates["archive_replay"]["metrics_match"] is not True:
                raise ValueError("Failed archive replay")
            messages=audit["messages"]
            if set(messages)!=CONDITIONS:raise ValueError("Condition coverage mismatch")
            for name,data in messages.items():
                if name in ("N","Z_ALL"):
                    if data["record"] is not True or not data["layers"]:raise ValueError("Missing requested norm records")
                    if data["norm_unit"]!="canonical_destination_sum_Frobenius_L2":raise ValueError("Norm unit mismatch")
                elif data["record"] is not False or data["layers"]:
                    raise ValueError("Unexpected norm recording strategy")
            normal,zero=messages["N"],messages["Z_ALL"]
            if normal["requested_relations"] or set(zero["requested_relations"])!=STATE:
                raise ValueError("Mask request mismatch")
            layers={str(i) for i in range(info["config"]["layers"])}
            if set(normal["layers"])!=layers or set(zero["layers"])!=layers:
                raise ValueError("Layer coverage mismatch")
            for layer in sorted(layers):rows.extend(layer_rows(normal["layers"][layer],zero["layers"][layer],support,job,checkpoint,layer))
            present={r["canonical"][1] for r in support["schema"]["canonical_relations"]}
            for relation in sorted(STATE):
                amounts=support["enhancement_support"][relation]
                relation_presence.append(dict(task_id=job["task_id"],variant=job["variant"],fold=job["fold"],
                    checkpoint=checkpoint,relation=relation,registered=relation in present,
                    train_edges=amounts["train"],val_edges=amounts["val"],
                    status="registered_observed" if relation in present else "absent_expected_noop"))
        completed.append(list(identity(job)))
    if missing and not allow_partial:raise ValueError("Refuse formal output before all 60 models complete")
    groups=defaultdict(list)
    for row in rows:groups[(row["task_id"],row["variant"],row["checkpoint"],row["layer"],tuple(row["canonical"]))].append(row)
    summary=[]
    for group,items in sorted(groups.items()):
        task,variant,checkpoint,layer,canonical=group
        row={k:items[0][k] for k in ("task_id","task","cohort","variant","checkpoint","layer","canonical","relation","state_relation","edge_count","cross_mean_relation_count")}
        row.update(folds_observed=len(items),nonzero_normal_message_folds=sum(r["normal_message_nonzero"] for r in items),
            zero_all_effective_zero_folds=sum(r["zero_all_message_zero"] for r in items),
            folds_without_train_support=sum(not r["has_training_support"] for r in items),
            folds_without_val_support=sum(not r["has_validation_support"] for r in items),
            cross_mean_denominator_preserved=all(r["cross_mean_denominator_preserved"] for r in items))
        for field in ("train_edges","val_edges","normal_aggregate_l2","zero_all_before_mask_aggregate_l2","zero_all_removed_aggregate_l2","zero_all_effective_aggregate_l2"):
            values=[r[field] for r in items]
            row[field+"_min"]=min(values);row[field+"_max"]=max(values);row[field+"_mean"]=statistics.mean(values)
        summary.append(row)
    state_rows=[r for r in rows if r["state_relation"]]
    report={"version":VERSION,"status":"partial_preview" if missing else "complete",
        "expected_models":60,"completed_models":len(completed),"missing_jobs":missing,
        "checkpoint_audits":len(completed)*2,"canonical_layer_observations":len(rows),
        "state_canonical_layer_observations":len(state_rows),
        "state_normal_nonzero_observations":sum(r["normal_message_nonzero"] for r in state_rows),
        "all_requested_state_effective_messages_zero":all(r["zero_all_message_zero"] for r in state_rows),
        "all_cross_mean_denominators_preserved":all(r["cross_mean_denominator_preserved"] for r in rows),
        "norm_unit":"canonical_destination_sum_Frobenius_L2",
        "score_role":plan["score_role"],"source_score_role":plan["source_score_role"],
        "not_per_edge_norms":True,"not_causal_contribution_share":True,"no_forward_or_training":True,
        "recorded_conditions":["N","Z_ALL"],"unrecorded_conditions_are_expected":True,
        "second_layer_base_messages_may_change_due_to_first_layer_intervention":True,
        "full_fixed_graph_norms_not_train_or_val_specific_norms":True,
        "train_val_support_is_edge_count_not_separate_message_attribution":True,
        "relation_presence":relation_presence,"input_sha256":inputs,
        "postprocessor_sha256":sha(__file__)}
    if not allow_partial:
        blobs={"message_norm_summary.csv":csv_bytes(summary),"message_norm_by_fold.csv":csv_bytes(rows),
               "message_edge_effectiveness.json":(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n").encode("utf8")}
        for name,body in blobs.items():
            file=output/name
            if file.exists() and file.read_bytes()!=body:raise FileExistsError("Refuse different postprocess output: "+name)
        for name,body in blobs.items():
            file=output/name
            if not file.exists():
                with file.open("xb") as stream:stream.write(body)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument("--allow-partial",action="store_true",help="read-only stdout preview; never writes summary files")
    args=parser.parse_args()
    report=analyze(args.output,args.allow_partial)
    print(json.dumps({k:v for k,v in report.items() if k not in ("relation_presence","input_sha256")},indent=2))

if __name__=="__main__":main()
