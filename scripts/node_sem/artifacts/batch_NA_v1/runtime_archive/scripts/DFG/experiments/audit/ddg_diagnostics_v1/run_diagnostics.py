"""Replay sealed checkpoints serially. No optimizer, no training, no source edits."""
import argparse
import gc
import json
import math
import re
import sys
import time
from pathlib import Path
from collections import defaultdict
import numpy as np
import torch
from .diagnostic_common import (ROOT, REPO, RUN, PROTOCOL, SCORE_ROLE, TOLERANCES,
    PILOTS, REWIRING_SEEDS, read_json, write_json, write_csv, file_sha,
    compare_outputs, align_records, summary)
from .interventions import DiagnosticContext
from .rewiring import rewire_ddg
from .validate_runner_inputs import validate_preflight
from scripts.DFG.experiments.runtime import make_model
from scripts.DFG.experiments.paper_runtime import Supervision
from scripts.DFG.experiments.paper_checkpoint import restore_checkpoint
from scripts.DFG.experiments.common import tensor_digest, metrics, seed_all
from scripts.DFG.model_validation import assert_model_input, capture_model_input
from scripts.labeling_v2.safe_graph import read_graph

def reset_device_statistics(device):
    # torch 1.8 resetPeakMemoryStats does not itself initialize the CUDA runtime.
    # Explicit init changes no graph/model/optimizer and must precede the query.
    torch.cuda.init()
    torch.cuda.reset_peak_memory_stats(device)


