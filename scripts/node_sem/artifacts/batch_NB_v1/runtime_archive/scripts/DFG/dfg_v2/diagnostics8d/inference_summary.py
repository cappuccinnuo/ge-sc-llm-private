"""Read-only complete-matrix summary for Prompt8D's three interventions.

No model forward or optimizer. Frozen best predictions, source identities,
prepared feature rows, receipts and execution seals are checked before output.
B_full vs old idN and B_matched vs C_matched are separate contrasts; edit
density and lexical exposure are reported rather than assumed equivalent.
"""
import argparse
from collections import defaultdict
from pathlib import Path
import statistics

from scripts.DFG.dfg_v2.diagnostics8c import scoring as s
from scripts.DFG.dfg_v2.diagnostics8c import inference_summary as old
from scripts.DFG.dfg_v2.diagnostics8c.common import checked_plan
from .inference_batch import expected_jobs, validate_completed
from .prepared import MODES, load_view
from .stratification import checked

VERSION = "prompt8d-complete-inference-summary-v1"
COHORTS = ("all", "SolidiFI", "nonSolidiFI")



def validate_current_environment_gate(batch, plan):
    """Bind the fresh no-intervention parity check, not just the old 8C gate."""
    if "current_environment_gate" not in batch:
        raise ValueError("Current environment gate binding missing")
    gate = s.read(checked(batch["current_environment_gate"]))
    parity = gate.get("archive_parity", {})
    if (gate.get("gate_only") is not True or
            type(gate.get("optimizer_steps")) is not int or gate["optimizer_steps"] != 0 or
            gate.get("gate_sha256") is not None or
            any(parity.get(key) is not True for key in
                ("passed", "argmax_bitwise", "probability_float32_bitwise")) or
            parity.get("maximum_probability_difference") != 0.0):
        raise ValueError("Current environment gate-only identity/parity failed")
    if gate.get("plan_sha256") != batch["source_plan"]["sha256"]:
        raise ValueError("Current environment gate source plan differs")
    if gate.get("implementation_sha256") != batch["old_worker"]["sha256"]:
        raise ValueError("Current environment gate implementation differs")
    job = gate.get("job")
    if job not in plan["jobs"]:
        raise ValueError("Current environment gate job is not in source plan")
    task = plan["tasks"][job["task_id"]]
    if task["record"]["task"] != "node" or job["profile"] != "G0":
        raise ValueError("Current environment gate is not a baseline node identity check")
    info = s.checked_json(task["prepared"]["%d/%d" % (job["fold"], job["seed"])])
    entry = info["profiles"][job["profile"]]
    if (gate.get("graph") != entry["graph"] or
            job.get("layer_impl") != entry["layer_impl"] or
            gate.get("feature_recipe") != task["record"]["feature"]):
        raise ValueError("Current environment gate graph/feature/implementation identity differs")
    for field in ("checkpoint_sha256", "checkpoint_state_sha256"):
        if not isinstance(gate.get(field), str) or len(gate[field]) != 64:
            raise ValueError("Current environment gate checkpoint identity missing")
    return gate


def validate_gate_checkpoint(gate, report):
    if gate["job"] != report["job"]:
        raise ValueError("Current environment gate/checkpoint job differs")
    for field in ("checkpoint_sha256", "checkpoint_state_sha256"):
        if gate[field] != report[field]:
            raise ValueError("Current environment gate checkpoint identity differs")


def matrix_index(planned, reports):
    """Reject duplicates, missing modes/jobs and surplus reports explicitly."""
    expected = {(item["mode"],) + s.job_key(item["job"]) for item in planned}
    if len(expected) != len(planned):
        raise ValueError("Duplicate planned intervention")
    actual = {}
    for path, report in reports:
        key = (report["intervention"],) + s.job_key(report["job"])
        if key not in expected or key in actual:
            raise ValueError("Unexpected/duplicate intervention report")
        actual[key] = (path, report)
    if set(actual) != expected:
        raise ValueError("Incomplete intervention matrix: %d/%d" % (len(actual), len(expected)))
    return actual


