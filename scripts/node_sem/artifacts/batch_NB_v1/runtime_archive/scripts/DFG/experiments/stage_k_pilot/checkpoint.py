"""Distinct batch binding; serialization and training numerics are reused."""
from types import FunctionType
from scripts.DFG.experiments import paper_checkpoint as old
from scripts.DFG.experiments.paper_protocol import NAME,VERSION as PROTOCOL_VERSION,FORWARD_SCOPE,SCORE_ROLE
from scripts.DFG.state.stage_f.initialization import INITIALIZATION_VERSION
from scripts.DFG.experiments.e23_pilot.model import validate_registration
from . import VERSION,VARIANTS
FORMAT="ddg-stage-k-overall-checkpoint-v1"
def validate_binding(model,binding):
 expected={"protocol":NAME,"protocol_version":PROTOCOL_VERSION,"forward_scope":FORWARD_SCOPE,
           "score_role":SCORE_ROLE,"experiment_version":VERSION,"initialization_version":INITIALIZATION_VERSION}
 for k,v in expected.items():
  if binding.get(k)!=v:raise ValueError("K binding mismatch: "+k)
 if binding.get("variant") not in VARIANTS or binding["split"]["fold"]!=0:raise ValueError("K variant/fold mismatch")
 validate_registration(model,binding["registered_schema"])
def adapted(fn):
 return FunctionType(fn.__code__,dict(fn.__globals__,validate_binding=validate_binding,FORMAT=FORMAT),
                     fn.__name__,fn.__defaults__,fn.__closure__)
save_checkpoint=adapted(old.save_checkpoint)
restore_checkpoint=adapted(old.restore_checkpoint)