def stage_name(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*",value):
        raise ValueError("Stage output must be a simple directory name")
    return value


def parameter_scales(model):
    rows=[]
    for i,layer in enumerate(model.gcs):
        for name in ['relation_att','relation_msg']:
            bank=getattr(layer,name).detach().cpu()
            fan_in,fan_out=torch.nn.init._calculate_fan_in_and_fan_out(bank)
            theoretical_std=math.sqrt(2.0/(fan_in+fan_out))
            matrix_std=math.sqrt(2.0/(bank.shape[-1]+bank.shape[-2]))
            for c,index in model.etypes_dict.items():
                v=bank[index]
                source_shape=list(bank.shape)
                copied_common=c[1]!='DATA_DEF_USE'
                if copied_common: source_shape[0]=sum(x[1]!='DATA_DEF_USE' for x in model.etypes_dict)
                source_fan_in=source_shape[1]*source_shape[2]*source_shape[3]
                source_fan_out=source_shape[0]*source_shape[2]*source_shape[3]
                source_std=math.sqrt(2.0/(source_fan_in+source_fan_out))
                rows.append(dict(layer=i,parameter=name,canonical=list(c),
                    shape=list(bank.shape),initialization_source=('fresh_E0_bank' if copied_common else 'new_E1_bank'),
                    initialization_source_shape=source_shape,initialization_source_theoretical_std=source_std,
                    source_to_matrix_std_ratio=source_std/matrix_std,std_population=float(v.std(unbiased=False)),
                    frobenius_norm=float(v.norm()),bank_fan_in=fan_in,bank_fan_out=fan_out,
                    theoretical_full_bank_xavier_std=theoretical_std,
                    theoretical_per_matrix_xavier_std=matrix_std,
                    bank_to_matrix_std_ratio=theoretical_std/matrix_std))
    return rows

def base_records(model, part, original, task, labels):
    records=[]
    if task=='node':
        for idx in part.full_ids:
            d=model.nx_graph.nodes[idx]
            records.append(dict(file=d['source_file'],original_graph_node_id=original[idx],
                                node_type=d['node_type'],target=int(model.node_labels[idx])))
    else:
        records=[dict(file=f,target=int(labels[f])) for f in part.files]
    return records

def archived_gate(archived, records, task, ck, logits, probabilities, expected_metrics):
    archived=align_records(archived,records,task)
    prediction=logits.argmax(1).cpu().tolist()
    if prediction!=[r[ck] for r in archived]:
        raise AssertionError('Native replay disagrees with archived discrete predictions')
    old=np.asarray([r[ck+'_positive_probability'] for r in archived])
    new=np.asarray(probabilities)
    if not np.allclose(new,old,rtol=TOLERANCES['archive_probability_rtol'],
                       atol=TOLERANCES['archive_probability_atol']):
        raise AssertionError('Native replay exceeds predeclared probability tolerance: '+str(np.abs(new-old).max()))
    current=metrics([r['target'] for r in records],prediction)
    for key in ['buggy_f1','macro_f1','precision','recall']:
        if abs(current[key]-expected_metrics[key])>TOLERANCES['archived_metric_atol']:
            raise AssertionError('Native metric replay mismatch: '+key)
    if current['tn_fp_fn_tp']!=expected_metrics['tn_fp_fn_tp']:
        raise AssertionError('Native confusion matrix mismatch')
    return dict(predictions_exact=True,metrics_match=True,
                probability_abs_max=float(np.abs(new-old).max()),
                probability_exact=bool(np.array_equal(new,old)))

def add_tags(rows,tags):
    return [dict(tags,**r) for r in rows]

def representations_difference(reference,changed,files_by_type,tags):
    rows=[]
    if set(reference)!=set(changed): raise AssertionError('Representation keys differ')
    for key,a in reference.items():
        b=changed[key]
        if a.shape!=b.shape: raise AssertionError('Representation shape mismatch')
        vals=(a-b).norm(dim=1).numpy()
        layer,typ,stage=key
        files=files_by_type[typ]
        for f in ['__all__']+sorted(set(files)):
            selected=vals if f=='__all__' else vals[np.asarray([x==f for x in files])]
            rows.append(dict(tags,layer=layer,node_type=typ,file=f,stage=stage,**summary(selected)))
    return rows

def replay_variant(job,variant,out,device,pilot,e0_reference=None):
    state=read_json(RUN/'state.json')['jobs'][job['id']]
    if state['status']!='passed': raise ValueError('Unaccepted job')
    attempt=RUN/state['attempt'];fold_dir=attempt/('fold_'+str(job['fold']))
    dest=fold_dir/variant;config=read_json(attempt/'effective_config.json')
    binding=read_json(dest/'binding.json');expected=read_json(dest/'model_input.json')
    results=read_json(dest/'result.json')
    prepared=Path(job['prepared']);manifest=read_json(prepared/'manifest.json')
    spec=manifest['graphs'][variant][job['task']]
    graph_path=prepared/spec['path']
    if file_sha(graph_path)!=spec['sha256'] or file_sha(graph_path)!=binding['graph_sha256']:
        raise ValueError('Frozen graph digest mismatch')
    if file_sha(prepared/'manifest.json')!=binding['prepared_manifest_sha256']:
        raise ValueError('Prepared manifest mismatch')
    split_doc=read_json(job['splits'])
    split=next(s for s in split_doc['folds'] if s['fold']==job['fold'])
    if split!=binding['split'] or file_sha(job['splits'])!=binding['split_manifest_sha256']:
        raise ValueError('Split binding mismatch')
    if file_sha(prepared/'graph_labels.json')!=binding['graph_labels_sha256']:
        raise ValueError('Graph labels changed')
    labels={r['contract_name']:r['targets'] for r in read_json(prepared/'graph_labels.json')}
    raw=read_graph(graph_path);original=list(raw)
    # Explicit source metadata establishes the production reindex mapping.
    identities=[(n,raw.nodes[n]['source_file'],raw.nodes[n]['node_type'],raw.nodes[n].get('code')) for n in original]
    del raw
    started=time.perf_counter()
    if torch.cuda.is_available():
        reset_device_statistics(device)
    seed_all(1)
    model=make_model(job['task'],graph_path,device,hidden_size=config['hidden_size'],
                     layers=config['layers'],heads=config['heads'])
    model.eval()
    part=Supervision(model,job['task'],split['val_files'])
    if part.manifest!=read_json(dest/'val_supervision.json'):
        raise ValueError('Validation supervision binding mismatch')
    for idx,(oid,file,typ,code) in enumerate(identities):
        d=model.nx_graph.nodes[idx]
        if (d['source_file'],d['node_type'],d.get('code'))!=(file,typ,code):
            raise ValueError('Production node reindex mapping mismatch')
    records=base_records(model,part,original,job['task'],labels)
    files=[r['file'] for r in records];truth=[r['target'] for r in records]
    function_doc=read_json(ROOT/'static/edge_functions.json')['tasks'][job['cohort']+'_'+job['task']]
    function_lookup={(type(r['node_id']).__name__,r['node_id']):r['function'] for r in function_doc['nodes']}
    files_by_type={t:[model.nx_graph.nodes[n]['source_file'] for n in ns] for t,ns in model.node_ids_dict.items()}
    functions_by_type={t:[function_lookup.get((type(original[n]).__name__,original[n])) for n in ns]
                       for t,ns in model.node_ids_dict.items()}
    archived=read_json(dest/'cv_validation_predictions.json')
    output=dict(job=job,variant=variant,device=device,trained_device=config['device'],
                cross_device=device!=config['device'],protocol=PROTOCOL,score_role=SCORE_ROLE,
                checkpoints={},status='running')
    normal_best=None
    for ck in (['best','initial','last'] if pilot else ['best']):
        ck_out=out/variant/ck;ck_out.mkdir(parents=True,exist_ok=False)
        if ck=='initial':
            assert_model_input(model,expected,external_inputs=binding)
            initial_path=fold_dir/(variant+'_initial.pt')
            if file_sha(initial_path)!=binding['initial_weights_sha256']: raise ValueError('Initial checkpoint changed')
            weights=torch.load(str(initial_path),map_location=device)
            model.load_state_dict(weights,strict=True);del weights
        else:
            obj=restore_checkpoint(dest/(ck+'.pt'),model,binding,results['checkpoint_sha256'][ck])
            del obj
        model.eval()
        weights_before=tensor_digest(model.state_dict())
        parameter_ids={n:id(p) for n,p in model.named_parameters()}
        graph_before=capture_model_input(model,external_inputs=binding)
        with torch.no_grad():
            native=part.forward(model).detach()
            native_probs=native.softmax(1)[:,1].cpu().tolist()
        gate=None
        if ck!='initial':
            gate=archived_gate(archived,records,job['task'],ck,native,native_probs,results['cv_validation'][ck])
        tags=dict(cohort=job['cohort'],task=job['task'],fold=job['fold'],variant=variant,checkpoint=ck,
                  condition='N',score_role=SCORE_ROLE)
        with torch.no_grad(),DiagnosticContext(model,mode='normal',record=True,
                    node_files_by_type=files_by_type,capture_representations=True,near_zero=TOLERANCES['near_zero_denominator']) as ctx:
            wrapped=part.forward(model).detach()
        if not torch.equal(native,wrapped): raise AssertionError('Diagnostic wrapper differs from native forward')
        n_cpu=native.cpu().numpy();normal_reps=ctx.representations
        write_csv(ck_out/'message_norms.csv',add_tags(ctx.rows,tags))
        if pilot: write_csv(ck_out/'parameter_scales.csv',add_tags(parameter_scales(model),tags))
        rows=[];prediction_rows=[];file_rows=[];rep_rows=[];rewiring=[]
        def export(condition,array,reference=n_cpu,reference_name='E1_N'):
            score,per_file,prob=compare_outputs(truth,reference,array,files)
            score.update(dict(tags,condition=condition,reference=reference_name))
            rows.append(score);file_rows.extend(add_tags(per_file,dict(tags,condition=condition,reference=reference_name)))
            pred=array.argmax(1).tolist()
            for i,record in enumerate(records):
                prediction_rows.append(dict(record,condition=condition,logits=array[i].tolist(),
                                            positive_probability=prob[i],prediction=pred[i],
                                            score_role=SCORE_ROLE))
            return score
        export('N',n_cpu,reference_name=variant+'_N')
        if ck=='best' and variant=='E0':
            normal_best=[dict(r,logits=n_cpu[i].tolist()) for i,r in enumerate(records)]
        if ck=='best' and variant=='E1':
            aligned=align_records(e0_reference,records,job['task'])
            e0_logits=np.asarray([r['logits'] for r in aligned],dtype=np.float32)
            comparison,per_file,_=compare_outputs(truth,e0_logits,n_cpu,files)
            rows.append(dict(comparison,**dict(tags,condition='E1_N_vs_E0_N',reference='E0_N')))
            file_rows.extend(add_tags(per_file,dict(tags,condition='E1_N_vs_E0_N',reference='E0_N')))
            with torch.no_grad(),DiagnosticContext(model,mode='zero',record=True,
                       node_files_by_type=files_by_type,capture_representations=True,near_zero=TOLERANCES['near_zero_denominator']) as zero_ctx:
                zero=part.forward(model).detach().cpu().numpy()
            export('Z',zero)
            write_csv(ck_out/'zero_message_norms.csv',add_tags(zero_ctx.rows,dict(tags,condition='Z')))
            rep_rows.extend(representations_difference(normal_reps,zero_ctx.representations,files_by_type,
                                                      dict(tags,condition='Z')))
            del zero_ctx
            original_graph=model.symmetrical_global_graph
            for seed in REWIRING_SEEDS:
                perturbed,audit=rewire_ddg(original_graph,files_by_type,functions_by_type,seed=seed)
                # This intervention manifest is separate from the validated original input.
                audit.update(seed=seed,cohort=job['cohort'],task=job['task'],fold=job['fold'])
                try:
                    model.symmetrical_global_graph=perturbed
                    with torch.no_grad(),DiagnosticContext(model,mode='normal',record=False,
                            node_files_by_type=files_by_type,capture_representations=True,near_zero=TOLERANCES['near_zero_denominator']) as rctx:
                        r=part.forward(model).detach().cpu().numpy()
                    export('R'+str(seed),r)
                    rep_rows.extend(representations_difference(normal_reps,rctx.representations,files_by_type,
                                                              dict(tags,condition='R'+str(seed))))
                finally:
                    model.symmetrical_global_graph=original_graph
                rewiring.append(audit);del perturbed,rctx
        with torch.no_grad():
            recovered=part.forward(model).detach()
        if not torch.equal(native,recovered): raise AssertionError('Native output not restored after diagnostics')
        if weights_before!=tensor_digest(model.state_dict()): raise AssertionError('Weights changed')
        if parameter_ids!={n:id(p) for n,p in model.named_parameters()}: raise AssertionError('Parameter identities changed')
        if graph_before!=capture_model_input(model,external_inputs=binding): raise AssertionError('Original graph/input changed')
        assert_model_input(model,expected,external_inputs=binding)
        write_csv(ck_out/'sensitivity.csv',rows);write_csv(ck_out/'file_changes.csv',file_rows)
        write_json(ck_out/'predictions.json',prediction_rows)
        write_csv(ck_out/'representation_changes.csv',rep_rows)
        write_json(ck_out/'rewiring_audit.json',rewiring)
        checkpoint_record=dict(native_replay_gate=gate,native_wrapper_exact=True,restored_native_exact=True,
                weights_sha256_before=weights_before,weights_sha256_after=tensor_digest(model.state_dict()),
                original_input=graph_before,original_input_restored=True,parameter_identities_preserved=True,
                conditions=[r['condition'] for r in rows],tolerances=TOLERANCES)
        write_json(ck_out/'checks.json',checkpoint_record)
        output['checkpoints'][ck]=checkpoint_record
        print('PASSED',job['id'],variant,ck,'conditions',[r['condition'] for r in rows],flush=True)
        del native,wrapped,recovered,normal_reps,ctx
    output['status']='passed'
    output['elapsed_seconds']=time.perf_counter()-started
    if torch.cuda.is_available():
        torch.cuda.synchronize(device)
        output['cuda_peak_allocated_bytes']=torch.cuda.max_memory_allocated(device)
        output['cuda_peak_reserved_bytes']=torch.cuda.max_memory_reserved(device)
    del model,part;gc.collect()
    if torch.cuda.is_available(): torch.cuda.empty_cache()
    return output,normal_best

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['pilot','remaining'],required=True)
    parser.add_argument('--device',default='cuda:0')
    parser.add_argument('--output-name',default=None,type=stage_name)
    parser.add_argument('--pilot-output',default='pilot',type=stage_name)
    args=parser.parse_args()
    preflight=validate_preflight(root=ROOT,run=RUN)
    # The archive reporter and input audit must have completed before model loading.
    if not (ROOT/'archive/asset_inventory.json').is_file(): raise ValueError('Archive assets not audited')
    if not (ROOT/'static/summary.json').is_file(): raise ValueError('Stage A static analysis not complete')
    if args.device!='cuda:0': raise ValueError('This frozen execution requires explicit same-device CUDA replay')
    if not torch.cuda.is_available(): raise RuntimeError('CUDA unavailable; no automatic CPU fallback')
    torch.set_num_threads(2)
    plan=read_json(RUN/'plan.json')
    jobs=plan['jobs']
    key=lambda j:(j['cohort'],j['task'],j['fold'])
    pilots=[next(j for j in jobs if key(j)==p) for p in PILOTS]
    stage_dir=ROOT/'forward'/(args.output_name or args.stage)
    stage_dir.mkdir(parents=True,exist_ok=False)
    write_json(stage_dir/'preflight.json',preflight)
    write_json(stage_dir/'policy.json',dict(protocol=PROTOCOL,score_role=SCORE_ROLE,tolerances=TOLERANCES,
                pilots=PILOTS,rewiring_seeds=REWIRING_SEEDS,device=args.device,model_residency='one model at a time',
                no_training=True,original_run=str(RUN),pilot_output=args.pilot_output,stage=args.stage,output_name=stage_dir.name,
                diagnostic_code_sha256={p.name:file_sha(p) for p in ROOT.glob('*.py')}))
    if args.stage=='remaining':
        gate=read_json(ROOT/'forward'/args.pilot_output/'completion.json')
        if gate.get('status')!='passed' or len(gate['jobs'])!=7: raise ValueError('Pilot gate not passed')
        selected=[j for j in jobs if key(j) not in PILOTS]
    else:selected=pilots
    outcomes=[];start=time.perf_counter()
    for job in selected:
        out=stage_dir/job['id'];out.mkdir()
        print('START',job['id'],flush=True)
        try:
            e0,reference=replay_variant(job,'E0',out,args.device,args.stage=='pilot')
            e1,_=replay_variant(job,'E1',out,args.device,args.stage=='pilot',reference)
            result=dict(job=job,status='passed',variants={'E0':e0,'E1':e1})
            write_json(out/'result.json',result);outcomes.append(job['id'])
        except Exception as exc:
            write_json(out/'failure.json',dict(type=type(exc).__name__,reason=str(exc),
                       no_automatic_retry=True,completed_jobs=outcomes))
            raise
    write_json(stage_dir/'completion.json',dict(status='passed',jobs=outcomes,
                          elapsed_seconds=time.perf_counter()-start))
    print('STAGE PASSED',args.stage,len(outcomes),flush=True)

if __name__=='__main__':main()
