"""Independent NS-P4 artifact validation, without fitting or changing history."""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
import torch
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from .init import checked_initial
from .checkpoint_io import load_checked
from .feature_spec import FeatureSpec


def verify_report(report,job):
    if report.get("job")!=job or report.get("passed") is not True or report.get("formal_fit") is not False:
        raise ValueError("Acceptance identity/status differs")
    cfg=copy.deepcopy(job["config"]);cfg["maximum_training_epochs"]=1
    if (report.get("effective_config")!=cfg or report.get("epochs")!=1
            or report.get("only_config_override")!="maximum_training_epochs"):
        raise ValueError("Smoke config changed beyond the one-epoch cap")
    h=report["history"]
    if len(h)!=1 or h[0]["epoch"]!=0 or not all(np.isfinite(h[0][k]) for k in ("train_loss","inner_val_loss")):
        raise ValueError("Finite single-epoch history absent")
    expected={r:{c:True for c in ("best","last")} for r in ("inner_val","outer_test")}
    if report.get("checkpoint_roundtrip_exact")!=expected: raise ValueError("Checkpoint reload not exact")
    if not report.get("common_initial_exact"): raise ValueError("Common initialization proof absent")
    if not report.get("modality_projection_gradient_l1") or not all(np.isfinite(x) and x>0 for x in report["modality_projection_gradient_l1"].values()):
        raise ValueError("Modality projection gradient absent/nonfinite")
    if not report.get("gradients") or not all(v["finite"] for v in report["gradients"].values()):
        raise ValueError("Nonfinite adapter gradient")
    return True


def verify(root,device="cpu"):
    root=Path(root);plan_ref=read(root/"plan.seal.json")["plan"];plan=read(checked(plan_ref))
    jobs=[j for j in plan["jobs"] if j["actual_device"]==device]
    if len(jobs)!=(7 if device=="cpu" else 2): raise ValueError("Incorrect smoke/probe matrix")
    checks=[]
    for j in jobs:
        folder=root/"runs"/device/j["name"]
        seal=read(folder/"acceptance.seal.json")
        if seal["plan"]!=plan_ref: raise ValueError("Acceptance belongs to another plan")
        report=read(checked(seal["acceptance"]))
        if checked(seal["acceptance"]).resolve()!= (folder/"acceptance.json").resolve(): raise ValueError("Misplaced acceptance")
        verify_report(report,j)
        spec=FeatureSpec.from_json(read(checked(j["spec"])))
        initial=checked_initial(j["initial"],j["task_id"],0,j["profile"],spec_digest=spec.digest())
        old=checked_initial(j["h8_initial"],j["task_id"],0,j["profile"])
        shared={k for k in initial["state_dict"] if k.startswith(("gcs.","classify."))}
        expected={k for k in old["state_dict"] if k.startswith(("gcs.","classify."))}
        if spec.layers==0: expected={k for k in expected if k.startswith("classify.")}
        if shared!=expected or not all(torch.equal(initial["state_dict"][k],old["state_dict"][k]) for k in shared):
            raise ValueError("Independent initial shared-parameter comparison failed")
        del initial,old
        binding=read(folder/"binding.json")
        if (binding["feature_spec_sha256"]!=spec.digest() or binding["graph"]!=j["graph"]
                or binding["split"]!=j["split"] or binding["initial_state_sha256"]!=j["initial"]["state_sha256"]):
            raise ValueError("Checkpoint binding differs")
        for key in ("graph","folds","labels","label_view","feature_view","feature_npz"):
            if binding[key]!=j[key]: raise ValueError("Input reference changed: "+key)
            checked(binding[key])
        for ck in ("best","last"):
            payload=load_checked(dict(path=str(folder/(ck+".pt")),sha256=report["checkpoint_sha256"][ck]))
            if payload["binding"]!=binding or payload["epoch"]!=0: raise ValueError("Saved checkpoint identity differs")
            del payload
        if device=="gpu":
            gate=read(root/("gpu_"+j["name"]+".json"))
            if gate.get("passed") is not True or gate["resources"]["minimum_free_mib"]<100:
                raise ValueError("GPU probe resource gate failed")
        checks.append(dict(name=j["name"],passed=True,acceptance=seal["acceptance"],
            carrier_dim=spec.carrier_dim(),parameters=j["parameters"],
            train_loss=report["history"][0]["train_loss"],inner_val_loss=report["history"][0]["inner_val_loss"],
            constructor_seconds=report["constructor_seconds"],constructor_over_3x_h8=report["constructor_over_3x_h8"],
            fit_seconds=report["fit_seconds"],tensor_memory=j["tensor_memory"]))
    return dict(passed=True,device=device,plan=plan_ref,checks=checks,formal_fits=0)


def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--device",choices=("cpu","gpu"),default="cpu")
    a=p.parse_args();result=verify(a.out,a.device)
    dest=Path(a.out)/(a.device+"_independent_verification.json")
    write(dest,result);write(dest.with_suffix(".seal.json"),dict(verification=ref(dest)))
    print(json.dumps(dict(passed=True,device=a.device,count=len(result["checks"]))))

if __name__=="__main__":main()
