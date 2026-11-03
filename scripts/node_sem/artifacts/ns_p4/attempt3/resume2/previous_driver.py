"""NS-P4b nonformal acceptance: reuse frozen fit, preserve all NS-P4 artifacts."""
import argparse
import copy
import csv
import gc
import json
import os
from pathlib import Path
import time
import traceback
import numpy as np
import torch
from . import p4_acceptance as p4
from .p4_verify import verify_report
from .feature_spec import FeatureSpec
from .init import checked_initial
from .checkpoint_io import load_checked
from .execution import runtime_refs, GPU_LOCK
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.experiment.run import _Lock, _move_model
from scripts.DFG.dfg_v2.experiment.preflight import LOCAL_DEV_POLICY, run_preflight, initialize_context, make_observed_resources
from scripts.DFG.experiments.common import seed_all

ROOT=p4.ROOT
ATTEMPT=p4.OUT/"attempt3"
OUT=ATTEMPT
OLD=p4.OUT/"attempt2"
VERSION="nodesem-p4b-acceptance-v1"
CPU_NAMES=("S3","S3m","S4","S4g","S4m","S4-noG")
NODE_GPU=("S1o","S2","S4","S4g","S4m","S4-noG")
HISTORY=ROOT/"scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/reports/resources.csv"


def matrix():
    return ([('cpu','reentrancy_node',n) for n in CPU_NAMES]
        +[('gpu','reentrancy_node',n) for n in NODE_GPU]
        +[('gpu','reentrancy_contract',n) for n in ('S1o','S4')])


def identity(job):
    return '_'.join((job['actual_device'],job['task_id'],job['name']))


def drivers():
    return [ref(Path(__file__)),ref(Path(p4.__file__)),ref(Path(__file__).with_name('p4_verify.py'))]


def history_row(path,job):
    with Path(path).open(newline='') as stream:
        rows=[r for r in csv.DictReader(stream) if (r['task_id'],int(r['fold']),int(r['seed']),r['profile'])
              ==(job['task_id'],job['fold'],job['seed'],job['profile'])]
    if len(rows)!=1: raise ValueError('Historical resource identity missing/duplicated')
    r=rows[0]
    for key in ('peak_allocated_mib','peak_reserved_mib','minimum_free_mib'):
        r[key]=float(r[key])
        if not np.isfinite(r[key]) or r[key]<0: raise ValueError('Invalid historical memory')
    if r['peak_reserved_mib']<=0: raise ValueError('Invalid historical reserved memory')
    return r


def compare_resources(summary,historical):
    values={k:float(summary[k]) for k in ('peak_allocated_mib','peak_reserved_mib','minimum_free_mib')}
    if not all(np.isfinite(v) and v>=0 for v in values.values()): raise ValueError('Invalid observed memory')
    ratio=values['peak_reserved_mib']/historical['peak_reserved_mib']
    return dict(current=values,historical=historical,reserved_ratio=ratio,
        significant_memory_increase=ratio>1.25,advisory_only=True,
        delta_mib={k:v-historical[k] for k,v in values.items()},
        caveat='Historical 8H baseline: different execution time, epochs and feature view; no controlled causal attribution. G0 S4-noG also removes HGT layers.')


def logits_comparison(cpu,gpu):
    a=cpu.detach().cpu().double();b=gpu.detach().cpu().double()
    if a.shape!=b.shape or a.numel()==0 or not bool(torch.isfinite(a).all() and torch.isfinite(b).all()):
        raise ValueError('Nonfinite/mismatched parity logits')
    difference=(a-b).abs();scale=max(float(a.abs().max()),float(b.abs().max()))
    absolute=float(difference.max());relative=absolute/scale if scale else 0.
    denominator=torch.maximum(a.abs(),b.abs());nonzero=denominator>0
    elementwise=float((difference[nonzero]/denominator[nonzero]).max()) if bool(nonzero.any()) else 0.
    return dict(passed=absolute<=1e-4 and relative<=1e-4,max_absolute=absolute,
        tensor_scale=scale,tensor_relative=relative,max_elementwise_relative=elementwise,
        shape=list(a.shape),absolute_limit=1e-4,relative_limit=1e-4,
        relative_definition='max_abs_difference / max(max_abs_cpu, max_abs_gpu); all-zero pair = 0')


