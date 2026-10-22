"""Original serializer plus strict readout architecture/batch binding."""
from scripts.DFG.experiments import paper_checkpoint as old
from scripts.DFG.experiments.paper_protocol import NAME,VERSION as PV,FORWARD_SCOPE,SCORE_ROLE
from .common import VERSION,PAIR_VERSION,VARIANTS,TASKS,task_kind,folds,READOUT
from .model import adapt,validate_registration,ADAPTER_VERSION,INITIALIZATION_VERSION,FORWARD_RELATIONS
FORMAT="author-hcg-attention-paper-checkpoint-v1"
def validate_binding(model,binding):
    expected=dict(protocol=NAME,protocol_version=PV,forward_scope=FORWARD_SCOPE,score_role=SCORE_ROLE,
        experiment_version=VERSION,pair_version=PAIR_VERSION,initialization_version=INITIALIZATION_VERSION,
        adapter_version=ADAPTER_VERSION,readout=READOUT)
    if any(binding.get(k)!=v for k,v in expected.items()):raise ValueError("Attention binding mismatch")
    tid=binding.get("task_id")
    if tid not in TASKS or binding.get("task")!="contract" or binding.get("variant") not in VARIANTS:raise ValueError("Unknown task/variant")
    if binding.get("split",{}).get("fold") not in range(5):raise ValueError("Invalid fold")
    if binding.get("forward_only_enhancement_relations")!=sorted(FORWARD_RELATIONS):raise ValueError("Relation direction drift")
    if model.readout_graph_kind!=binding["variant"]:raise ValueError("Graph kind binding mismatch")
    source=binding.get("source_mean",{})
    if not all(source.get(k) for k in ("manifest_sha256","initial_sha256","initial_state_sha256","receipt_sha256")):raise ValueError("Missing historical mean binding")
    vector=getattr(model,"readout_vector",None)
    if vector is None or tuple(vector.shape)!=(model.hidden_size,) or vector.numel()!=READOUT["additional_parameters"] or not vector.requires_grad or vector.dtype!=model.classify.weight.dtype:raise ValueError("Wrong attention parameter architecture")
    validate_registration(model,binding["registered_schema"])
save_checkpoint=adapt(old.save_checkpoint,validate_binding=validate_binding,FORMAT=FORMAT)
restore_checkpoint=adapt(old.restore_checkpoint,validate_binding=validate_binding,FORMAT=FORMAT)
