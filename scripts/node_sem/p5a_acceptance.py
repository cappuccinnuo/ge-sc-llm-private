"""NS-P5A CPU gates. These are acceptance fits, never formal results."""
import argparse
import copy
import gc
import json
from pathlib import Path
import time
import traceback
import numpy as np
import torch
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, checked, ref
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.model import make_model
from scripts.DFG.experiments.common import seed_all, tensor_digest
from scripts.labeling_v2.safe_graph import read_graph
from . import batch_na_worker as worker
from . import p4_acceptance
from .carrier import carry
from .init import checked_initial
from .model import make_nodesem_model
from .na_carrier import load_carrier, construct_carried
from .feature_spec import FeatureSpec
from .checkpoint_io import load_checked
from .equivalence import assert_exact, snapshot

OUT=worker.OUT/"acceptance"


def carrier_proof(plan,out):
    checks=[]
    for job in plan["jobs"]:
        if job["fold"]!=0:continue
        started=time.monotonic()
        graph=read_graph(checked(job["graph"]));before=graph_fingerprint(graph)
        direct,record,spec=load_carrier(job)
        original,original_record=carry(graph,spec,job["task_id"])
        assert_exact(record,original_record,"carrier_record")
        assert_exact(list(direct),list(original),"node_order")
        if not all(np.array_equal(direct.nodes[n]["token"],original.nodes[n]["token"]) for n in graph):
            raise AssertionError("Direct carrier differs")
        if graph_fingerprint(graph)!=before:raise AssertionError("Original graph mutated")
        token_equal=None
        if job["name"]=="S0o":
            token_equal=all(np.array_equal(direct.nodes[n]["token"],graph.nodes[n]["token"]) for n in graph)
            if not token_equal:raise AssertionError("S0o original token differs")
        # Also prove model allocation/RNG order for each of the 32 groups.
        seed_all(job["seeds"]["constructor"])
        a=construct_carried(job,direct,record,spec);sa=snapshot(a);del a
        seed_all(job["seeds"]["constructor"])
        b=make_nodesem_model(job["granularity"],job["graph"],job["profile"],spec,
                            job["config"],"cpu",job["task_id"])
        assert_exact(sa,snapshot(b),"fresh_model")
        del sa,b,graph,direct,original
        row=dict(job_id=worker.job_id(job),passed=True,carrier=job["feature_view"],
            spec=job["spec"],original_tokens_exact=token_equal,
            fresh_model_parameters_features_schema_exact=True,seconds=time.monotonic()-started)
        checks.append(row)
        write(out/(worker.job_id(job)+".json"),row)
        print("carrier/model proof {}/32 {} {:.1f}s".format(len(checks),worker.job_id(job),row["seconds"]),flush=True)
        gc.collect()
    if len(checks)!=32:raise ValueError("Expected 32 carrier groups")
    result=dict(passed=True,count=32,plan=ref(worker.OUT/"plan.json"),checks=checks)
    write(out/"carrier_proof.json",result)
    return result


def compare_folders(left,right,epochs):
    left,right=Path(left),Path(right)
    histories=[]
    for folder in (left,right):
        histories.append([{k:v for k,v in json.loads(line).items() if k!="seconds"}
            for line in (folder/"history.jsonl").read_text().splitlines()])
    assert_exact(histories[0],histories[1],"history")
    if len(histories[0])!=epochs:raise AssertionError("Acceptance epoch count differs")
    states={}
    for ck in ("best","last"):
        a=load_checked(ref(left/(ck+".pt")));b=load_checked(ref(right/(ck+".pt")))
        for k in ("state_dict","state_sha256","optimizer","scheduler","epoch","monitor"):
            assert_exact(a[k],b[k],ck+"/"+k)
        states[ck]=a["state_sha256"];del a,b
    for role in ("inner_val","outer_test","inner_val_orig_all","outer_test_orig_all"):
        assert_exact(read(left/(role+"_predictions.json")),read(right/(role+"_predictions.json")),role)
    return dict(passed=True,epochs=epochs,history=histories[0],checkpoint_tensor_digests=states,
        predictions_bitwise=True,adam_and_scheduler_exact=True,history_exclusion="wall-clock seconds only",
        formal_fits=0)


