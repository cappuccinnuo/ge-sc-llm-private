"""Frozen C1 targets and C2 include mask, separate from immutable HCG labels."""
import copy
import torch
from ..supervision import DfgV2Supervision
from .. import AUX_NODE_TYPES
from ..tasks import checked_ref
from scripts.DFG.integration.io import read_json
from scripts.DFG.experiments.common import digest
from .protocol import PROTOCOL_NAME

def bind_rows(model, task_id, view_ref):
    rows = read_json(checked_ref(view_ref))[task_id]
    task = model.dfg_task
    key = (lambda r: (r["file"], r["original_graph_node_id"])) if task == "node" else (lambda r: r["file"])
    table = {key(r): r for r in rows}
    if len(table) != len(rows):
        raise ValueError("Duplicate label-view identity")
    originals = [(i, d) for i,d in model.nx_graph.nodes(data=True) if d["node_type"] not in AUX_NODE_TYPES]
    expected = ({(d["source_file"],model.original_graph_node_ids[i]) for i,d in originals}
                if task == "node" else {d["source_file"] for i,d in originals})
    if set(table) != expected:
        raise ValueError("Label-view population/identity differs from graph")
    for i,d in originals:
        r = table[(d["source_file"],model.original_graph_node_ids[i])] if task == "node" else table[d["source_file"]]
        if task == "node" and (r["node_type"] != d["node_type"] or r["orig"] != model.node_labels[i]):
            raise ValueError("Original node label/type differs from frozen diagnostic view")
        for policy in ("L-orig", "L-audit"):
            if type(r[policy+"_include"]) is not bool or type(r[policy+"_target"]) is not int or r[policy+"_target"] not in (0,1):
                raise ValueError("Invalid target or include flag")
        if task == "contract" and (not r["L-audit_include"] or r["L-audit_target"] != r["orig"]):
            raise ValueError("Contract labels must remain unchanged")
    return table

class AuditSupervision(DfgV2Supervision):
    def __init__(self, model, task, files, table, policy="L-audit"):
        super().__init__(model,task,files)
        if policy not in ("L-orig","L-audit"):
            raise ValueError("Unknown label policy")
        self.policy = policy
        self.all_full_ids = list(self.full_ids)
        self.audit_targets = torch.full((model.total_nodes,), -1, dtype=torch.long, device=model.device)
        self.audit_include = torch.zeros(model.total_nodes,dtype=torch.bool,device=model.device)
        if task == "node":
            for i in self.all_full_ids:
                d=model.nx_graph.nodes[i]
                r=table[(d["source_file"],model.original_graph_node_ids[i])]
                self.audit_targets[i]=r[policy+"_target"]
                self.audit_include[i]=r[policy+"_include"]
            self.mask = self.mask & self.audit_include
            self.full_ids = [i for i in self.all_full_ids if bool(self.mask[i])]
            if not self.full_ids:
                raise ValueError("Label mask leaves no supervised nodes")
        self.manifest.update(label_policy=policy,model_node_ids=self.full_ids,
            all_original_model_node_ids=self.all_full_ids,
            targets_sha256=digest(self.audit_targets.cpu().tolist()),
            include_sha256=digest(self.audit_include.cpu().tolist()))
        self.manifest.pop("sha256",None)
        self.manifest["sha256"]=digest(self.manifest)

    def targets(self,model,labels):
        if self.task=="contract":
            return super().targets(model,labels)
        return self.audit_targets[self.mask]

    def forward(self,model):
        from .runtime_model import validate_registration
        validate_registration(model,deep=False)
        return model()[self.mask] if self.task=="node" else model(self.files)[0]

def make_part(model,task,files,binding):
    if binding["protocol"] != PROTOCOL_NAME:
        return DfgV2Supervision(model,task,files)
    table=bind_rows(model,binding["task_id"],binding["label_view"])
    return AuditSupervision(model,task,files,table,binding["label_policy"])
