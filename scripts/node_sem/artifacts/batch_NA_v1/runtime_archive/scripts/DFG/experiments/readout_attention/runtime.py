"""Separate HGT and readout gradients; supervision and relation audits unchanged."""
import torch
from scripts.DFG.experiments.guard_extension.runtime import Supervision,graph_schema_and_support
from scripts.DFG.experiments.guard_extension.runtime import gradient_audit as prior_audit

def gradient_audit(model,support):
    result=prior_audit(model,support)
    hgt=[(n,p) for n,p in model.named_parameters() if n.startswith(("gcs.","adapt_ws."))]
    if not hgt or not any(p.grad is not None for _,p in hgt):raise AssertionError("HGT disconnected, readout gradients cannot substitute")
    p=model.readout_vector
    if p.grad is None:raise AssertionError("Attention readout disconnected")
    if not torch.isfinite(p.grad).all():raise ValueError("Nonfinite readout gradient")
    result["backbone_gradient_l1"]=sum(float(p.grad.abs().sum()) for n,p in model.named_parameters()
        if not n.startswith("classify.") and n!="readout_vector" and p.grad is not None)
    result["hgt_gradient_l1"]=sum(float(p.grad.abs().sum()) for _,p in hgt if p.grad is not None)
    result["readout"]={"connected":True,"gradient_l1":float(p.grad.abs().sum()),
        "weight_l1":float(p.detach().abs().sum()),"zero_gradient_allowed":True}
    return result