def validate_prepared_report(report, view, prepared_ref):
    if report.get("prepared") != prepared_ref or report.get("tokenizer") != view["tokenizer"]:
        raise ValueError("Worker prepared view/tokenizer binding differs")
    rows = s.index_rows(report["predictions"])
    files = {row["file"] for row in rows.values()}
    if report["mappings"] != {file:view["mappings"][file] for file in files}:
        raise ValueError("Worker rename map differs from prepared view")
    if report["source_refs"] != {file:view["source_refs"][file] for file in files}:
        raise ValueError("Worker source binding differs from prepared view")
    expected = {key:row for key,row in s.index_rows(view["rows"]).items() if key in rows}
    observed = s.index_rows(report["changed_nodes"])
    if set(expected) != set(observed):
        raise ValueError("Worker changed-node population differs from prepared view")
    for key, row in observed.items():
        planned = expected[key]
        actual = dict(row)
        feature_changed = actual.pop("feature_changed", None)
        if actual != planned:
            raise ValueError("Worker changed-node proof differs from prepared view")
        expected_changed = planned["original_vector_sha256"] != planned["renamed_vector_sha256"]
        if type(feature_changed) is not bool or feature_changed != expected_changed:
            raise ValueError("Worker changed-feature count/digest differs")
    return len(expected)


def filter_rows(rows, views, cohort):
    if cohort not in COHORTS:
        raise ValueError("Unknown cohort")
    return [row for row in rows if cohort == "all" or
            views[s.identity(row)]["solidifi"] == (cohort == "SolidiFI")]


def flip_rates(rows, views, view):
    result = {}
    for target, name in ((0, "negative"), (1, "positive")):
        subset = [row for row in rows if views[s.identity(row)][view] == target]
        flips = sum(row["original_best"] != row["renamed_best"] for row in subset)
        result[name + "_n"] = len(subset)
        result[name + "_flips"] = flips
        result[name + "_flip_rate_percent"] = 100.0*flips/len(subset) if subset else None
    return result


def cohort_tables(task, profile, mode, fold_reports, views):
    folds, pooled, means, changes, per_file = [], [], [], [], []
    all_rows = []
    for fold, report in sorted(fold_reports.items()):
        rows = report["predictions"]
        all_rows.extend(rows)
        for cohort in COHORTS:
            subset = filter_rows(rows, views, cohort)
            for view in old.VIEWS:
                for state in old.MODES:
                    folds.append(dict(task=task, profile=profile, intervention=mode, fold=fold,
                        cohort=cohort, view=view, prediction_state=state, aggregation="one_outer_fold",
                        **old.metrics_for(subset, views, view, state)))
                changes.append(dict(task=task, profile=profile, intervention=mode, fold=fold,
                    cohort=cohort, view=view, aggregation="one_outer_fold",
                    **old.changes_for(subset, views, view), **flip_rates(subset, views, view)))
        changed = s.index_rows(report["changed_nodes"])
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["file"]].append(row)
        for file, subset in sorted(grouped.items()):
            edited = [changed[s.identity(row)] for row in subset if s.identity(row) in changed]
            for view in old.VIEWS:
                per_file.append(dict(task=task, profile=profile, intervention=mode, fold=fold,
                    file=file, source_sha256=subset[0]["source_sha256"], view=view,
                    cohort="SolidiFI" if views[s.identity(subset[0])]["solidifi"] else "nonSolidiFI",
                    changed_code_nodes=len(edited),
                    changed_feature_nodes=sum(row["feature_changed"] for row in edited),
                    renamed_unique_identifiers=len(report["mappings"][file]),
                    lexical_occurrences_in_scored_node_code=sum(row["replacements"] for row in edited),
                    edited_token_positions_in_scored_node_code=sum(
                        row["position_proof"]["edited_token_positions"] for row in edited),
                    n_nodes=len(subset),
                    **old.changes_for(subset,views,view),**flip_rates(subset,views,view)))
    for cohort in COHORTS:
        subset = filter_rows(all_rows, views, cohort)
        for view in old.VIEWS:
            for state in old.MODES:
                pooled.append(dict(task=task,profile=profile,intervention=mode,
                    cohort=cohort,view=view,prediction_state=state,aggregation="pooled_OOF",
                    **old.metrics_for(subset,views,view,state)))
                if cohort != "nonSolidiFI":
                    relevant = [row for row in folds if row["cohort"]==cohort and
                                row["view"]==view and row["prediction_state"]==state]
                    mean = dict(task=task,profile=profile,intervention=mode,cohort=cohort,
                                view=view,prediction_state=state,aggregation="equal_nonempty_fold_mean",
                                empty_folds=[row["fold"] for row in relevant if not row["n"]])
                    for name in s.SCORE_NAMES:
                        mean[name]=s._mean_sd(row[name] for row in relevant if row["n"])
                    means.append(mean)
            changes.append(dict(task=task,profile=profile,intervention=mode,fold=None,
                cohort=cohort,view=view,aggregation="pooled_OOF",
                **old.changes_for(subset,views,view),**flip_rates(subset,views,view)))
    return dict(cohort_fold_metrics=folds,cohort_pooled_metrics=pooled,
                cohort_fold_means=means,cohort_changes=changes,file_exposure_changes=per_file)