def gate_checks(model):
    rows=[]
    for adapter in model.adapt_ws:
        gate=adapter.last_gates
        if gate is None: continue
        if gate.device.type!='cpu' or gate.requires_grad or not bool(torch.isfinite(gate).all()):
            raise ValueError('last_gates must be detached finite CPU tensors')
        sums=gate.sum(1);active=sums!=0
        error=float((sums[active]-1).abs().max()) if bool(active.any()) else 0.
        if error>1e-6: raise ValueError('Gate rows do not sum to one')
        rows.append(dict(node_type=adapter.ntype,rows=len(sums),active_rows=int(active.sum()),max_sum_error=error,device='cpu'))
    return rows


def unchanged_history():
    before=read(ATTEMPT/'before.json')
    # Snapshot paths are repo-relative, not a new mutable historical seal.
    entries=before['previous_attempt_files']
    for expected in entries:
        name=expected['path']
        path=ROOT/name
        if ref(path)['sha256']!=expected['sha256'] or path.stat().st_size!=expected['bytes']:
            raise ValueError('Historical NS-P4 artifact changed: '+name)
    return len(entries)


def prepare():
    old_ref=read(OLD/'plan.seal.json')['plan'];old=read(checked(old_ref))
    p4.h8.load(checked(old['source_h8_plan']))
    prepared=OUT/'prepared';prepared.mkdir(exist_ok=False)
    jobs=[]
    for device,task_id,name in matrix():
        found=[j for j in old['jobs'] if j['task_id']==task_id and j['name']==name]
        if found:
            if len(found)!=1: raise ValueError('Ambiguous historical P4 job')
            job=copy.deepcopy(found[0]);job['actual_device']=device
            job['initial_provenance']='reused sealed NS-P4 zero-step initial; never trained weights'
        else:
            if (task_id,name)!=('reentrancy_node','S1o'): raise ValueError('Unexpected new preparation')
            source=p4.h8.load(checked(old['source_h8_plan']))
            _,(task,info,entry)=p4._entry(source,task_id,'G3R')
            spec_ref=ref(OLD/'prepared/specs'/task_id/(name+'.json'))
            spec=FeatureSpec.from_json(read(checked(spec_ref)))
            directory=prepared/device/task_id/name;directory.mkdir(parents=True,exist_ok=False)
            seed_all(info['seeds']['constructor']);start=time.monotonic()
            model=p4.make_nodesem_model(task['granularity'],entry['graph'],'G3R',spec,task['config'],'cpu',task_id)
            seconds=time.monotonic()-start
            initial=p4.save_initial(model,spec,task_id,'G3R',info,entry,directory/'initial.pt')
            carrier=p4.write_carrier(spec,task_id,p4.read_graph(checked(entry['graph'])),directory/'carrier')
            # Copy only the same task/profile metadata, then bind the new S1 carrier and parameters.
            job=copy.deepcopy(next(j for j in old['jobs'] if j['task_id']==task_id and j['name']=='S2'))
            job.update(name=name,actual_device=device,spec=spec_ref,spec_sha256=spec.digest(),initial=initial,
                feature_view=carrier['manifest'],feature_npz=carrier['data'],support=p4.model_support(model,info['split']),
                constructor_seconds=seconds,carrier_dim=spec.carrier_dim(),parameters=sum(p.numel() for p in model.parameters()),
                initial_provenance='new sealed zero-step S1o from the same historical fit identity')
            params=sum(p.numel()*p.element_size() for p in model.parameters())
            inp=sum(model.symmetrical_global_graph.nodes[n].data['inp'].numel()*4 for n in model.symmetrical_global_graph.ntypes)
            edges=sum(sum(t.numel()*t.element_size() for t in model.symmetrical_global_graph.edges(etype=e)) for e in model.symmetrical_global_graph.canonical_etypes)
            job['tensor_memory']=dict(parameter_bytes=params,gradient_bytes=params,adam_moments_bytes=2*params,input_bytes=inp,
                edge_endpoint_bytes=edges,estimated_subtotal_mib=(4*params+inp+edges)/1024**2,excludes='activation/cache/context/peak lifetime')
            del model;gc.collect()
        for key in ('spec','graph','labels','folds','label_view','feature_view','feature_npz'): checked(job[key])
        spec=FeatureSpec.from_json(read(checked(job['spec'])))
        checked_initial(job['initial'],task_id,0,job['profile'],spec_digest=spec.digest())
        job['historical_resources']=history_row(HISTORY,job)
        jobs.append(job)
    plan=dict(version=VERSION,jobs=jobs,source_p4_plan=old_ref,source_h8_plan=old['source_h8_plan'],
        source_preparation=old['source_preparation'],h8_constructor_seconds=old['h8_constructor_seconds'],
        historical_resources=ref(HISTORY),runtime=runtime_refs(),drivers=drivers(),decisions=ref(OUT/'decisions.json'),
        resource_policy=LOCAL_DEV_POLICY,cpu_fits=6,gpu_probes=8,formal_training_authorized=False,
        maximum_training_epochs=1,only_training_config_override='maximum_training_epochs',
        dropout_version='fit-task-fold-profile-spec-ntype-v2',prompt=ref(p4.BASE/'PROMPTS.md'))
    validate_matrix(plan)
    write(OUT/'plan.json',plan);write(OUT/'plan.seal.json',dict(plan=ref(OUT/'plan.json')))
    return plan



