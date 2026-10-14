"""One model/one fit in a short-lived GPU process; sealed initial state only."""
import argparse,copy,traceback,sys
from pathlib import Path
import torch
from scripts.DFG.experiments.common import read_json,write_json,sha256,digest,tensor_digest
from scripts.DFG.experiments.paper_protocol import NAME,VERSION,FORWARD_SCOPE,SCORE_ROLE,SCHEMA_POLICY
from scripts.DFG.state.stage_f.initialization import INITIALIZATION_VERSION
from . import EXPERIMENT_VERSION,ADAPTER_VERSION,TRIPLE_INITIALIZATION_VERSION
from .control import verify_plan
from .model import make_model,move_to_device,validate_registration
from .runtime import Supervision,graph_schema_and_support
from .training import fit
def run(output,task_id,variant,mode,attempt):
    output,attempt=Path(output),Path(attempt);plan=verify_plan(output)
    job=next(j for j in plan["jobs"] if j["task_id"]==task_id and j["variant"]==variant)
    expected_parent=output/("smoke" if mode=="smoke" else "runs")/task_id/"fold_0"/variant
    if attempt.parent.resolve()!=expected_parent.resolve() or attempt.exists():raise ValueError("Invalid or existing attempt")
    if not torch.cuda.is_available():raise RuntimeError("CUDA unavailable; CPU fallback is forbidden")
    torch.set_num_threads(plan["threads"]);torch.cuda.set_device(plan["device"]);torch.cuda.reset_peak_memory_stats(plan["device"])
    info=read_json(job["task_manifest"]);config=copy.deepcopy(info["config"])
    config.update(mode=mode,maximum_training_epochs=3 if mode=="smoke" else 50,
                  experiment_version=EXPERIMENT_VERSION,adapter_version=ADAPTER_VERSION,
                  initialization_version=INITIALIZATION_VERSION,triple_initialization_version=TRIPLE_INITIALIZATION_VERSION,
                  source_config_sha256=info["source_config_sha256"],pilot_plan_sha256=digest(plan))
    import dgl, sklearn, numpy, networkx
    observed={"python":sys.version,"torch":torch.__version__,"dgl":dgl.__version__,
              "sklearn":sklearn.__version__,"numpy":numpy.__version__,"networkx":networkx.__version__}
    if observed!=info["config"]["environment"]:
        raise ValueError("Runtime package versions differ from frozen configuration: "+repr(observed))
    config["environment"]=observed
    config["environment_observation"]="measured in this worker before model creation"
    config["cuda_runtime"]=torch.version.cuda
    config["gpu_name"]=torch.cuda.get_device_name(plan["device"])
    init=info["initialization"][variant]
    if sha256(init["path"])!=init["sha256"]:raise ValueError("Untrained initial bytes changed")
    record=torch.load(init["path"],map_location="cpu")
    if record["kind"]!="untrained_initial" or record["optimizer_steps"]!=0 or record["variant"]!=variant or record["task_id"]!=task_id:raise ValueError("Wrong initial identity")
    if tensor_digest(record["state_dict"])!=init["state_sha256"]:raise ValueError("Initial tensor digest changed")
    model=make_model(info["task"],info["graphs"][variant]["path"],"cpu")
    model.load_state_dict(record["state_dict"])
    support=graph_schema_and_support(model.nx_graph,info["split"])
    if support!=info["support"][variant]:raise ValueError("Schema/support differs from preparation")
    validate_registration(model,support["schema"])
    model=move_to_device(model,plan["device"])
    parts={n:Supervision(model,info["task"],info["split"][n+"_files"]) for n in ("train","val")}
    if {n:p.manifest for n,p in parts.items()}!=info["supervision"][variant]:raise ValueError("Supervised row identities changed")
    labels={r["contract_name"]:int(r["targets"]) for r in read_json(info["labels_path"])}
    binding={"protocol":NAME,"protocol_version":VERSION,"forward_scope":FORWARD_SCOPE,"score_role":SCORE_ROLE,"schema_policy":SCHEMA_POLICY,
        "experiment_version":EXPERIMENT_VERSION,"adapter_version":ADAPTER_VERSION,
        "initialization_version":INITIALIZATION_VERSION,"triple_initialization_version":TRIPLE_INITIALIZATION_VERSION,
        "registered_schema":support["schema"],"supervision_sha256":{n:p.manifest["sha256"] for n,p in parts.items()},
        "support_audit_sha256":digest(support),"cohort":info["cohort"],"variant":variant,"task":info["task"],
        "graph_sha256":info["graphs"][variant]["sha256"],"graph_fingerprint":info["graphs"][variant]["fingerprint"],
        "graph_labels_sha256":info["labels_sha256"],"node_attributes_sha256":info["graphs"][variant]["node_attributes_sha256"],
        "source_prepared_manifest_sha256":info["source_prepared_manifest_sha256"],"source_split_manifest_sha256":info["source_splits_sha256"],
        "split":info["split"],"effective_config_sha256":digest(config),"initial_weights_sha256":init["sha256"],
        "initial_state_sha256":init["state_sha256"],"pairing_audit_sha256":info["initialization_audit_sha256"],
        "pilot_plan_sha256":digest(plan),"mode":mode}
    result=fit(model,parts,info["task"],labels,config,attempt,binding,model.original_graph_node_ids,support,record["state_dict"],info["fit_seed"])
    write_json(attempt/"schema_support_audit.json",support)
    write_json(attempt/"receipt.json",{"status":"complete","job":job,"mode":mode,"plan_sha256":digest(plan),
        "binding_sha256":digest(binding),"result_sha256":sha256(attempt/"result.json"),
        "artifact_sha256":{str(p.relative_to(attempt)):sha256(p) for p in sorted(attempt.rglob("*")) if p.is_file()}})
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True);p.add_argument("--task",required=True)
    p.add_argument("--variant",choices=("E2","E3a","E3b"),required=True);p.add_argument("--mode",choices=("smoke","full"),required=True)
    p.add_argument("--attempt",required=True);a=p.parse_args()
    try:run(a.output,a.task,a.variant,a.mode,a.attempt)
    except Exception as exc:
        failure=Path(a.attempt).with_suffix(".failure.json")
        write_json(failure,{"status":"failed","exception":repr(exc),"traceback":traceback.format_exc(),"mode":a.mode,"task":a.task,"variant":a.variant,"automatic_retry":False})
        raise
if __name__=="__main__":main()
