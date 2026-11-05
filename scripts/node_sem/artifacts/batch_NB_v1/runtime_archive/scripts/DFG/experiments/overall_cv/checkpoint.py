"""Reuse checkpoint serialization; bind overall experiment identity and original fold."""
from types import FunctionType
from scripts.DFG.experiments import paper_checkpoint as old
from scripts.DFG.experiments.paper_protocol import NAME,VERSION as PV,FORWARD_SCOPE,SCORE_ROLE
from scripts.DFG.state.stage_f.initialization import INITIALIZATION_VERSION
from scripts.DFG.experiments.e23_pilot.model import validate_registration,ADAPTER_VERSION
from .common import VERSION,VARIANTS,PAIR_VERSION,TASKS,task_kind,folds
FORMAT="ddg-overall-paper-checkpoint-v1"
def validate_binding(model,binding):
 expected=dict(protocol=NAME,protocol_version=PV,forward_scope=FORWARD_SCOPE,score_role=SCORE_ROLE,
     experiment_version=VERSION,pair_version=PAIR_VERSION,initialization_version=INITIALIZATION_VERSION,adapter_version=ADAPTER_VERSION)
 if any(binding.get(k)!=v for k,v in expected.items()):raise ValueError("Overall binding mismatch")
 tid=binding.get("task_id")
 if tid not in TASKS or binding.get("task")!=task_kind(tid) or binding.get("variant") not in VARIANTS:raise ValueError("Unknown task/variant")
 if binding.get("split",{}).get("fold") not in range(folds(tid)):raise ValueError("Invalid fold")
 validate_registration(model,binding["registered_schema"])
def adapted(fn):
 return FunctionType(fn.__code__,dict(fn.__globals__,validate_binding=validate_binding,FORMAT=FORMAT),fn.__name__,fn.__defaults__,fn.__closure__)
save_checkpoint=adapted(old.save_checkpoint)
restore_checkpoint=adapted(old.restore_checkpoint)
