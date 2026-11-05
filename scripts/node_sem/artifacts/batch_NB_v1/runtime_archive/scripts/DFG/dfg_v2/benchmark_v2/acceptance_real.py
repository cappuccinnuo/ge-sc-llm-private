"""Read-only independent score recount and fail-closed 8E acceptance record."""
import argparse
import math
from collections import Counter
from pathlib import Path

from .prepare import read, write, ref, checked, sha
from .prepare_real import load_naming


def binary_metrics(pairs):
    counts = Counter((int(y), int(p)) for y, p in pairs)
    if set(counts) - {(0, 0), (0, 1), (1, 0), (1, 1)}:
        raise ValueError("Non-binary score")
    tn, fp, fn, tp = (counts[k] for k in ((0, 0), (0, 1), (1, 0), (1, 1)))
    return dict(tn=tn, fp=fp, fn=fn, tp=tp, n=tn+fp+fn+tp,
                buggy_f1=200.0*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0,
                precision=100.0*tp/(tp+fp) if tp+fp else 0.0,
                recall=100.0*tp/(tp+fn) if tp+fn else 0.0)


def compare_metrics(expected, observed):
    for key, value in observed.items():
        if key not in expected or not math.isclose(expected[key], value, rel_tol=0, abs_tol=1e-10):
            raise ValueError("Independent metric mismatch: " + key)


def gate_failures(summary):
    failures = []
    if summary["P1"]["N-real"]["passed"] is not True:
        failures.append(dict(probe="P1", reason="ordinary-name witness requirement failed"))
    for task, labels in summary["P2"]["N-real"].items():
        for label, value in labels.items():
            delta = value["pooled"]["buggy_f1"] - value["all_positive"]["buggy_f1"]
            if not math.isfinite(delta):
                raise ValueError("Non-finite P2 score")
            if delta > 5.0:
                failures.append(dict(probe="P2", task=task, label=label, delta_bf1_pp=delta,
                                     threshold_pp=5.0))
    auc = summary["P3"]["N-real"]["auc"]
    if not math.isfinite(auc):
        raise ValueError("Non-finite P3 score")
    if auc > 0.60:
        failures.append(dict(probe="P3", auc=auc, threshold=0.60))
    return failures


def verify_results(naming, probes):
    manifest, inventory, _, _ = load_naming(naming)
    probes = Path(probes)
    summary = read(probes/"summary.json")
    if read(probes/"summary.seal.json")["summary"] != ref(probes/"summary.json"):
        raise ValueError("Probe summary seal mismatch")
    if summary["naming"] != ref(Path(naming)/"manifest.json"):
        raise ValueError("Probe naming identity differs")
    old = read(checked(manifest["old_plan"]))
    labels = read(checked(old["bound_artifacts"]["node_diagnostic_views"]))
    expected_views = {"original", "idN", "N-real"}
    if set(summary["P1"]) != expected_views or set(summary["P2"]) != expected_views or set(summary["P3"]) != expected_views:
        raise ValueError("Probe view matrix incomplete")
    p2_count, p3_count = 0, 0
    for view, tasks in summary["P2"].items():
        if set(tasks) != {"reentrancy_node", "access_control_node"}:
            raise ValueError("P2 task matrix incomplete")
        for task, label_reports in tasks.items():
            if set(label_reports) != {"orig", "C1"}:
                raise ValueError("P2 label matrix incomplete")
            expected_targets = {(r["file"], r["source_sha256"], r["original_graph_node_id"]): r
                                for r in labels[task]}
            frozen_folds = read(checked(old["tasks"][task]["folds"]))["folds"]
            outer = {f["fold"]: set(f["outer_test_files"]) for f in frozen_folds}
            for label, detail in label_reports.items():
                report = read(checked(detail["artifact"]))
                predictions = [row for f in report["folds"] for row in f["predictions"]]
                identities = [(r["file"], r["source_sha256"], r["original_graph_node_id"])
                              for r in predictions]
                if set(identities) != set(expected_targets):
                    raise ValueError("OOF population differs from frozen labels")
                for f in report["folds"]:
                    if f["fold"] not in outer or any(r["file"] not in outer[f["fold"]] for r in f["predictions"]):
                        raise ValueError("OOF fold attribution differs")
                if len(set(identities)) != len(identities):
                    raise ValueError("Duplicate OOF identity")
                for row in predictions:
                    identity = (row["file"], row["source_sha256"], row["original_graph_node_id"])
                    if row[label] != expected_targets[identity][label]:
                        raise ValueError("OOF target differs from frozen diagnostic labels")
                    if inventory[task+"/"+row["file"]]["source_sha256"] != row["source_sha256"]:
                        raise ValueError("OOF source identity changed")
                rows = [r for r in predictions if r["solidifi"]]
                for expected in (detail, report):
                    compare_metrics(expected["pooled"], binary_metrics((r[label], r["prediction"]) for r in rows))
                    compare_metrics(expected["all_positive"], binary_metrics((r[label], 1) for r in rows))
                for f in report["folds"]:
                    selected = [r for r in f["predictions"] if r["solidifi"]]
                    compare_metrics(f["metric"], binary_metrics((r[label], r["prediction"]) for r in selected))
                p2_count += 1
    # Compute AUC directly as Mann-Whitney ranks, independently of sklearn.
    for view, detail in summary["P3"].items():
        report = read(checked(detail["artifact"]))
        ranked = sorted((r["probability"], r["target"]) for r in report["predictions"])
        rank_sum, pos, neg, start = 0.0, 0, 0, 0
        while start < len(ranked):
            end = start+1
            while end < len(ranked) and ranked[end][0] == ranked[start][0]:
                end += 1
            npos = sum(y for _, y in ranked[start:end])
            rank_sum += npos * ((start+1+end)/2.0)
            pos += npos; neg += end-start-npos
            start = end
        auc = (rank_sum-pos*(pos+1)/2)/(pos*neg)
        if not math.isclose(auc, detail["auc"], rel_tol=0, abs_tol=1e-12):
            raise ValueError("Independent rank AUC mismatch")
        p3_count += 1
    failures = gate_failures(summary)
    if summary["passed"] != (not failures):
        raise ValueError("Acceptance status contradicts observed gates")
    return dict(passed=True, p2_reports=p2_count, p2_fold_metrics=p2_count*10,
                p3_auc_reports=p3_count, acceptance_passed=not failures, failures=failures,
                original_summary=ref(probes/"summary.json"))