def prepare_resume():
    """Preserve failed pre-fit attempt; reuse its zero-step references verbatim."""
    approval=read(OUT/'resume_authorization.json')
    if approval.get('user_approved') is not True: raise ValueError('Explicit recovery authorization missing')
    original_ref=read(ATTEMPT/'plan.seal.json')['plan']
    old=read(checked(original_ref))
    failure_ref=ref(ATTEMPT/'cpu_reentrancy_node_S3.failure.json')
    failure=read(checked(failure_ref))
    if 'FileExistsError' not in failure['error'] or (ATTEMPT/'runs/cpu/reentrancy_node/S3').exists():
        raise ValueError('Expected pre-fit recording failure not confirmed')
    if old['runtime']!=runtime_refs(): raise ValueError('Training runtime changed during orchestration repair')
    plan=copy.deepcopy(old)
    plan.update(drivers=drivers(),recovery=dict(source_plan=original_ref,source_failure=failure_ref,
        authorization=ref(OUT/'resume_authorization.json'),optimizer_steps_in_failed_attempt=0,
        change='Append-only JSONL phases; no model, input, initialization or numerical change'))
    write(OUT/'plan.json',plan);write(OUT/'plan.seal.json',dict(plan=ref(OUT/'plan.json')))
    return plan

def validate_matrix(plan):
    actual=[(j['actual_device'],j['task_id'],j['name']) for j in plan['jobs']]
    if actual!=matrix() or plan.get('formal_training_authorized') is not False: raise ValueError('P4b matrix differs')
    for j in plan['jobs']:
        if j['profile']!=('G0' if j['name']=='S4-noG' else 'G3R') or j['fold']!=0 or j['seed']!=1:
            raise ValueError('P4b identity differs')
    return True


def load(execute=True):
    plan=read(checked(read(OUT/'plan.seal.json')['plan']))
    if plan['version']!=VERSION: raise ValueError('Wrong acceptance version')
    validate_matrix(plan)
    if 'recovery' in plan:
        if read(checked(plan['recovery']['authorization'])).get('user_approved') is not True:
            raise ValueError('Recovery approval absent')
        original=read(checked(plan['recovery']['source_plan']))
        checked(plan['recovery']['source_failure'])
        if plan['jobs']!=original['jobs'] or plan['runtime']!=original['runtime']:
            raise ValueError('Recovery changed jobs or numerical runtime')
    if execute and (plan['runtime']!=runtime_refs() or plan['drivers']!=drivers()): raise ValueError('Execution runtime changed')
    decisions=read(checked(plan['decisions']))
    if not decisions.get('gpu_eight_probes_authorized') or not decisions.get('tensor_relative_approved'):
        raise ValueError('Missing scoped authorization')
    checked(plan['source_p4_plan']);checked(plan['historical_resources']);checked(plan['prompt'])
    p4.h8.load(checked(plan['source_h8_plan']))
    return plan


def folder_for(job):
    return OUT/'runs'/job['actual_device']/job['task_id']/job['name']


def phase_writer(job):
    def record(value):
        with (OUT/(identity(job)+'.phases.jsonl')).open('a',encoding='utf8') as stream:
            stream.write(json.dumps(dict(phase=value,unix_seconds=time.time()))+'\n')
    return record


def device_setup(job,phase,parity_file):
    def setup(model,cfg):
        parity=job['task_id']=='reentrancy_node' and job['name'] in ('S4','S4g')
        cpu_logits=None
        if parity:
            phase('zero_step_cpu_eval');model.eval()
            with torch.no_grad(): cpu_logits=model().detach().cpu().clone()
            cpu_gates=gate_checks(model)
        phase('move_model_to_gpu');model=_move_model(model,cfg['device'])
        if parity:
            phase('zero_step_gpu_eval');model.eval()
            with torch.no_grad(): gpu_logits=model().detach().cpu()
            result=logits_comparison(cpu_logits,gpu_logits)
            result.update(initial=job['initial'],cpu_gates=cpu_gates,gpu_gates=gate_checks(model),
                          evaluation_only=True,optimizer_steps=0)
            write(parity_file,result)
            if not result['passed']: raise ValueError('CPU/GPU logits parity failed')
            del cpu_logits,gpu_logits
        # Observe coarse failure phase without altering any fit arithmetic.
        def before(module,args): phase('fit_training_forward' if module.training else 'fit_eval_or_checkpoint_reload_forward')
        def after(module,args,output):
            if module.training: phase('fit_backward_optimizer_or_checkpoint')
        model.register_forward_pre_hook(before);model.register_forward_hook(after)
        return model
    return setup


