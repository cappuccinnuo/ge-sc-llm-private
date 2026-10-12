"""Verify saved weights changed where gradients should flow (CPU only)."""
import torch
from common import *

def main():
    root=HERE/"artifacts/v1";rows=[]
    torch.set_num_threads(1)
    for p in sorted((root/"runs").glob("*/*/seed_*/result.json")):
        r=read_json(p)
        if not r["complete"]:continue
        cfg=r["config"];cut=cfg["settings"]["gradient"]=="detached"
        for f in r["folds"]:
            initial=torch.load(f["initialization"]["reference"],map_location="cpu")
            current=torch.load(str(p.parent/("fold_"+str(f["fold"]))/"best.pt"),map_location="cpu")
            changed_head=[];changed_backbone=[];unchanged=[];excluded=[]
            for name,value in current.items():
                if cfg["experiment"]=="C_local_relations" and any(name.endswith(x) for x in ["relation_pri","relation_att","relation_msg"]):
                    excluded.append(name);continue
                if value.shape!=initial[name].shape:raise AssertionError("Unexpected shape")
                if torch.equal(value,initial[name]):unchanged.append(name)
                elif name.startswith("classify."):changed_head.append(name)
                else:changed_backbone.append(name)
            if not changed_head:raise AssertionError("Classifier did not update")
            if cut and changed_backbone:raise AssertionError("Detached backbone changed")
            if not cut and not changed_backbone:raise AssertionError("Connected backbone failed to update")
            rows.append({"task":cfg["task"],"experiment":cfg["experiment"],"seed":cfg["seed"],"fold":f["fold"],
                         "detached":cut,"changed_classifier_tensors":len(changed_head),
                         "changed_backbone_tensors":len(changed_backbone),"unchanged_tensors":len(unchanged),
                         "excluded_relation_tensors":excluded})
    write_json(root/"weight_update_audit.json",{"created_utc":utc(),"folds_verified":len(rows),"passed":True,"folds":rows})
    print("Saved weight update checks passed for",len(rows),"folds")
if __name__=="__main__":main()
