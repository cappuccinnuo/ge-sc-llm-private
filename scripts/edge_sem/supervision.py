"""EP7 registration-only supervision adapter.
Source: scripts/DFG/dfg_v2/benchmark_v2/audit_supervision.py; SHA recorded below.
Targets, include masks, row identity and file pooling are inherited unchanged.
"""
from scripts.DFG.dfg_v2.benchmark_v2.audit_supervision import AuditSupervision,bind_rows
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PROTOCOL_NAME
from .model import validate_registration

class EdgeSupervision(AuditSupervision):
    def forward(self,model):
        validate_registration(model,deep=False)
        return model()[self.mask] if self.task=="node" else model(self.files)[0]

def make_part(model,task,files,binding):
    if binding["protocol"]!=PROTOCOL_NAME:raise ValueError("EdgeSem requires grouped nested supervision")
    table=bind_rows(model,binding["task_id"],binding["label_view"])
    return EdgeSupervision(model,task,files,table,binding["label_policy"])

FROZEN_SOURCE_SHA256 = '51c06300f6172d7286984aa18c48e8c0458f78a6bdb4de1a7ad9e8bb79affaf1'
