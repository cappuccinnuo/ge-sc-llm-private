"""N-C2 initialization: exact S4 common parameters, S5/S8 exact full pairing."""
import torch
from scripts.DFG.experiments.common import tensor_digest
from .init import initial_state
from .nc1_init import baseline_state

VERSION="nodesem-nc2-s4-student-paired-v1"

def merge_common(candidate,baseline):
    extra=set(candidate)-set(baseline)
    if not baseline or not extra or not set(baseline)<set(candidate):
        raise ValueError("Student must strictly extend S4")
    if any(not(k.startswith("adapt_ws.") and (".norm.student." in k or ".proj.student." in k)) for k in extra):
        raise ValueError("Unexpected non-STUDENT new parameter")
    merged={k:v.detach().cpu().clone() for k,v in candidate.items()}
    for k,v in baseline.items():
        if merged[k].shape!=v.shape or merged[k].dtype!=v.dtype:raise ValueError("Common tensor shape differs")
        merged[k]=v.detach().cpu().clone()
    return merged,dict(common_bitwise_equal=True,common_keys=len(baseline),student_keys=sorted(extra),
                       baseline_state_sha256=tensor_digest(baseline))

def paired_state(model,spec,job,baseline):
    state,_=initial_state(model,spec,job["task_id"],job["fold"],job["profile"],job["h8_initial"])
    return merge_common(state,baseline)

def apply_dropout_pair(model,job):
    """Only S8's RNG identity uses S5; actual S8 spec/bindings remain unchanged."""
    if job["name"]=="S8":
        if job["paired_random_spec_sha256"]==job["spec_sha256"]:
            raise ValueError("S8 must bind its separate feature specification")
        for adapter in model.adapt_ws:
            if adapter.spec_digest!=job["spec_sha256"]:raise ValueError("Adapter digest differs")
            adapter.spec_digest=job["paired_random_spec_sha256"]
    elif job["paired_random_spec_sha256"]!=job["spec_sha256"]:
        raise ValueError("S5 random identity differs")
    return model
