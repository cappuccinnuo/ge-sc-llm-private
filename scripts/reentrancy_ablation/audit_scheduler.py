"""Record actual OneCycle LR and Adam beta1 traces used in the ablations."""
import torch
from common import *
def main():
    out={}
    for task in ["node","contract"]:
        for schedule in ["current","legacy"]:
            parameter=torch.nn.Parameter(torch.zeros(1))
            optimizer=torch.optim.Adam([parameter],lr=.0002 if task=="node" else .0005)
            kwargs={}
            if schedule=="current":kwargs=dict(div_factor=25 if task=="node" else 20,final_div_factor=1)
            scheduler=torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=.005 if task=="node" else .01,total_steps=50,**kwargs)
            rows=[]
            for epoch in range(50):
                g=optimizer.param_groups[0]
                rows.append({"epoch":epoch,"lr":g["lr"],"beta1":g["betas"][0],"beta2":g["betas"][1]})
                optimizer.zero_grad();parameter.sum().backward();optimizer.step()
                if schedule=="current" or task=="node":scheduler.step()
            out[task+"_"+schedule]=rows
    write_json(HERE/"artifacts/v1/scheduler_trace.json",{
        "created_utc":utc(),"traces":out,
        "note":"Default OneCycle cycle_momentum=True also varies Adam beta1. Contract legacy freezes both LR and beta1 because scheduler.step is disabled. This is a scheduler-behavior ablation, not LR-only."})
    print({k:{"first":v[0],"last":v[-1]} for k,v in out.items()})
if __name__=="__main__":main()
