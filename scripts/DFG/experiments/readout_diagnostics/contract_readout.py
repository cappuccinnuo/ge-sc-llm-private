"""Existing best checkpoints only; no fit, no edited graph, no alternative-pooling score."""
import argparse,csv,gc,hashlib,json,subprocess,time
from pathlib import Path
import torch
from scripts.DFG.experiments.common import read_json,write_json,sha256,tensor_digest
from scripts.DFG.experiments.guard_extension.common import verify_plan,DEFAULT
from scripts.DFG.experiments.guard_extension.archive import verify_archive
from scripts.DFG.experiments.guard_extension import checks as guard_checks
from scripts.DFG.experiments.overall_cv import checks as old_checks
from scripts.DFG.experiments.guard_extension.model import make_model as guard_model
from scripts.DFG.experiments.e23_pilot.model import make_model as old_model,move_to_device
from scripts.DFG.experiments.guard_extension.checkpoint import restore_checkpoint as guard_restore
from scripts.DFG.experiments.overall_cv.checkpoint import restore_checkpoint as old_restore
from .core import capture_forward,decompose,validate_export,author_node_target,PROBABILITY_ATOL
from . import VERSION
ROOT=Path(__file__).resolve().parents[4]
TASKS=("reentrancy_author_contract","access_control_author_contract")
VARIANTS=("HCG","HCG_DDG","HCG_DDG_GUARD")

def csv_write(path,rows):
    if not rows:raise ValueError("Empty diagnostic export")
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def graph_labels(path):
    out={}
    for row in read_json(path):
        if row["contract_name"] in out:raise ValueError("Duplicate graph label")
        out[row["contract_name"]]=row["targets"]
    return out

def manifest_for(plan,tid,fold):
    refs=[x for x in plan["tasks"] if x["task_id"]==tid and x["fold"]==fold]
    if len(refs)!=1:raise ValueError("Missing/duplicate manifest")
    ref=refs[0]
    if sha256(ref["manifest"])!=ref["sha256"]:raise ValueError("Manifest drift")
    return read_json(ref["manifest"]),ref

