"""One candidate per process, original numerical training loop."""
import argparse,traceback
from pathlib import Path
from scripts.DFG.experiments.overall_cv import worker as old
from .common import *
from .model import adapt,make_model,validate_registration,ADAPTER_VERSION,INITIALIZATION_VERSION,FORWARD_RELATIONS
from .runtime import Supervision,graph_schema_and_support
from .checks import check_initial
from .training import fit as frozen_fit

def fit(model,parts,task,labels,config,dest,binding,original_ids,support,initial,fit_seed):
    config["readout"]=READOUT;binding["readout"]=READOUT
    plan=read_json(Path(dest).parents[4]/"plan.json")
    if digest(plan)!=binding["plan_sha256"]:raise ValueError("Worker source plan mismatch")
    info=read_json(task_ref(plan,binding["task_id"],binding["split"]["fold"])["manifest"])
    binding["source_mean"]=info["mean_sources"][binding["variant"]]
    if model.readout_graph_kind!=binding["variant"]:raise ValueError("Worker graph-kind mismatch")
    config["forward_only_enhancement_relations"]=sorted(FORWARD_RELATIONS)
    binding["forward_only_enhancement_relations"]=sorted(FORWARD_RELATIONS)
    binding["effective_config_sha256"]=digest(config)
    return frozen_fit(model,parts,task,labels,config,dest,binding,original_ids,support,initial,fit_seed)
run=adapt(old.run,verify_plan=verify_plan,make_model=make_model,validate_registration=validate_registration,
    graph_schema_and_support=graph_schema_and_support,Supervision=Supervision,check_initial=check_initial,
    fit=fit,VERSION=VERSION,PAIR_VERSION=PAIR_VERSION,ADAPTER_VERSION=ADAPTER_VERSION,INITIALIZATION_VERSION=INITIALIZATION_VERSION)
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",default=str(DEFAULT));p.add_argument("--task",required=True)
    p.add_argument("--fold",type=int,required=True);p.add_argument("--variant",choices=VARIANTS,required=True);p.add_argument("--attempt",required=True);a=p.parse_args()
    try:run(a.output,a.task,a.fold,a.variant,a.attempt)
    except Exception as exc:
        write_json(Path(a.attempt).with_suffix(".failure.json"),dict(exception=repr(exc),traceback=traceback.format_exc(),
            automatic_retry=False,task_id=a.task,fold=a.fold,variant=a.variant));raise
if __name__=="__main__":main()
