"""Strict Stage G binding around unchanged paper checkpoint serialization."""
from types import FunctionType
from scripts.DFG.experiments import paper_checkpoint as old
from scripts.DFG.experiments.checkpoint import snapshot_input, StopMonitor
from scripts.DFG.experiments.paper_protocol import NAME,VERSION,FORWARD_SCOPE,SCORE_ROLE
from scripts.DFG.state.stage_f.initialization import INITIALIZATION_VERSION
from . import EXPERIMENT_VERSION,ADAPTER_VERSION,TRIPLE_INITIALIZATION_VERSION,VARIANTS
from .model import validate_registration

FORMAT="ddg-e23-paper-cv-checkpoint-v1"
def validate_binding(model,binding):
    expected={"protocol":NAME,"protocol_version":VERSION,"forward_scope":FORWARD_SCOPE,
              "score_role":SCORE_ROLE,"experiment_version":EXPERIMENT_VERSION,
              "adapter_version":ADAPTER_VERSION,"initialization_version":INITIALIZATION_VERSION,
              "triple_initialization_version":TRIPLE_INITIALIZATION_VERSION}
    for key,value in expected.items():
        if binding.get(key)!=value:raise ValueError("Stage G binding mismatch: "+key)
    if binding.get("variant") not in VARIANTS:raise ValueError("Unknown Stage G variant")
    validate_registration(model,binding["registered_schema"])
def adapted(fn):
    return FunctionType(fn.__code__,dict(fn.__globals__,validate_binding=validate_binding,FORMAT=FORMAT),fn.__name__,fn.__defaults__,fn.__closure__)
save_checkpoint=adapted(old.save_checkpoint)
restore_checkpoint=adapted(old.restore_checkpoint)
