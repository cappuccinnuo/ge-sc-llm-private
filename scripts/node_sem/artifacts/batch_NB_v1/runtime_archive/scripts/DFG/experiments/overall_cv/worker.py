"""One serial CUDA model; exact frozen numerical trainer, separate overall binding."""
import argparse,copy,traceback,sys
from pathlib import Path
import torch
from .common import *
from scripts.DFG.experiments.paper_protocol import NAME,VERSION as PV,FORWARD_SCOPE,SCORE_ROLE,SCHEMA_POLICY
from scripts.DFG.state.stage_f.initialization import INITIALIZATION_VERSION
from scripts.DFG.experiments.e23_pilot.model import make_model,move_to_device,validate_registration,ADAPTER_VERSION
from scripts.DFG.experiments.e23_pilot.runtime import Supervision,graph_schema_and_support
from .training import fit

from .checks import check_initial

def run(output,taskid,fold,variant,attempt):
 output,attempt=Path(output),Path(attempt);plan=verify_plan(output)
 if {"task_id":taskid,"variant":variant,"fold":fold} not in plan["jobs"]:raise ValueError("Unknown task")
 if attempt.parent.resolve()!=(output/"runs"/taskid/("fold_"+str(fold))/variant).resolve() or attempt.exists():raise ValueError("Wrong/existing attempt")
 if not torch.cuda.is_available():raise RuntimeError("CUDA unavailable; no CPU fallback")
 torch.set_num_threads(plan["threads"]);torch.cuda.set_device(plan["device"]);torch.cuda.reset_peak_memory_stats(plan["device"])
 tref=task_ref(plan,taskid,fold);info=read_json(tref["manifest"])
 config=copy.deepcopy(info["config"])
 import dgl,sklearn,numpy,networkx
 observed={"python":sys.version,"torch":torch.__version__,"dgl":dgl.__version__,"sklearn":sklearn.__version__,
           "numpy":numpy.__version__,"networkx":networkx.__version__}
 if observed!=config["environment"]:raise ValueError("Frozen package environment differs")
 config.update(mode="full",maximum_training_epochs=50,experiment_version=VERSION,
               adapter_version=ADAPTER_VERSION,initialization_version=INITIALIZATION_VERSION,pair_version=PAIR_VERSION,
               plan_sha256=digest(plan),cuda_runtime=torch.version.cuda,gpu_name=torch.cuda.get_device_name(plan["device"]))
 init=info["initialization"][variant]
 record=torch.load(init["path"],map_location="cpu");check_initial(record,info,variant)
 model=make_model(info["task"],info["graphs"][variant]["path"],"cpu")
 model.load_state_dict(record["state_dict"])
 support=graph_schema_and_support(model.nx_graph,info["split"])
 if support!=info["support"][variant]:raise ValueError("Schema/support mismatch")
 validate_registration(model,support["schema"]);model=move_to_device(model,plan["device"])
 parts={n:Supervision(model,info["task"],info["split"][n+"_files"]) for n in ("train","val")}
 if {n:p.manifest for n,p in parts.items()}!=info["supervision"][variant]:raise ValueError("Supervision identity mismatch")
 labels={x["contract_name"]:int(x["targets"]) for x in read_json(info["labels_path"])}
 binding={"protocol":NAME,"protocol_version":PV,"forward_scope":FORWARD_SCOPE,"score_role":SCORE_ROLE,
  "schema_policy":SCHEMA_POLICY,"experiment_version":VERSION,"adapter_version":ADAPTER_VERSION,
  "initialization_version":INITIALIZATION_VERSION,"pair_version":PAIR_VERSION,"registered_schema":support["schema"],
  "supervision_sha256":{n:p.manifest["sha256"] for n,p in parts.items()},"support_audit_sha256":digest(support),
  "task_id":taskid,"cohort":info["cohort"],"task":info["task"],"variant":variant,"split":info["split"],
  "graph_sha256":info["graphs"][variant]["sha256"],"graph_fingerprint":info["graphs"][variant]["fingerprint"],
  "node_attributes_sha256":info["graphs"][variant]["node_attributes_sha256"],
  "graph_labels_sha256":info["labels_sha256"],"source_split_sha256":info["source_splits_sha256"],
  "source_prepared_manifest_sha256":info["source_prepared_manifest_sha256"],
  "effective_config_sha256":digest(config),"initial_weights_sha256":init["sha256"],
  "initial_state_sha256":init["state_sha256"],"pairing_audit_sha256":info["initialization_audit_sha256"],
  "plan_sha256":digest(plan),"mode":"full"}
 result=fit(model,parts,info["task"],labels,config,attempt,binding,model.original_graph_node_ids,support,
            record["state_dict"],info["fit_seed"])
 write_json(attempt/"schema_support_audit.json",support)
 write_json(attempt/"receipt.json",{"status":"complete","task_id":taskid,"variant":variant,"fold":fold,
    "plan_sha256":digest(plan),"binding_sha256":digest(binding),
    "artifacts":{str(p.relative_to(attempt)):sha256(p) for p in attempt.rglob("*") if p.is_file()}})
 print("COMPLETED",taskid,variant,result["cv_validation"],flush=True)
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument("--output",default=str(DEFAULT));p.add_argument("--task",required=True)
 p.add_argument("--fold",type=int,required=True);p.add_argument("--variant",choices=VARIANTS,required=True);p.add_argument("--attempt",required=True);a=p.parse_args()
 try:run(a.output,a.task,a.fold,a.variant,a.attempt)
 except Exception as exc:
  write_json(Path(a.attempt).with_suffix(".failure.json"),{"exception":repr(exc),"traceback":traceback.format_exc(),
      "automatic_retry":False,"task_id":a.task,"fold":a.fold,"variant":a.variant})
  raise
if __name__=="__main__":main()