def paired_change(left, right, views, view):
    """right - left; identities and frozen originals must agree, not CSV order."""
    lrows, rrows = s.index_rows(left), s.index_rows(right)
    if set(lrows) != set(rrows):
        raise ValueError("Comparison populations differ")
    transitions, probabilities = [], []
    for key in sorted(lrows):
        before, after = lrows[key], rrows[key]
        for field in ("target","source_sha256","original_best","original_probability"):
            if before[field] != after[field]:
                raise ValueError("Comparison frozen originals differ: "+field)
        transitions.append(dict(before,
            original_best=before["renamed_best"],original_probability=before["renamed_probability"],
            renamed_best=after["renamed_best"],renamed_probability=after["renamed_probability"]))
    lm=old.metrics_for(left,views,view,"renamed")
    rm=old.metrics_for(right,views,view,"renamed")
    return dict(left_metrics=lm,right_metrics=rm,
        metric_delta_pp={name:rm[name]-lm[name] if lm[name] is not None else None for name in s.SCORE_NAMES},
        **old.changes_for(transitions,views,view),**flip_rates(transitions,views,view))


def contrast_tables(task,profile,left_name,right_name,left_reports,right_reports,views):
    if set(left_reports) != set(right_reports):
        raise ValueError("Comparison folds differ")
    fold_rows,pooled,means,files=[],[],[],[]
    all_left,all_right=[],[]
    for fold in sorted(left_reports):
        left,right=left_reports[fold]["predictions"],right_reports[fold]["predictions"]
        all_left.extend(left);all_right.extend(right)
        if set(s.index_rows(left))!=set(s.index_rows(right)):
            raise ValueError("Comparison fold identity mismatch")
        for cohort in COHORTS:
            ls,rs=filter_rows(left,views,cohort),filter_rows(right,views,cohort)
            for view in old.VIEWS:
                fold_rows.append(dict(task=task,profile=profile,left=left_name,right=right_name,
                    fold=fold,cohort=cohort,view=view,aggregation="one_outer_fold",
                    **paired_change(ls,rs,views,view)))
        by_file=sorted({row["file"] for row in left})
        for file in by_file:
            ls=[row for row in left if row["file"]==file]
            rs=[row for row in right if row["file"]==file]
            for view in old.VIEWS:
                files.append(dict(task=task,profile=profile,left=left_name,right=right_name,
                    fold=fold,file=file,source_sha256=ls[0]["source_sha256"],view=view,
                    left_changed_code_nodes=sum(row["file"]==file for row in left_reports[fold]["changed_nodes"]),
                    right_changed_code_nodes=sum(row["file"]==file for row in right_reports[fold]["changed_nodes"]),
                    left_renamed_identifiers=len(left_reports[fold]["mappings"][file]),
                    right_renamed_identifiers=len(right_reports[fold]["mappings"][file]),
                    left_occurrences=sum(row["replacements"] for row in left_reports[fold]["changed_nodes"] if row["file"]==file),
                    right_occurrences=sum(row["replacements"] for row in right_reports[fold]["changed_nodes"] if row["file"]==file),
                    **paired_change(ls,rs,views,view)))
    for cohort in COHORTS:
        ls,rs=filter_rows(all_left,views,cohort),filter_rows(all_right,views,cohort)
        for view in old.VIEWS:
            pooled.append(dict(task=task,profile=profile,left=left_name,right=right_name,
                cohort=cohort,view=view,aggregation="pooled_OOF",
                **paired_change(ls,rs,views,view)))
            if cohort!="nonSolidiFI":
                relevant=[r for r in fold_rows if r["cohort"]==cohort and r["view"]==view]
                result=dict(task=task,profile=profile,left=left_name,right=right_name,
                    cohort=cohort,view=view,aggregation="equal_nonempty_fold_delta",
                    empty_folds=[r["fold"] for r in relevant if not r["n"]])
                result["metric_delta_pp"]={name:s._mean_sd(r["metric_delta_pp"][name] for r in relevant if r["n"])
                                           for name in s.SCORE_NAMES}
                means.append(result)
    return dict(contrast_fold_metrics=fold_rows,contrast_pooled_metrics=pooled,
                contrast_fold_means=means,contrast_file_changes=files)


