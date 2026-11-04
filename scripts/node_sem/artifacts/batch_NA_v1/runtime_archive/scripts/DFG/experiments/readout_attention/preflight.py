"""Four real-data, zero-step interface/gradient/memory checks before formal fits."""
import gc,time,traceback
from pathlib import Path
import torch
from .common import *
from .model import make_model,move_to_device,attention_pool
from .runtime import Supervision,gradient_audit
from .checks import check_initial
from scripts.DFG.experiments.guard_extension.model import make_model as mean_model
from scripts.DFG.experiments.e23_pilot.training import CardMonitor

def observe(model,files):
    captured={}
    def hook(module,args,out):
        captured.update({k:v.detach().cpu().clone() for k,v in out.items()})
    handle=model.gcs[-1].register_forward_hook(hook)
    try:
        model.eval()
        with torch.no_grad():z,p=model(files)
    finally:handle.remove()
    return captured,z.detach().cpu(),p.detach().cpu()

def _run(output=DEFAULT):
    output=Path(output);plan=verify_plan(output)
    if (output/"preflight.json").exists() or (output/"preflight_failure.json").exists():raise FileExistsError("Preflight already attempted; preserve prior evidence")
    if not torch.cuda.is_available():raise RuntimeError("CUDA unavailable; no CPU fallback")
    torch.set_num_threads(plan["threads"]);reports=[];current=None
    try:
        with CardMonitor() as monitor:
            for tid in TASKS:
                info=read_json(task_ref(plan,tid,0)["manifest"]);cfg=info["config"];files=sorted(info["split"]["val_files"])
                for variant in VARIANTS:
                    current=dict(task_id=tid,fold=0,variant=variant);torch.cuda.reset_peak_memory_stats();tick=time.monotonic()
                    source=info["mean_sources"][variant];saved=torch.load(source["initial_path"],map_location="cpu")
                    if sha256(source["initial_path"])!=source["initial_sha256"] or tensor_digest(saved["state_dict"])!=source["initial_state_sha256"]:raise ValueError("Source mean initial drift")
                    baseline=mean_model("contract",info["graphs"][variant]["path"],"cpu",cfg["hidden_size"],cfg["layers"],cfg["heads"])
                    baseline.load_state_dict(saved["state_dict"],strict=True);baseline=move_to_device(baseline,plan["device"])
                    bh,bz,bp=observe(baseline,files);base_parameters=sum(p.numel() for p in baseline.parameters())
                    del baseline,saved;gc.collect();torch.cuda.empty_cache()
                    record=torch.load(info["initialization"][variant]["path"],map_location="cpu");check_initial(record,info,variant)
                    model=make_model("contract",info["graphs"][variant]["path"],"cpu",cfg["hidden_size"],cfg["layers"],cfg["heads"],graph_kind=variant)
                    model.load_state_dict(record["state_dict"]);model=move_to_device(model,plan["device"])
                    ah,az,ap=observe(model,files)
                    if set(ah)!=set(bh) or any(not torch.equal(ah[k],bh[k]) for k in ah):raise ValueError("Initial HGT outputs changed")
                    if not torch.allclose(ap,bp,atol=1e-5,rtol=1e-5):raise ValueError("Zero readout differs from mean")
                    # Baseline and new pooling use different finite-precision reductions.
                    if not torch.allclose(az,bz,atol=1e-4,rtol=1e-5):raise ValueError("Initial classifier alignment failed")
                    if not torch.equal(az.argmax(1),bz.argmax(1)):raise ValueError("Initial class alignment failed")
                    h=torch.zeros((model.total_nodes,model.hidden_size))
                    for typ,ids in model.node_ids_dict.items():h[ids]=ah[typ]
                    for f in files:
                        nodes=h[model.node_ids_by_filename[f]];_,alpha=attention_pool(nodes,model.readout_vector.detach().cpu())
                        if not torch.equal(alpha,torch.full_like(alpha,1/len(alpha))):raise ValueError("Attention initial not uniform")
                    params=sum(p.numel() for p in model.parameters())
                    if params-base_parameters!=128:raise ValueError("More than the approved 128 parameters added")
                    parts=Supervision(model,"contract",info["split"]["train_files"])
                    labels={x["contract_name"]:int(x["targets"]) for x in read_json(info["labels_path"])}
                    before=tensor_digest(model.state_dict());seed_all(info["fit_seed"]);model.train();model.zero_grad()
                    loss=torch.nn.CrossEntropyLoss()(parts.forward(model),parts.targets(model,labels))
                    if not torch.isfinite(loss):raise ValueError("Nonfinite initial training loss")
                    loss.backward();audit=gradient_audit(model,info["support"][variant]);torch.cuda.synchronize()
                    if tensor_digest(model.state_dict())!=before:raise ValueError("Zero-step preflight altered model state")
                    reports.append(dict(current,status="passed",hgt_exact=True,uniform_attention=True,
                        maximum_pool_error=float((ap-bp).abs().max()),maximum_logit_error=float((az-bz).abs().max()),
                        maximum_probability_error=float((az.softmax(1)-bz.softmax(1)).abs().max()),initial_classes_equal=True,
                        added_parameters=params-base_parameters,gradient=audit,initial_weights_unchanged=True,optimizer_steps=0,
                        peak_allocated_mib=torch.cuda.max_memory_allocated()/1024**2,peak_reserved_mib=torch.cuda.max_memory_reserved()/1024**2,seconds=time.monotonic()-tick))
                    print("PREFLIGHT_PASSED",tid,variant,"attention_grad",audit["readout"]["gradient_l1"],flush=True)
                    del model,record,h,ah,bh,az,bz,ap,bp,loss,parts;gc.collect();torch.cuda.empty_cache()
            resource=monitor.report()
        result=dict(status="passed",plan_sha256=digest(plan),cases=reports,trained_fits=0,optimizer_steps=0,
            card=monitor.report(),scope="four fold0 single backward checks, not efficacy results")
        write_json(output/"preflight.json",result);return dict(status="passed",cases=len(reports))
    except BaseException as exc:
        write_json(output/"preflight_failure.json",dict(status="failed",job=current,error=repr(exc),traceback=traceback.format_exc(),automatic_retry=False));raise


def run(output=DEFAULT):
    # Same cross-batch GPU lease as the formal controller; never overlap a fit.
    import fcntl
    output=Path(output)
    if not output.is_dir():raise ValueError("Prepare batch before preflight")
    lockpath=ROOT/"scripts/DFG/experiments/overall_cv/.execution.lock"
    with lockpath.open("a") as global_lock,(output/".execution.lock").open("a") as lock:
        fcntl.flock(global_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return _run(output)