def run(output,guard_batch):
    output,guard_batch=Path(output),Path(guard_batch)
    if output.exists():raise FileExistsError("New diagnostic attempt required; no overwrite/resume")
    if not torch.cuda.is_available():raise RuntimeError("Recorded CUDA unavailable; no automatic CPU substitution")
    output.mkdir(parents=True);torch.set_num_threads(2);started=time.monotonic();current=None
    try:
        guard_plan=verify_plan(guard_batch);old_batch=Path(guard_plan["source_batch"])
        old_plan,archive=verify_archive(old_batch);write_json(output/"archive_acceptance.json",archive)
        runtime={str(p):sha256(p) for p in [Path(__file__),Path(__file__).with_name("core.py"),Path(__file__).with_name("__init__.py")]}
        write_json(output/"diagnostic_plan.json",dict(version=VERSION,score_role="cv_validation",checkpoint="best",
            purpose="float64 linear reference decomposition plus explicit GPU residual; not a node classifier",tasks=list(TASKS),variants=list(VARIANTS),
            folds=5,trained_models=0,forward_count=30,device="cuda:0",runtime=runtime,
            source_plans={str(guard_batch/"plan.json"):sha256(guard_batch/"plan.json"),str(old_batch/"plan.json"):sha256(old_batch/"plan.json")},
            tolerances=dict(probability_absolute=1e-5,pool_absolute=1e-5,relative=1e-5,float64_identity_absolute=1e-10,head_replay="torch.equal",old_reference_logit_diagnostic=1e-4),
            numeric_backend=dict(torch_version=torch.__version__,cuda_version=torch.version.cuda,matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32,cudnn_allow_tf32=torch.backends.cudnn.allow_tf32),
            source_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip()))
        protected={};all_files=[];all_nodes=[];jobs=[]
        for tid in TASKS:
            for fold in range(5):
                for variant in VARIANTS:
                    current=dict(task_id=tid,fold=fold,variant=variant);is_guard=variant=="HCG_DDG_GUARD"
                    batch,plan=(guard_batch,guard_plan) if is_guard else (old_batch,old_plan)
                    info,ref=manifest_for(plan,tid,fold);check=guard_checks if is_guard else old_checks
                    accepted=check.completed(batch,current,plan)
                    if accepted is None:raise ValueError("Missing accepted fit")
                    receipt=read_json(accepted/"receipt.json");binding=read_json(accepted/"binding.json");graph=info["graphs"][variant]
                    if sha256(graph["path"])!=graph["sha256"] or binding["graph_sha256"]!=graph["sha256"]:raise ValueError("Graph digest mismatch")
                    for key in ("labels","source_prepared_manifest"):
                        path=info["labels_path"] if key=="labels" else info[key]
                        expected=info["labels_sha256"] if key=="labels" else info[key+"_sha256"]
                        if sha256(path)!=expected:raise ValueError("Input digest mismatch "+key)
                        protected[str(path)]=expected
                    sources=read_json(info["source_prepared_manifest"])["sources"];files=sorted(info["split"]["val_files"])
                    if set(files)&set(info["split"]["train_files"]):raise ValueError("Train/val overlap")
                    rows=validate_export(files,read_json(accepted/"cv_validation_predictions.json"),sources,graph_labels(info["labels_path"]))
                    for f in files:
                        if sha256(sources[f]["path"])!=sources[f]["sha256"]:raise ValueError("Source byte mismatch")
                        protected[sources[f]["path"]]=sources[f]["sha256"]
                    ck=accepted/"best.pt";expected_ck=receipt["artifacts"]["best.pt"]
                    protected[str(ck)]=expected_ck;protected[graph["path"]]=graph["sha256"];protected[ref["manifest"]]=ref["sha256"]
                    cfg=info["config"]
                    if cfg["device"]!="cuda:0" or cfg["feature"]!="inside_token":raise ValueError("Unexpected frozen device/features")
                    maker=guard_model if is_guard else old_model
                    model=maker("contract",graph["path"],"cpu",cfg["hidden_size"],cfg["layers"],cfg["heads"])
                    restore=guard_restore if is_guard else old_restore
                    obj=restore(ck,model,binding,expected_ck);state_digest=obj["state_sha256"];epoch=obj["epoch"];del obj
                    model=move_to_device(model,"cuda:0");model.eval();torch.cuda.reset_peak_memory_stats();tick=time.monotonic()
                    h,pool,logits,pool_error,replay=capture_forward(model,files);torch.cuda.synchronize()
                    probs=logits.softmax(-1)[:,1];preds=logits.argmax(-1)
                    probability_error=max(abs(float(probs[i])-rows[f]["best_positive_probability"]) for i,f in enumerate(files))
                    if probability_error>=PROBABILITY_ATOL or any(int(preds[i])!=rows[f]["best"] for i,f in enumerate(files)):raise ValueError("Export probability/class mismatch")
                    w=model.classify.weight.detach().cpu().clone();b=model.classify.bias.detach().cpu().clone();job_files=[];job_nodes=[]
                    for i,f in enumerate(files):
                        ids=model.node_ids_by_filename[f]
                        if len(ids)!=len(set(ids)):raise ValueError("Duplicate file nodes")
                        for n in ids:
                            attrs=model.nx_graph.nodes[n]
                            if attrs["source_file"]!=f or model.node_ids_dict[attrs["node_type"]][attrs["node_hetero_id"]]!=n:raise ValueError("File/type row mapping mismatch")
                        score,contribution,local,stats=decompose(h[ids],w,b,logits[i],pool[i],replay[i]);target=rows[f]["target"];pred=int(preds[i])
                        outcome=("TP" if target else "FP") if pred else ("FN" if target else "TN")
                        identity=dict(task_id=tid,cohort=info["cohort"],fold=fold,variant=variant,file=f,source_sha256=sources[f]["sha256"])
                        rec=dict(identity,score_role="cv_validation",checkpoint="best",target=target,prediction=pred,outcome=outcome,
                            probability=float(probs[i]),historical_probability=rows[f]["best_positive_probability"],**stats)
                        rec["mixed_local_margin_signs"]=stats["positive_local_margin_nodes"]>0 and stats["negative_local_margin_nodes"]>0
                        rec["diagnostic_fn_with_positive_local_evidence"]=outcome=="FN" and stats["max_local_margin"]>0 and stats["reference_actual_class_agree"]
                        labels=[bool(author_node_target(model.nx_graph.nodes[n])) for n in ids]
                        rec["author_positive_nodes"]=sum(labels)
                        rec["author_positive_contribution_sum"]=float(contribution[torch.tensor(labels,dtype=torch.bool)].sum())
                        rec["author_other_contribution_sum"]=float(contribution[torch.tensor([not x for x in labels],dtype=torch.bool)].sum())
                        job_files.append(rec)
                        for j,n in enumerate(ids):
                            attrs=model.nx_graph.nodes[n];code=str(attrs.get("code",attrs.get("label","")))
                            job_nodes.append(dict(identity,original_graph_node_id=str(model.original_graph_node_ids[n]),model_node_id=n,
                                node_type=attrs["node_type"],graph_stored_source_lines=json.dumps(attrs.get("node_source_code_lines")),
                                author_node_target=int(labels[j]),node_score=float(score[j]),normalized_contribution=float(contribution[j]),
                                local_margin_with_shared_bias=float(local[j]),code_sha256=hashlib.sha256(code.encode()).hexdigest(),code_preview=code[:400]))
                    if tensor_digest(model.state_dict())!=state_digest or any(p.grad is not None for p in model.parameters()):raise ValueError("Weights/gradients changed")
                    folder=output/tid/("fold_"+str(fold))/variant;folder.mkdir(parents=True)
                    csv_write(folder/"files.csv",job_files);csv_write(folder/"nodes.csv",job_nodes)
                    record=dict(current,status="complete",checkpoint_sha256=expected_ck,graph_sha256=graph["sha256"],
                        historical_receipt=str(accepted/"receipt.json"),historical_receipt_sha256=sha256(accepted/"receipt.json"),
                        state_sha256=state_digest,source_manifest_sha256=info["source_prepared_manifest_sha256"],epoch=epoch,
                        pool_max_abs_error=pool_error,probability_max_abs_error=probability_error,
                        decomposition_max_abs_error=max(x["reconstruction_max_abs_error"] for x in job_files),
                        files=len(job_files),nodes=len(job_nodes),seconds=time.monotonic()-tick,
                        peak_allocated_mib=torch.cuda.max_memory_allocated()/1024**2,peak_reserved_mib=torch.cuda.max_memory_reserved()/1024**2,
                        head_replay_exact=True,weights_unchanged=True,backward_calls=0,fit_calls=0,artifacts={k:sha256(folder/k) for k in ["files.csv","nodes.csv"]})
                    write_json(folder/"receipt.json",record);jobs.append(record);all_files.extend(job_files);all_nodes.extend(job_nodes)
                    write_json(output/"progress.json",dict(completed=len(jobs),expected=30,last=current))
                    print("VERIFIED_READOUT",tid,fold,variant,len(job_files),"files",probability_error,flush=True)
                    del model,h,pool,logits,replay,probs,preds,w,b,score,contribution,local
                    gc.collect();torch.cuda.empty_cache()
        for path,expected in protected.items():
            if sha256(path)!=expected:raise ValueError("Historical input/checkpoint mutated")
        if any(sha256(path)!=h for path,h in runtime.items()):raise ValueError("Runtime changed during execution")
        if len(all_files)!=768 or len(all_nodes)!=95232 or len(jobs)!=30:raise ValueError("Incomplete held-out population")
        for entries,fields in [(all_files,["task_id","variant","file","source_sha256"]),(all_nodes,["task_id","variant","file","source_sha256","original_graph_node_id"])]:
            if len({tuple(x[k] for k in fields) for x in entries})!=len(entries):raise ValueError("Duplicate OOF identity")
        csv_write(output/"contract_files.csv",all_files);csv_write(output/"node_contributions.csv",all_nodes)
        groups=[]
        for tid in TASKS:
            for variant in VARIANTS:
                for outcome in ["TP","TN","FP","FN"]:
                    g=[x for x in all_files if x["task_id"]==tid and x["variant"]==variant and x["outcome"]==outcome]
                    groups.append(dict(task_id=tid,variant=variant,outcome=outcome,files=len(g),
                        mixed_local_margin_signs=sum(x["mixed_local_margin_signs"] for x in g),
                        fn_with_positive_local_evidence=sum(x["diagnostic_fn_with_positive_local_evidence"] for x in g),
                        mean_nodes=sum(x["nodes"] for x in g)/len(g) if g else None,mean_margin=sum(x["margin"] for x in g)/len(g) if g else None))
        write_json(output/"summary.json",dict(status="complete",version=VERSION,score_role="cv_validation",fits=0,checkpoints=30,
            held_out_file_rows=len(all_files),held_out_node_rows=len(all_nodes),groups=groups,jobs=jobs,source_unchanged=True,
            protected=protected,seconds=time.monotonic()-started,
            interpretation="Local margin is contextual contract-head evidence, not node prediction. Mixed signs do not prove pooling failure; no alternative-pooling scores or threshold search."))
        print("READOUT_DIAGNOSTIC_COMPLETE",len(jobs),len(all_files),len(all_nodes),flush=True)
    except BaseException as exc:
        write_json(output/"failure.json",dict(status="failed",job=current,error=repr(exc),fits=0,seconds=time.monotonic()-started));raise

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True);p.add_argument("--guard-batch",type=Path,default=DEFAULT)
    a=p.parse_args();run(a.output,a.guard_batch)
if __name__=="__main__":main()