def cpu_proof(plan,out):
    j=copy.deepcopy(next(j for j in plan["jobs"] if j["task_id"]=="reentrancy_node"
        and j["profile"]=="G3R" and j["name"]=="S4" and j["fold"]==0))
    j["actual_device"]="cpu"
    local_plan=dict(plan,h8_constructor_seconds=1.0)
    write(out/"plan.json",local_plan)
    # Old acceptance path remains unchanged, including its diagnostic hooks.
    p4_acceptance.run_fit(local_plan,j,output_root=out,run_directory=out/"old_worker")
    model=worker.construct(j)
    cfg=copy.deepcopy(j["config"]);cfg["maximum_training_epochs"]=1
    worker.run_core(plan,j,model,cfg,out/"new_worker",purpose="CPU_worker_equivalence_only")
    del model;gc.collect()
    records=[dict(name="S4_worker",**compare_folders(out/"old_worker",out/"new_worker",1))]
    for task,profile in (("reentrancy_node","G3R"),("access_control_contract","G0")):
        job=next(j for j in plan["jobs"] if j["task_id"]==task and j["profile"]==profile
            and j["name"]=="S0o" and j["fold"]==0)
        initial=checked_initial(job["initial"],task,0,profile,spec_digest=job["spec_sha256"])
        old=checked_initial(job["h8_initial"],task,0,profile)
        assert_exact(initial["state_dict"],old["state_dict"],"S0o_h8_initial")
        cfg=copy.deepcopy(job["config"]);cfg["maximum_training_epochs"]=2
        carried,record,spec=load_carrier(job)
        seed_all(job["seeds"]["constructor"])
        baseline=make_model(job["granularity"],carried,profile,"cpu",node_feature="inside_token",
            hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"],
            reducer="mean",layer_impl=cfg["layer_impl"])
        # Metadata is used only for binding; the baseline uses original Linear adapters.
        baseline.nodesem_spec=spec.to_json();baseline.nodesem_spec_sha256=spec.digest()
        baseline.load_state_dict(old["state_dict"],strict=True)
        model=worker.construct(job)
        assert_exact(snapshot(baseline),snapshot(model),"S0_baseline_initial")
        left=out/(task+"_baseline");right=out/(task+"_nodesem")
        worker.run_core(plan,job,baseline,cfg,left,purpose="CPU_S0_equivalence_only")
        del baseline;gc.collect()
        worker.run_core(plan,job,model,cfg,right,purpose="CPU_S0_equivalence_only")
        del model,old,initial;gc.collect()
        records.append(dict(name=task+"_S0o",**compare_folders(left,right,2)))
        print("S0o 2-epoch equivalence PASS "+task,flush=True)
    result=dict(passed=True,plan=ref(worker.OUT/"plan.json"),checks=records,
        formal_fits=0,cpu_acceptance_fits=6,device="cpu")
    write(out/"cpu_proof.json",result);return result


def main():
    p=argparse.ArgumentParser();p.add_argument("stage",choices=("carriers","cpu"))
    a=p.parse_args();torch.set_num_threads(2)
    out=OUT/a.stage;out.mkdir(parents=True,exist_ok=False)
    write(out/"started.json",dict(started=time.time(),stage=a.stage))
    try:
        plan=worker.load_plan()
        (carrier_proof if a.stage=="carriers" else cpu_proof)(plan,out)
    except BaseException as error:
        write(out/"failure.json",dict(error=repr(error),traceback=traceback.format_exc(),automatic_retry=False));raise


if __name__=="__main__":main()
