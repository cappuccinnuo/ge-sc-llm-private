"""Read-only correction of the non-gating access_check diagnostic.

The original NS-P7 plan, runtime, responses and report remain immutable.
This module never generates text, changes facts or recomputes pass thresholds.
"""
import argparse
import json
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, checked, ref, write
from .llm_post import role_agreement


def own_sender_condition(facts):
    """Three-valued proof from the *current condition*, not enclosing guards."""
    if facts["node_kind"] != "condition":
        return False
    own = facts.get("self_condition", {})
    if not own:
        return None
    operands = set(own["operand_classes"])
    if not operands.intersection({"msg.sender", "tx.origin"}):
        return False
    if set(own["eq_pairs"]).intersection({"env_state","env_param","env_literal"}):
        return True
    # Predicate calls, inequalities, or absent equality proof are not silently
    # classified as a confirmed absence of authorization checking.
    return None


def corrected_agreement(rows, facts):
    result = role_agreement(rows, facts)
    truths = [own_sender_condition(facts[r["row_key"]]) for r in rows]
    predicted = [r["role"] == "access_check" for r in rows]
    claimed = sum(p and t is not None for p,t in zip(predicted,truths))
    correct = sum(p and t is True for p,t in zip(predicted,truths))
    actual = sum(t is True for t in truths)
    result["access_check"] = dict(claimed_verifiable=claimed,correct=correct,facts_positive=actual,
        precision=correct/claimed if claimed else None,recall=correct/actual if actual else None,
        facts_unknown=sum(t is None for t in truths),
        claimed_unknown=sum(p and t is None for p,t in zip(predicted,truths)),
        missing=sum("missing" in r["flags"] or "parse_failed" in r["flags"] for r in rows),
        reference="self_condition confirmed caller equality; predicate/opaque checks unknown",
        interpretation="agreement with available static proof, not ground-truth authorization correctness")
    return result


def review(root, approval):
    root, approval = Path(root), Path(approval)
    consent = read(approval)
    if consent.get("access_check_read_only_correction") is not True:
        raise PermissionError("Read-only diagnostic correction approval required")
    original_path = root/"pilot_report/pilot_report.json"
    original = read(checked(read(root/"pilot_report/report.seal.json")["report"]))
    rows = [json.loads(s) for s in checked(read(root/"pilot_report/report.seal.json")["rows"]).read_text(encoding="utf8").splitlines()]
    inputs = read(checked(read(root/"pilot_plan.json")["inputs"]))
    facts = {}
    for task, item in inputs["inputs"].items():
        fm = read(checked(item["facts_manifest"]))
        for row in map(json.loads, checked(fm["facts"]).read_text(encoding="utf8").splitlines()):
            facts[task+":"+str(row["row_key"])] = row["facts"]
    rows = [r for r in rows if r["target_kind"]=="statement"]
    amended = corrected_agreement(rows,facts)
    for role in ("external_call","state_update"):
        if amended[role] != original["agreement"][role]:
            raise AssertionError("Gating metric changed during non-gating correction")
    out = root/"access_check_review"
    out.mkdir(exist_ok=False)
    result = dict(version="nodesem-llm-access-check-review-v1", original=ref(original_path),
        approval=ref(approval), implementation=ref(__file__),
        original_access_check_invalid=True,
        reason="guards describes conditions protecting a node; self_condition describes this node's check",
        original_agreement=original["agreement"], corrected_agreement=amended,
        gates_unchanged=original["gates"], new_inference_calls=0, original_files_modified=False)
    write(out/"review.json",result)
    write(out/"review.seal.json",dict(review=ref(out/"review.json")))
    return result


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True)
    ap.add_argument("--approval",required=True)
    a=ap.parse_args()
    print(json.dumps(review(a.root,a.approval)["corrected_agreement"]["access_check"],indent=2))
