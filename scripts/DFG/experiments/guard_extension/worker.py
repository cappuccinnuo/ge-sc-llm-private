"""One CUDA candidate; delegate the unchanged frozen worker numerical path."""
import argparse,traceback
from pathlib import Path
from scripts.DFG.experiments.overall_cv import worker as old
from .common import *
from .model import adapt,make_model,validate_registration,ADAPTER_VERSION,INITIALIZATION_VERSION
from .runtime import graph_schema_and_support,Supervision
from .checks import check_initial
from .training import fit as frozen_fit
from .model import FORWARD_RELATIONS

def fit(model,parts,task,labels,config,dest,binding,original_ids,support,initial,fit_seed):
    # Metadata-only adapter; the borrowed worker and trainer numeric code is unchanged.
    config["forward_only_enhancement_relations"]=sorted(FORWARD_RELATIONS)
    binding["forward_only_enhancement_relations"]=sorted(FORWARD_RELATIONS)
    binding["effective_config_sha256"]=digest(config)
    return frozen_fit(model,parts,task,labels,config,dest,binding,original_ids,support,initial,fit_seed)
run=adapt(old.run,verify_plan=verify_plan,make_model=make_model,validate_registration=validate_registration,
          graph_schema_and_support=graph_schema_and_support,Supervision=Supervision,
          check_initial=check_initial,fit=fit,VERSION=VERSION,PAIR_VERSION=PAIR_VERSION,
          ADAPTER_VERSION=ADAPTER_VERSION,INITIALIZATION_VERSION=INITIALIZATION_VERSION)
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",default=str(DEFAULT));p.add_argument("--task",required=True)
    p.add_argument("--fold",type=int,required=True);p.add_argument("--variant",choices=VARIANTS,required=True)
    p.add_argument("--attempt",required=True);a=p.parse_args()
    try:run(a.output,a.task,a.fold,a.variant,a.attempt)
    except Exception as exc:
        write_json(Path(a.attempt).with_suffix(".failure.json"),dict(exception=repr(exc),
          traceback=traceback.format_exc(),automatic_retry=False,task_id=a.task,fold=a.fold,variant=a.variant))
        raise
if __name__=="__main__":main()