def run_job(plan,job):
    phase=phase_writer(job);folder=folder_for(job)
    if job['actual_device']=='cpu':
        return p4.run_fit(plan,job,output_root=OUT,run_directory=folder,phase=phase)
    for name in CPU_NAMES:
        completed=OUT/('cpu_reentrancy_node_'+name+'.complete.json')
        if not read(completed).get('passed'): raise ValueError('CPU gate incomplete')
    resources_dir=OUT/'resources'/job['task_id']/job['name'];resources_dir.mkdir(parents=True,exist_ok=False)
    with _Lock(GPU_LOCK):
        phase('startup_preflight')
        pre=run_preflight(job,ref(OUT/'plan.json')['sha256'],resources_dir,LOCAL_DEV_POLICY)
        phase('cuda_context')
        context=initialize_context(pre['baseline'],job['config']['device']);write(resources_dir/'context.json',context)
        resource=make_observed_resources(job['config']['device'],pre['baseline'],context,resources_dir/'samples.jsonl',
            policy=LOCAL_DEV_POLICY,history_path=folder/'history.jsonl')
        try:
            with resource:
                resource.check()
                report=p4.run_fit(plan,job,resource,output_root=OUT,run_directory=folder,phase=phase,
                    device_setup=device_setup(job,phase,resources_dir/'cpu_gpu_parity.json'))
                resource.check()
        finally:
            summary=resource.summary();write(resources_dir/'resource_summary.json',summary)
            comparison=compare_resources(summary,history_row(checked(plan['historical_resources']),job))
            write(resources_dir/'comparison.json',comparison)
            if comparison['significant_memory_increase']:
                print('ADVISORY: reserved VRAM exceeds 1.25x historical 8H',flush=True)
        report['resource_comparison']=comparison
        return report


def verify_job(plan,job):
    folder=folder_for(job);seal=read(folder/'acceptance.seal.json')
    if seal['plan']!=ref(OUT/'plan.json') or checked(seal['acceptance']).resolve()!=folder/'acceptance.json':
        raise ValueError('Acceptance plan/path differs')
    report=read(checked(seal['acceptance']));verify_report(report,job)
    spec=FeatureSpec.from_json(read(checked(job['spec'])))
    initial=checked_initial(job['initial'],job['task_id'],0,job['profile'],spec_digest=spec.digest())
    old=checked_initial(job['h8_initial'],job['task_id'],0,job['profile'])
    common={k for k in initial['state_dict'] if k.startswith(('gcs.','classify.'))}
    expected={k for k in old['state_dict'] if k.startswith(('gcs.','classify.'))}
    if spec.layers==0: expected={k for k in expected if k.startswith('classify.')}
    if common!=expected or not all(torch.equal(initial['state_dict'][k],old['state_dict'][k]) for k in common):
        raise ValueError('Initial common parameters differ')
    del initial,old
    binding=read(folder/'binding.json')
    if binding['feature_spec_sha256']!=spec.digest() or binding['initial_state_sha256']!=job['initial']['state_sha256'] or binding['split']!=job['split']:
        raise ValueError('Binding differs')
    for key in ('graph','folds','labels','label_view','feature_view','feature_npz'):
        if binding[key]!=job[key]: raise ValueError('Binding changed: '+key)
        checked(binding[key])
    for ck in ('best','last'):
        payload=load_checked(dict(path=str(folder/(ck+'.pt')),sha256=report['checkpoint_sha256'][ck]))
        if payload['binding']!=binding or payload['epoch']!=0: raise ValueError('Checkpoint differs')
        del payload
    gate_checks_from_report=report['gates']
    if any(r['max_sum_error']>1e-6 for r in gate_checks_from_report): raise ValueError('Gate acceptance invalid')
    if job['actual_device']=='gpu':
        rdir=OUT/'resources'/job['task_id']/job['name']
        summary=read(rdir/'resource_summary.json')
        expected=compare_resources(summary,history_row(checked(plan['historical_resources']),job))
        if read(rdir/'comparison.json')!=expected: raise ValueError('Resource comparison differs')
        if job['task_id']=='reentrancy_node' and job['name'] in ('S4','S4g'):
            parity=read(rdir/'cpu_gpu_parity.json')
            if not parity['passed'] or parity['initial']!=job['initial'] or parity['max_absolute']>1e-4 or parity['tensor_relative']>1e-4:
                raise ValueError('Missing/failed parity')
    return dict(identity=identity(job),passed=True,acceptance=seal['acceptance'],parameters=job['parameters'])


