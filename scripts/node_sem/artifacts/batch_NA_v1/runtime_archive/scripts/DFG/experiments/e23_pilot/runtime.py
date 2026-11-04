"""Use frozen supervision and support counting with the Stage F forward adapter."""
from types import FunctionType, SimpleNamespace
import torch
import sco_models.graph_utils as gu
from scripts.DFG.experiments import paper_runtime as old
from scripts.DFG.state.stage_f.model_adapter import reflected_input
from scripts.DFG.state.stage_f import FORWARD_RELATIONS
from .model import validate_registration

Supervision = old.Supervision
_proxy = SimpleNamespace(**dict(vars(gu), reflect_graph=reflected_input))
_support = FunctionType(old.graph_schema_and_support.__code__,
                        dict(old.graph_schema_and_support.__globals__, gu=_proxy))
def graph_schema_and_support(graph, split):
    report = _support(graph, split)
    report["enhancement_support"] = {
        rel: {phase: sum(x[phase + "_edges"] for x in report["relations"] if x["canonical"][1] == rel)
              for phase in ("train", "val")} for rel in sorted(FORWARD_RELATIONS)}
    return report

def gradient_audit(model, support):
    for name, parameter in model.named_parameters():
        if parameter.grad is not None and not torch.isfinite(parameter.grad).all():
            raise ValueError("Nonfinite parameter gradient: " + name)
    backbone = [(n,p) for n,p in model.named_parameters() if not n.startswith("classify.")]
    if not any(p.grad is not None for _,p in backbone):
        raise AssertionError("HGT disconnected from training loss")
    result = {
        "backbone_gradient_l1":sum(float(p.grad.abs().sum()) for _,p in backbone if p.grad is not None),
        "classifier_gradient_l1":sum(float(p.grad.abs().sum()) for n,p in model.named_parameters() if n.startswith("classify.") and p.grad is not None),
        "ddg_relations":[], "enhancement_relations":[],
        "ddg_training_support": support["ddg_training_edges"],
        "note":"No train support permits zero supervised gradient; weight decay is separate."}
    for row in support["relations"]:
        canonical=tuple(row["canonical"])
        if canonical[1] not in FORWARD_RELATIONS:continue
        idx=model.etypes_dict[canonical];item=dict(row)
        connected=any(layer.relation_msg.grad is not None for layer in model.gcs)
        if row["train_edges"] and not connected:
            raise AssertionError("Supported relation bank disconnected")
        for name in ("relation_msg","relation_att","relation_pri"):
            item[name+"_gradient_l1"]=sum(float(getattr(layer,name).grad[idx].abs().sum())
                for layer in model.gcs if getattr(layer,name).grad is not None)
        value=item["relation_msg_gradient_l1"]
        if not row["train_edges"] and any(item[k] != 0 for k in item if k.endswith("_gradient_l1")):
            raise AssertionError("Unexpected training gradient for val-only relation")
        item.update(message_gradient_l1=value,status="no_training_support" if not row["train_edges"] else
                    "training_support_nonzero_gradient" if value>0 else "training_support_zero_gradient_observed")
        result["enhancement_relations"].append(item)
        if canonical[1]=="DATA_DEF_USE":result["ddg_relations"].append(item)
    return result
