"""Prompt 8H mandatory old-input acceptance. Never authorizes bulk fits."""
import argparse
import copy
import json
from pathlib import Path
import torch
from .prepare import read, write, ref, checked
from .equivalence import nested_equal, scheduler_equal
from ..experiment import run as old
from ..experiment.preflight import run_preflight
from .acceptance_worker import _run_one as new_run
from scripts.DFG.experiments.common import tensor_digest

ROOT=Path(__file__).resolve().parents[4]
ART=ROOT/"scripts/DFG/experiments/artifacts/dfg_v2"
DEFAULT=ART/"prompt8h_v1"

def authorize(output):
    a=read(DEFAULT/"authorization.json")
    if a["formal_fit_count"]!=170 or a["label_policy"]!="L-audit" or a["seeds"]!=[1] or a["execution_location"]!="local":
        raise ValueError("Prompt8H authorization differs")
    checked(a["source_plan"]);checked(a["source_seal"]);checked(a["document"])
    if DEFAULT.resolve() not in Path(output).resolve().parents:
        raise ValueError("Acceptance output escapes new batch")
    return a

def historical_verify(output):
    authorize(output)
    from ..experiment.amendment import validate_amendment
    path=ART/"prompt8_v1/batch1/plan.json"
    amendment=ART/"prompt8b0_v1/stage_B_amendment.json"
    a=read(amendment);proof=read(checked(a["equivalence_proof"]))
    runtime=proof["runtime"]
    actual={name:ref(ROOT/name)["sha256"] for name in runtime}
    if actual!=runtime:
        raise ValueError("Historical calculation file changed")
    validate_amendment(amendment,path,current_runtime=actual)
    plan=old._load_plan(path,check_code=False)
    results={}
    for j in plan["jobs"]:
        folder=old._job_directory(path.parent,j)
        found=list(folder.glob("attempt_*/receipt.json"))
        if len(found)!=1: raise ValueError("Missing/duplicate historical receipt")
        from .archive import _verify_attempt
        result=_verify_attempt(found[0].parent,plan,j,path)
        results[old.job_id(j)]={"receipt":ref(found[0]),"complete":result["status"]=="complete"}
    write(output,dict(passed=True,approved_archive_policy="read-only bound runtime hashes; new files separately bound; old seals and executor unchanged",
        old_plan=ref(path),old_amendment=ref(amendment),runtime_files=len(actual),jobs=len(results),results=results))
    return True

def replay(kind,output):
    output=Path(output);authorize(output);output.mkdir(parents=True,exist_ok=False)
    path=ART/"prompt8_v1/batch1/plan.json"
    plan=read(path)
    job=next(j for j in plan["jobs"] if j["task_id"]=="reentrancy_node" and j["fold"]==0 and j["seed"]==1 and j["profile"]=="G0")
    if kind=="cpu":
        plan=copy.deepcopy(plan)
        plan.pop("resource_policy",None);plan.pop("resource_origin",None);plan.pop("batch_registration",None)
        plan["tasks"][job["task_id"]]["config"].update(device="cpu",maximum_training_epochs=2)
        for name,worker in (("old",old._run_one),("new",new_run)):
            worker(plan,job,output/name,path,optimize_validation=True)
        a=torch.load(str(output/"old/last.pt"),map_location="cpu");b=torch.load(str(output/"new/last.pt"),map_location="cpu")
        ah=[json.loads(x) for x in (output/"old/history.jsonl").read_text().splitlines()]
        bh=[json.loads(x) for x in (output/"new/history.jsonl").read_text().splitlines()]
        fields=("epoch","lr","adam_beta1","train_loss","inner_val_loss","inner_val","saved_best","patience_counter")
        checks=dict(two_epochs=len(ah)==len(bh)==2,
            loss_history_bitwise=all(all(x[k]==y[k] for k in fields) for x,y in zip(ah,bh)),
            parameters_bitwise=nested_equal(a["state_dict"],b["state_dict"]),
            optimizer_bitwise=nested_equal(a["optimizer"],b["optimizer"]),
            scheduler_equal=scheduler_equal(a["scheduler"],b["scheduler"]),
            predictions_equal=all(read(output/"old"/(r+"_predictions.json"))==read(output/"new"/(r+"_predictions.json")) for r in ("inner_val","outer_test")))
        report=dict(passed=all(checks.values()),checks=checks,kind="CPU old-input exact replay",formal_fits=0,epochs_each=2)
    elif kind=="gpu":
        if not read(DEFAULT/"acceptance/cpu_attempt2/report.json")["passed"]:
            raise ValueError("CPU gate has not passed")
        preflight=run_preflight(job,ref(path)["sha256"],output,plan["resource_policy"])
        attempt=output/"new"
        write(attempt.with_suffix(".started.json"),dict(purpose="Prompt8H historical acceptance replay; not a formal fit",authorization=ref(DEFAULT/"authorization.json"),job=job))
        new_run(plan,job,attempt,path,preflight=preflight,optimize_validation=True)
        historical=old._job_directory(path.parent,job)/"attempt_001"
        before,after=read(historical/"result.json"),read(attempt/"result.json")
        differences={}
        for role in ("inner_val","outer_test"):
            def keyed(rows):
                d={(r["file"],r["original_graph_node_id"]):r for r in rows}
                if len(d)!=len(rows):raise ValueError("Duplicate historical prediction identity")
                return d
            x,y=keyed(read(historical/(role+"_predictions.json"))),keyed(read(attempt/(role+"_predictions.json")))
            if set(x)!=set(y):raise ValueError("Historical prediction identity mismatch")
            differences[role]={ck:[dict(file=k[0],original_graph_node_id=k[1],before=x[k][ck],after=y[k][ck]) for k in x if x[k][ck]!=y[k][ck]] for ck in ("best","last")}
        ah=[json.loads(x) for x in (historical/"history.jsonl").read_text().splitlines()]
        bh=[json.loads(x) for x in (attempt/"history.jsonl").read_text().splitlines()]
        checks=dict(best_epoch_equal=before["best_epoch"]==after["best_epoch"],
            predicted_classes_equal=not any(v for d in differences.values() for v in d.values()))
        report=dict(passed=all(checks.values()),checks=checks,kind="GPU complete old-input historical replay",
            historical_receipt=ref(historical/"receipt.json"),new_receipt=ref(attempt/"receipt.json"),
            old_best_epoch=before["best_epoch"],new_best_epoch=after["best_epoch"],
            old_last_epoch=before["last_epoch"],new_last_epoch=after["last_epoch"],
            differences=differences,epoch_differences=[dict(epoch=i,train_loss_new_minus_old=y["train_loss"]-x["train_loss"],val_loss_new_minus_old=y["inner_val_loss"]-x["inner_val_loss"]) for i,(x,y) in enumerate(zip(ah,bh))],
            formal_fits=0,failed_gate_requires_stop_and_user_discussion=True)
    else:raise ValueError("Unknown acceptance kind")
    write(output/"report.json",report)
    if not report["passed"]:raise RuntimeError("Prompt8H mandatory acceptance failed; stop before formal fits")
    print(kind+" acceptance PASSED",flush=True)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["archive","cpu","gpu"]);a=p.parse_args()
    out=DEFAULT/"acceptance";out.mkdir(parents=True,exist_ok=True)
    if a.command=="archive":historical_verify(out/"historical_archive.json")
    else:replay(a.command,out/("cpu_attempt2" if a.command=="cpu" else a.command))
if __name__=="__main__":main()