def summarize(execution_plan_path, old_root, output):
    execution_plan_path,old_root,output=map(lambda p:Path(p).resolve(),
                                           (execution_plan_path,old_root,output))
    if output.exists():raise FileExistsError(str(output))
    batch=s.read(execution_plan_path)
    if s.read(execution_plan_path.with_name("execution_plan.seal.json"))["sha256"]!=s.sha(execution_plan_path):
        raise ValueError("Execution plan seal differs")
    for key in ("source_plan","prepared","gate","verification","approval","old_worker"):
        checked(batch[key])
    plan_path=Path(batch["source_plan"]["path"]);plan=checked_plan(plan_path)
    current_gate=validate_current_environment_gate(batch,plan)
    planned=expected_jobs(plan)
    if batch["jobs"]!=planned or len(planned)!=300 or batch.get("optimizer_steps")!=0 or batch.get("training_count")!=0:
        raise ValueError("Expected the sealed three-view 300-inference matrix")
    for name,digest in batch["code"].items():
        if s.sha(Path(__file__).with_name(name))!=digest:
            raise ValueError("Bound inference computation changed: "+name)
    completion_path=execution_plan_path.parent/"execution_complete.json"
    complete=s.read(completion_path)
    if complete["plan"]!=s.ref(execution_plan_path) or complete["jobs"]!=300:
        raise ValueError("Completed execution identity differs")
    reports=[]
    for mode in MODES:
        for path in sorted((execution_plan_path.parent/mode/"jobs").glob("*.json")):
            report=s.read(path)
            if report["intervention"]!=mode:raise ValueError("Intervention directory differs")
            reports.append((path,report))
    indexed=matrix_index(planned,reports)
    statuses={}
    for status in complete["statuses"]:
        key=(status["mode"],)+s.job_key(status["job"])
        if key in statuses or status["returncode"]!=0 or key not in indexed:
            raise ValueError("Completion statuses invalid")
        path,report=indexed[key]
        if status["result"]!=s.ref(path):raise ValueError("Completion result SHA differs")
        checked(status["log"])
        status_path=path.parent.parent/"status"/path.name
        if s.read(status_path)!=status:raise ValueError("Individual completion status differs")
        statuses[key]=status
    if set(statuses)!=set(indexed):raise ValueError("Completion status matrix incomplete")
    verification=s.read(batch["verification"]["path"])
    if verification["verified"]!=150 or verification["plan_sha256"]!=s.sha(plan_path):
        raise ValueError("Original 150-fit verification missing")
    verified={s.job_key(row["job"]):row for row in verification["fits"]}
    if len(verified)!=150:raise ValueError("Verification identities duplicated")
    views_path=old_root/"A/node_views.json"
    label_audit=s.read(old_root/"A/audit.json")
    if label_audit["node_views"]!=s.ref(views_path) or label_audit["provenance"]["plan"]!=s.ref(plan_path):
        raise ValueError("Original diagnostic label view binding differs")
    views={task:s.validate_views(task,plan["tasks"][task],value)
           for task,value in s.read(views_path).items()}
    old_summary_path=old_root/"D/summary/summary.json"
    old_summary=s.read(old_summary_path)
    if old_summary["status"]!="complete" or old_summary["interventions"]!=100:
        raise ValueError("Complete 8C idN summary required")
    for reference in old_summary["bindings"].values():checked(reference)
    if old_summary["bindings"]["plan"]!=s.ref(plan_path):raise ValueError("8C plan differs")
    old_reports={}
    for row in old_summary["inputs"]:
        report=s.read(checked(row["intervention"]))
        key=s.job_key(report["job"])
        if key in old_reports:raise ValueError("Duplicate 8C report")
        old_reports[key]=report
    if set(old_reports)!={s.job_key(item["job"]) for item in planned}:
        raise ValueError("8C comparison population incomplete")
    prepared={}
    for task in sorted(views):
        for mode in MODES:
            view,vectors,reference=load_view(batch["prepared"]["path"],task,mode,plan_path)
            prepared[(task,mode)]=(view,reference)
    grouped=defaultdict(dict);old_grouped=defaultdict(dict);inputs=[]
    archives={}
    for key,(path,report) in sorted(indexed.items()):
        mode=key[0];job=report["job"];jk=s.job_key(job);task=plan["tasks"][job["task_id"]]
        validate_completed(report,job,mode,batch)
        item=verified[jk]
        if item["status"]!="verified":raise ValueError("Historical fit not verified")
        if jk not in archives:
            attempt=Path(item["attempt"])
            receipt_path=attempt/"receipt.json"
            if s.sha(receipt_path)!=item["receipt_sha256"]:raise ValueError("Historical receipt changed")
            receipt=s.read(receipt_path)
            if receipt["job"]!=job or receipt["artifacts"]!=item["artifacts"]:
                raise ValueError("Historical receipt artifact binding differs")
            pred_path=attempt/"outer_test_predictions.json"
            sidecar_path=attempt/"best.json"
            for name in ("outer_test_predictions.json","best.json"):
                if s.sha(attempt/name)!=receipt["artifacts"][name]:raise ValueError("Historical artifact changed")
            archives[jk]=(s.read(pred_path),s.read(sidecar_path),receipt,s.ref(pred_path))
        archived,sidecar,receipt,pred_ref=archives[jk]
        if report["checkpoint_sha256"]!=receipt["artifacts"]["best.pt"] or report["checkpoint_state_sha256"]!=sidecar["state_sha256"]:
            raise ValueError("Intervention checkpoint identity differs")
        info=s.checked_json(task["prepared"]["%d/%d"%(job["fold"],job["seed"])])
        entry=info["profiles"][job["profile"]]
        old.validate_report(report,job,s.sha(plan_path),task,entry,archived,views[job["task_id"]])
        if job==current_gate["job"]:
            validate_gate_checkpoint(current_gate,report)
        pv,pref=prepared[(job["task_id"],mode)]
        validate_prepared_report(report,pv,pref)
        grouped[(job["task_id"],job["profile"],mode)][job["fold"]]=report
        if mode==MODES[0]:
            prior=old_reports[jk]
            old.validate_report(prior,job,s.sha(plan_path),task,entry,archived,views[job["task_id"]])
            if prior["checkpoint_sha256"]!=report["checkpoint_sha256"] or prior["checkpoint_state_sha256"]!=report["checkpoint_state_sha256"]:
                raise ValueError("8C/8D checkpoint identity differs")
            old_grouped[(job["task_id"],job["profile"])][job["fold"]]=prior
        inputs.append(dict(mode=mode,job=job,report=s.ref(path),prediction=pred_ref,
                           status=s.ref(path.parent.parent/"status"/path.name)))
    result=dict(version=VERSION,status="complete",inference_count=300,training_count=0,
        optimizer_steps=0,summary_forward_count=0,checkpoint="best",score_role="outer_test",
        views=list(old.VIEWS),interventions=list(MODES),
        bindings=dict(execution_plan=s.ref(execution_plan_path),completion=s.ref(completion_path),
                      source_plan=s.ref(plan_path),prepared=batch["prepared"],verification=batch["verification"],
                      current_environment_gate=batch["current_environment_gate"],
                      label_views=s.ref(views_path),old_idN_summary=s.ref(old_summary_path)),
        inputs=inputs)
    for (task,profile,mode),fold_reports in sorted(grouped.items()):
        if set(fold_reports)!=set(plan["tasks"][task]["folds"]):raise ValueError("Task fold population differs")
        inherited=old.aggregate(task,profile,fold_reports,views[task])
        for name,rows in inherited.items():
            result.setdefault(name,[]).extend(dict(row,intervention=mode) for row in rows)
        for name,rows in cohort_tables(task,profile,mode,fold_reports,views[task]).items():
            result.setdefault(name,[]).extend(rows)
    for task,profile in sorted(old_grouped):
        comparisons=(("8C_idN","B_full",old_grouped[(task,profile)],grouped[(task,profile,"B_full")]),
                     ("B_matched","C_matched",grouped[(task,profile,"B_matched")],grouped[(task,profile,"C_matched")]))
        for left,right,lrows,rrows in comparisons:
            for name,rows in contrast_tables(task,profile,left,right,lrows,rrows,views[task]).items():
                result.setdefault(name,[]).extend(rows)
    result["notes"]=[
        "Every inference uses the original best checkpoint; no optimizer or new model selection.",
        "B_full vs 8C_idN contrasts all-marker replacement with and without preserved token positions.",
        "B_matched vs C_matched has equal unique-name counts/token-length histograms, not necessarily equal occurrences/node coverage.",
        "B_full is not compared as though it had the edit density of C_matched.",
        "Test-time lexical changes remain distribution shifts; no diagnostic contrast proves pure causal dependence.",
        "All/each SolidiFI summaries use equal nonempty fold means and pooled OOF separately.",
        "NonSolidiFI has per-fold count diagnostics and pooled metrics; no fold-mean claim.",
        "orig/C1 are reported separately; C1 is a diagnostic label view, not verified ground truth.",
        "Node metrics retain frozen HCG-node identities and do not deduplicate source lines.",
        "No p-values, Holm recalculation, training authorization or replacement of sealed primary endpoints."]
    output.mkdir(parents=False)
    for name,rows in result.items():
        if isinstance(rows,list) and rows and isinstance(rows[0],dict) and name not in ("inputs",):
            s._csv(output/(name+".csv"),rows)
    s.write(output/"summary.json",result)
    s.write(output/"receipt.json",dict(status="complete",version=VERSION,inferences=300,
        bindings=result["bindings"],artifacts={path.name:s.ref(path) for path in sorted(output.iterdir()) if path.is_file()}))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--execution-plan",required=True)
    parser.add_argument("--old-root",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=summarize(args.execution_plan,args.old_root,args.output)
    print("Summarized",result["inference_count"],"frozen-checkpoint diagnostic inferences")
