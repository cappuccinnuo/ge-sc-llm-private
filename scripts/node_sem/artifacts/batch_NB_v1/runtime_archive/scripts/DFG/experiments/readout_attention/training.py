"""Borrow original epoch loop; only observation and checkpoint handlers change."""
import torch
from scripts.DFG.experiments.e23_pilot import training as old
from .model import adapt,FORWARD_RELATIONS
from .runtime import gradient_audit
from .checkpoint import save_checkpoint,restore_checkpoint
from .common import write_json,READOUT
FIT=adapt(old.FIT,gradient_audit=gradient_audit,save_checkpoint=save_checkpoint,restore_checkpoint=restore_checkpoint)
_frozen_fit=adapt(old.fit,FIT=FIT,FORWARD_RELATIONS=FORWARD_RELATIONS)
assert FIT.__code__ is old.FIT.__code__ and _frozen_fit.__code__ is old.fit.__code__
def fit(model,parts,task,labels,config,dest,binding,original_ids,support,initial,fit_seed):
    result=_frozen_fit(model,parts,task,labels,config,dest,binding,original_ids,support,initial,fit_seed)
    readout_update=float((model.readout_vector.detach().cpu()-initial["readout_vector"]).abs().sum())
    audit=result["gradient_audit"]
    audit["non_classifier_update_l1_including_readout"]=audit["backbone_update_l1"]
    audit["backbone_update_l1"]=sum(float((v.detach().cpu()-initial[k]).abs().sum()) for k,v in model.state_dict().items() if not k.startswith("classify.") and k!="readout_vector")
    audit["readout_update_l1"]=readout_update
    result.update(readout=READOUT,parameters_added_vs_saved_mean=model.readout_vector.numel(),
        readout_last_norm=float(model.readout_vector.detach().norm()),readout_last_update_l1=readout_update)
    write_json(dest/"gradient_audit.json",audit);write_json(dest/"result.json",result)
    return result
