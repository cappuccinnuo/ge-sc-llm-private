"""Same fit completion rules plus zero untrained attention and separate audit."""
import torch
from scripts.DFG.experiments.overall_cv import checks as prior
from .common import *
from .model import adapt
_original_initial=adapt(prior.check_initial,PAIR_VERSION=PAIR_VERSION)
def check_initial(record,info,variant):
    _original_initial(record,info,variant)
    if record.get("readout")!=READOUT:raise ValueError("Initial readout identity drift")
    a=record["state_dict"].get("readout_vector")
    if a is None or tuple(a.shape)!=(128,) or not torch.equal(a,torch.zeros_like(a)):raise ValueError("Attention initial must be zero")
_completed=adapt(prior.completed,job_dir=job_dir)
def completed(output,job,plan):
    dest=_completed(output,job,plan)
    if dest is None:return None
    result=read_json(dest/"result.json");binding=read_json(dest/"binding.json")
    if binding.get("readout")!=READOUT or result.get("readout")!=READOUT:raise ValueError("Missing readout binding")
    if result.get("parameters_added_vs_saved_mean")!=128:raise ValueError("Unexpected parameter intervention")
    epochs=result["gradient_audit"]["epochs"]
    if any(not x["readout"]["connected"] for x in epochs):raise ValueError("Disconnected attention")
    return dest