def verify():
    plan=load(execute=False);checks=[];oom=[]
    for job in plan['jobs']:
        failure=OUT/(identity(job)+'.failure.json')
        if failure.exists():
            record=read(failure)
            if job['actual_device']=='gpu' and job['task_id']=='reentrancy_contract' and record.get('cuda_oom'):
                oom.append(dict(identity=identity(job),failure=ref(failure),requires_server=True));continue
            raise ValueError('Unaccepted failed job: '+identity(job))
        completed=read(OUT/(identity(job)+'.complete.json'))
        if completed.get('passed') is not True: raise ValueError('Completion missing')
        # Bind every run file, including scoring exports and resource evidence.
        for item in read(checked(completed['receipt']))['artifacts']: checked(item)
        checks.append(verify_job(plan,job))
    result=dict(passed=True,checks=checks,contract_oom=oom,formal_fits=0,
        node_gpu_passed=sum(c['identity'].startswith('gpu_reentrancy_node_') for c in checks),
        unchanged_attempt2_files=unchanged_history(),plan=ref(OUT/'plan.json'))
    write(OUT/'independent_verification.json',result)
    write(OUT/'independent_verification.seal.json',dict(verification=ref(OUT/'independent_verification.json')))
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','resume-prepare','run','verify'))
    parser.add_argument('--only');parser.add_argument('--out');a=parser.parse_args();torch.set_num_threads(2)
    global OUT
    if a.out:
        OUT=Path(a.out).resolve()
        if OUT!=ATTEMPT.resolve() and ATTEMPT.resolve() not in OUT.parents:
            raise ValueError('Output must remain under attempt3')
    if a.stage=='verify': print(json.dumps(verify()));return
    plan=None;job=None
    if a.stage=='run':
        plan=load();jobs=[j for j in plan['jobs'] if identity(j)==a.only]
        if len(jobs)!=1: raise ValueError('Unknown P4b job')
        job=jobs[0]
    name='prepare' if job is None else identity(job)
    marker=OUT/(name+'.started.json')
    with marker.open('x',encoding='utf8') as stream:
        json.dump(dict(pid=os.getpid(),unix_seconds=time.time(),drivers=drivers(),runtime=runtime_refs()),stream,indent=2)
    try:
        result=(prepare_resume() if a.stage=='resume-prepare' else prepare()) if job is None else run_job(plan,job)
        if job is not None:
            verify_job(plan,job)
            artifacts=[ref(p) for p in sorted(folder_for(job).rglob('*')) if p.is_file()]
            rdir=OUT/'resources'/job['task_id']/job['name']
            if job['actual_device']=='gpu': artifacts += [ref(p) for p in sorted(rdir.rglob('*')) if p.is_file()]
            receipt=OUT/(name+'.receipt.json');write(receipt,dict(job=job,plan=ref(OUT/'plan.json'),artifacts=artifacts))
            write(OUT/(name+'.complete.json'),dict(passed=True,finished=time.time(),receipt=ref(receipt)))
        else: write(OUT/'prepare.complete.json',dict(passed=True,finished=time.time()))
    except Exception as error:
        oom=isinstance(error,RuntimeError) and 'cuda out of memory' in str(error).lower()
        memory={}
        if torch.cuda.is_initialized():
            memory=dict(allocated_mib=torch.cuda.memory_allocated()/1024**2,reserved_mib=torch.cuda.memory_reserved()/1024**2,
                peak_allocated_mib=torch.cuda.max_memory_allocated()/1024**2,peak_reserved_mib=torch.cuda.max_memory_reserved()/1024**2)
        phase=OUT/(name+'.phases.jsonl')
        write(OUT/(name+'.failure.json'),dict(error=repr(error),traceback=traceback.format_exc(),cuda_oom=oom,
            phase=json.loads(phase.read_text().splitlines()[-1]) if phase.exists() else None,memory=memory,automatic_retry=False))
        raise


if __name__=='__main__': main()
