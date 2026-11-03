"""Optional, separately authorized zero-step TF32 diagnostic. Never trains."""
import json
from pathlib import Path
import torch
from . import p4b_acceptance as run
from . import p4_acceptance as p4
from .feature_spec import FeatureSpec
from .init import checked_initial
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from scripts.DFG.dfg_v2.experiment.run import _Lock,_move_model
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY,run_preflight,initialize_context
from scripts.DFG.experiments.common import seed_all,tensor_digest

ROOT=run.ROOT
OUT=run.ATTEMPT/'parity_diagnostic1'


def capture(model):
    values={};handles=[]
    def keep(name):
        def hook(module,args,output):
            if isinstance(output,dict):
                for key,value in output.items():values[name+'/'+key]=value.detach().cpu().clone()
            else:values[name]=output.detach().cpu().clone()
        return hook
    for n,a in zip(sorted(model.ntypes_dict,key=model.ntypes_dict.get),model.adapt_ws):
        handles.append(a.register_forward_hook(keep('adapter/'+n)))
    for i,a in enumerate(model.gcs):handles.append(a.register_forward_hook(keep('hgt/'+str(i))))
    try:
        model.eval()
        with torch.no_grad():values['logits']=model().detach().cpu().clone()
    finally:
        for h in handles:h.remove()
    return values


def compare(a,b):
    if set(a)!=set(b):raise ValueError('Diagnostic layer identities differ')
    return {name:run.logits_comparison(a[name],b[name]) for name in a if a[name].numel()}


def main():
    torch.set_num_threads(2)
    authorization=read(OUT/'authorization.json')
    if authorization.get('user_approved') is not True:raise ValueError('Additional diagnostic authorization required')
    with (OUT/'started.json').open('x') as stream:json.dump(dict(driver=ref(Path(__file__))),stream)
    run.OUT=run.ATTEMPT/'resume1';plan=run.load()
    job=next(j for j in plan['jobs'] if run.identity(j)=='gpu_reentrancy_node_S4')
    spec=FeatureSpec.from_json(read(checked(job['spec'])))
    with _Lock(run.GPU_LOCK):
        pre=run_preflight(job,ref(run.OUT/'plan.json')['sha256'],OUT,LOCAL_DEV_POLICY)
        context=initialize_context(pre['baseline'],job['config']['device']);write(OUT/'context.json',context)
        seed_all(job['seeds']['constructor'])
        model=p4.make_nodesem_model(job['granularity'],job['graph'],job['profile'],spec,job['config'],'cpu',job['task_id'])
        initial=checked_initial(job['initial'],job['task_id'],0,job['profile'],spec_digest=spec.digest())
        model.load_state_dict(initial['state_dict'],strict=True);del initial
        before=tensor_digest(model.state_dict())
        cpu=capture(model);model=_move_model(model,job['config']['device'])
        default=dict(matmul=torch.backends.cuda.matmul.allow_tf32,cudnn=torch.backends.cudnn.allow_tf32)
        try:
            gpu_default=capture(model)
            gpu_repeat=capture(model)
            torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
            gpu_fp32=capture(model)
        finally:
            torch.backends.cuda.matmul.allow_tf32=default['matmul'];torch.backends.cudnn.allow_tf32=default['cudnn']
        assert tensor_digest(model.state_dict())==before==job['initial']['state_sha256']
        assert all(p.grad is None for p in model.parameters())
        report=dict(optimizer_steps=0,training=False,scope='One CPU and three GPU eval forwards only; no acceptance/retry policy changed',
            default_tf32=default,restored_tf32=dict(matmul=torch.backends.cuda.matmul.allow_tf32,cudnn=torch.backends.cudnn.allow_tf32),
            initial=job['initial'],plan=ref(run.OUT/'plan.json'),authorization=ref(OUT/'authorization.json'),
            cpu_vs_default=compare(cpu,gpu_default),default_repeat=compare(gpu_default,gpu_repeat),
            cpu_vs_tf32_disabled=compare(cpu,gpu_fp32),parameters_unchanged=True,
            peak_allocated_mib=torch.cuda.max_memory_allocated()/1024**2,peak_reserved_mib=torch.cuda.max_memory_reserved()/1024**2)
        write(OUT/'report.json',report);write(OUT/'report.seal.json',dict(report=ref(OUT/'report.json')))
        print(json.dumps({k:report[k]['logits'] for k in ('cpu_vs_default','default_repeat','cpu_vs_tf32_disabled')}))

if __name__=='__main__':main()