def finalize(naming, probes, semantics, output):
    output = Path(output); output.mkdir(exist_ok=False)
    verification = verify_results(naming, probes)
    parity = read(Path(semantics)/"summary.json")
    if not parity["passed"] or parity["graph_file_checks"] != 160:
        raise ValueError("Incomplete real-data semantic parity")
    for reference in parity["artifacts"].values():
        checked(reference)
    manifest, _, _, _ = load_naming(naming)
    if parity["naming"] != ref(Path(naming)/"manifest.json"):
        raise ValueError("Semantic parity belongs to another naming manifest")
    old = read(checked(manifest["old_plan"]))
    if verification["acceptance_passed"]:
        # This report is not an execution plan; downstream feature preparation
        # must be separately implemented/verified before any authorization.
        status = "probe_gate_passed_feature_preparation_required"
    else:
        status = "blocked_by_preregistered_leakage_gate"
    write(output/"independent_verification.json", verification)
    decision = dict(status=status, execution_authorized=False,
        ready_for_training=False, formal_fit_count=0, diagnostic_logistic_fits=15,
        naming=ref(Path(naming)/"manifest.json"), probes=ref(Path(probes)/"summary.json"),
        semantics=ref(Path(semantics)/"summary.json"), superseded_plan=manifest["old_plan"],
        requested_future_fit_count=old["fit_count"], failures=verification["failures"],
        original_jobs_and_splits_unchanged=True, feature_npz_created=False,
        ready_plan_created=False, optional_N_anon_prepared=False,
        no_resampling_no_retuning=True,
        deferred=["N-real token feature assembly and identity verification",
                  "new 170-fit executable plan and seal",
                  "label/seed/location choices and execution authorization"],
        interpretation=dict(access_control_node="descriptive only; not primary DFG evidence",
                            primary_tasks=["reentrancy_node", "reentrancy_contract", "access_control_contract"],
                            nonSolidiFI="pooled counts only", C1="diagnostic label hypothesis, not established truth"),
        timing_reference=old["bound_artifacts"]["timing"],
        resource_note="Final runs are intended for sufficient-VRAM server; local RTX3050 4GB only constrains development. Server not verified.")
    write(output/"acceptance_decision.json", decision)
    write(output/"acceptance_decision.seal.json",
          dict(decision=ref(output/"acceptance_decision.json")))
    write(output/"authorization_template.json", dict(
        version="prompt8e-authorization-blocked-v1", execution_authorized=False,
        acceptance_decision=ref(output/"acceptance_decision.json"),
        selected_label_policy=None, selected_seeds=None, selected_location=None,
        default_label_suggestion="L-audit",
        cannot_authorize_current_candidate=bool(verification["failures"]),
        reason="Acceptance gates must be resolved in a separately agreed new protocol, not by toggling this field."))
    return decision


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--naming", required=True); p.add_argument("--probes", required=True)
    p.add_argument("--semantics", required=True); p.add_argument("--output", required=True)
    a=p.parse_args()
    print(finalize(a.naming,a.probes,a.semantics,a.output)["status"])
