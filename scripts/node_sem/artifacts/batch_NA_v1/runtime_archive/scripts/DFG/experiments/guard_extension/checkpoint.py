"""Original serializer; guard-specific schema/input/protocol binding."""
from scripts.DFG.experiments import paper_checkpoint as old
from scripts.DFG.experiments.paper_protocol import NAME,VERSION as PV,FORWARD_SCOPE,SCORE_ROLE
from .common import VERSION,PAIR_VERSION,VARIANTS,TASKS,task_kind,folds
from .model import adapt,validate_registration,ADAPTER_VERSION,INITIALIZATION_VERSION,FORWARD_RELATIONS
FORMAT="author-hcg-ddg-guard-paper-checkpoint-v1"
def validate_binding(model,binding):
    expected=dict(protocol=NAME,protocol_version=PV,forward_scope=FORWARD_SCOPE,score_role=SCORE_ROLE,
                  experiment_version=VERSION,pair_version=PAIR_VERSION,
                  initialization_version=INITIALIZATION_VERSION,adapter_version=ADAPTER_VERSION)
    if any(binding.get(k)!=v for k,v in expected.items()):
        raise ValueError("Guard binding mismatch")
    tid=binding.get("task_id")
    if tid not in TASKS or binding.get("task")!=task_kind(tid) or binding.get("variant") not in VARIANTS:
        raise ValueError("Unknown task/variant")
    if binding.get("split",{}).get("fold") not in range(folds(tid)):
        raise ValueError("Invalid fold")
    if binding.get("forward_only_enhancement_relations")!=sorted(FORWARD_RELATIONS):
        raise ValueError("Guard relation direction binding mismatch")
    validate_registration(model,binding["registered_schema"])
save_checkpoint=adapt(old.save_checkpoint,validate_binding=validate_binding,FORMAT=FORMAT)
restore_checkpoint=adapt(old.restore_checkpoint,validate_binding=validate_binding,FORMAT=FORMAT)
