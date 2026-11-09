"""S8 decision from the sole preregistered S5-S4 endpoint; no alternative metrics."""
import statistics
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,checked,ref
from scripts.DFG.dfg_v2.benchmark_v2.reporting import scored
from .student import s8_gate
from .nc1_history import verify_index
from .reporting import read_artifact,aligned_rows
from .nb_reporting import paired_rows
from .nc1_reporting import check_scores

def build(root,plan):
    from .batch_nc2_controller import successful
    root=Path(root);inputs=[];folds=[]
    # All 30 S5 must pass, not only the ten primary folds.
    accepted={}
    for j in plan["jobs"][:30]:
        entry=successful(root,plan,j,deep=True)
        if entry is None:raise ValueError("All 30 S5 receipts required before S8")
        accepted[(j["task_id"],j["fold"])]=entry
        inputs.append(ref(entry[0]/"receipt.json"))
    parents=verify_index(plan["na_result_index"])
    labels=read(checked(plan["jobs"][0]["label_view"]))
    inputs.extend([plan["na_result_index"],plan["jobs"][0]["label_view"]])
    for j in plan["jobs"][:10]:
        if j["task_id"]!="reentrancy_node":raise ValueError("Wrong primary task")
        old=parents[j["baseline_job_id"]]
        baseline=(Path(old["receipt"]["path"]).parent,read(checked(old["receipt"])))
        pair=[accepted[(j["task_id"],j["fold"])],baseline]
        aligned=[]
        for job,entry in zip((j,old["job"]),pair):
            rows=aligned_rows(read_artifact(entry,"outer_test_predictions.json"),job,labels)
            check_scores(rows,read_artifact(entry,"result.json"))
            aligned.append(rows)
            inputs.append(ref(entry[0]/"fit/outer_test_predictions.json"))
            inputs.append(ref(entry[0]/"fit/result.json"))
        paired_rows(aligned[0],aligned[1],"node")
        folds.append(dict(fold=j["fold"],S5=scored(aligned[0],"best")["buggy_f1"],
                          S4=scored(aligned[1],"best")["buggy_f1"]))
    delta=statistics.mean(r["S5"]-r["S4"] for r in folds)
    gate=dict(plan=ref(root/"plan.json"),task_id="reentrancy_node",checkpoint="best",
        score_role="outer_test",metric="buggy_f1",folds=folds,mean_delta_pp=delta,
        run_S8=s8_gate(delta),inputs=inputs,source=ref(Path(__file__)))
    target=root/"s8_decision.json"
    if target.exists():
        if read(target)!=gate:raise ValueError("Existing S8 decision differs")
    else:write(target,gate)
    return gate

def verify(root,plan):
    root=Path(root);gate=read(root/"s8_decision.json")
    if gate["plan"]!=ref(root/"plan.json"):raise ValueError("S8 gate plan mismatch")
    checked(gate["source"])
    for r in gate["inputs"]:checked(r)
    if (gate["task_id"]!="reentrancy_node" or gate["checkpoint"]!="best"
        or gate["score_role"]!="outer_test" or gate["metric"]!="buggy_f1"
        or [r["fold"] for r in gate["folds"]]!=list(range(10))):
        raise ValueError("Wrong S8 endpoint")
    delta=statistics.mean(r["S5"]-r["S4"] for r in gate["folds"])
    if gate["mean_delta_pp"]!=delta or gate["run_S8"]!=s8_gate(delta):
        raise ValueError("S8 decision differs")
    return gate["run_S8"]
