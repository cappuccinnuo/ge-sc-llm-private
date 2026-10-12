"""Fixed-fold runner. No edits to the imported production model or trainers."""
import argparse, copy, gc, time, warnings
import numpy as np
import torch
from common import *
import sco_models.graph_utils as gu
gu.read_gpickle = lambda path: read_graph(Path(path))
from sco_models.model_hgt import HGTVulNodeClassifier, HGTVulGraphClassifier
from sco_models.tools import EarlyStopping

EXPERIMENTS = {
 "A_author": {"variant":"A_author"},
 "B_local_labels": {"variant":"B_local_labels","tasks":["node"]},
 "C_local_relations": {"variant":"C_local_relations"},
 "D_local_features": {"variant":"D_local_features"},
 "T_gradient_detached": {"variant":"A_author","gradient":"detached","tasks":["contract"]},
 "T_validation_legacy": {"variant":"A_author","validation":"legacy","tasks":["node"]},
 "T_lr_legacy": {"variant":"A_author","schedule":"legacy"},
 "T_delta_legacy": {"variant":"A_author","delta":0.005,"tasks":["contract"]},
 "T_upstream_behavior": {"variant":"A_author","upstream":True}
}

class StopMonitor:
    def __init__(self, patience, delta, legacy=False):
        self.patience=patience; self.delta=delta; self.legacy=legacy
        self.reference=None; self.best=float("inf"); self.counter=0
    def step(self, loss):
        if not np.isfinite(loss): raise ValueError("Nonfinite validation loss")
        improved=loss < self.best
        self.best=min(self.best,loss)
        significant=(self.reference is None or
                     (loss <= self.reference-self.delta if self.legacy else loss < self.reference-self.delta))
        if significant:self.reference=loss;self.counter=0
        else:self.counter+=1
        return improved,self.counter>=self.patience

def make_model(task, path, device):
    cls=HGTVulNodeClassifier if task=="node" else HGTVulGraphClassifier
    return cls(str(path),node_feature="inside_token",hidden_size=128,num_layers=2,
               num_heads=8,use_norm=True,device=device).to(device)

def gradient_hook(module, args):
    # Numerically identical float32 values to tolist()->torch.tensor(), same gradient cut.
    return (args[0].detach(),)

def initialize(model, task, prepared, init_dir, seed):
    init_dir.mkdir(parents=True,exist_ok=True)
    state_path=init_dir/"initial.pt";schema_path=init_dir/"schema.json"
    if not state_path.exists():
        seed_all(seed)
        ref=make_model(task,prepared/"A_author"/(task+".gpickle"),"cpu")
        state={k:v.detach().cpu().clone() for k,v in ref.state_dict().items()}
        torch.save(state,str(state_path))
        write_json(schema_path,{"seed":seed,"state_hash":tensor_digest(state),
            "edge_order":[list(k) for k,v in sorted(ref.etypes_dict.items(),key=lambda item:item[1])],
            "node_order":ref.ntypes_dict})
        del ref
    reference=torch.load(str(state_path),map_location="cpu");schema=read_json(schema_path)
    if tensor_digest(reference)!=schema["state_hash"] or schema["seed"]!=seed:
        raise ValueError("Initial checkpoint integrity failure")
    if model.ntypes_dict!=schema["node_order"]:
        raise ValueError("Node schema changed")
    old_edges={tuple(e):i for i,e in enumerate(schema["edge_order"])}
    current={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    shared_keys=[];unmatched=set()
    for name,value in current.items():
        relation=any(name.endswith(s) for s in ["relation_pri","relation_att","relation_msg"])
        if relation:
            for edge,index in model.etypes_dict.items():
                if edge in old_edges:value[index].copy_(reference[name][old_edges[edge]])
                else:unmatched.add(edge)
        else:
            if value.shape!=reference[name].shape:raise ValueError("Unexpected nonrelation shape")
            value.copy_(reference[name]);shared_keys.append(name)
    model.load_state_dict(current)
    actual=tensor_digest(current)
    if model.etypes_dict==old_edges and actual!=schema["state_hash"]:
        raise AssertionError("Paired initial weights differ")
    shared=tensor_digest({k:current[k] for k in shared_keys})
    if shared!=tensor_digest({k:reference[k] for k in shared_keys}):
        raise AssertionError("Common parameter initialization differs")
    return {"reference":str(state_path),"reference_hash":schema["state_hash"],"actual_hash":actual,
            "shared_nonrelation_hash":shared,"exact_reference_match":actual==schema["state_hash"],
            "new_canonical_relations":[list(x) for x in sorted(unmatched)],
            "canonical_relations":len(model.etypes_dict),
            "trainable_parameters":sum(p.numel() for p in model.parameters())}

def settings(task, experiment):
    spec=copy.deepcopy(EXPERIMENTS[experiment])
    if task not in spec.get("tasks",["node","contract"]):
        raise ValueError("Experiment not applicable to task")
    upstream=spec.get("upstream",False)
    return {"variant":spec["variant"],"gradient":("detached" if upstream and task=="contract" else spec.get("gradient","connected")),
            "validation":("legacy" if upstream and task=="node" else spec.get("validation","current")),
            "schedule":("legacy" if upstream else spec.get("schedule","current")),
            "delta":(0.005 if upstream and task=="contract" else spec.get("delta",0.001)),
            "legacy_stop":upstream,"primary_checkpoint":"last" if upstream else "best",
            "patience":7,"hidden_size":128,"layers":2,"heads":8,"hgt_dropout":0.2,
            "use_norm":True,"weight_decay":5e-6 if task=="contract" else 0.0,
            "batch_size":"full training fold (below original contract batch_size=256)",
            "note":"Controlled comparison with fixed splits/init/50-epoch cap; upstream_behavior is executable-behavior emulation, not proof of original paper settings."}

def run(args):
    prepared=Path(args.prepared).resolve();manifest=read_json(prepared/"manifest.json")
    cfg=settings(args.task,args.experiment)
    if cfg["variant"]=="D_local_features" and manifest["feature_variant_identical"]:
        raise ValueError("Feature variant is byte-identical; report alias to A instead of fitting")
    out=confined(args.output)
    config={"created_utc":utc(),"task":args.task,"experiment":args.experiment,"seed":args.seed,
            "epochs":args.epochs,"device":args.device,"settings":cfg,"prepared":str(prepared),
            "prepared_manifest_hash":sha256(prepared/"manifest.json"),
            "runner_hash":sha256(Path(__file__)),"model_hash":sha256(REPO/"sco_models/model_hgt.py")}
    out.mkdir(parents=True,exist_ok=True)
    if (out/"config.json").exists():
        old=read_json(out/"config.json")
        if any(old[k]!=config[k] for k in ["task","experiment","seed","epochs","settings","prepared_manifest_hash","runner_hash","model_hash"]):
            raise ValueError("Refuse mixing different experiment configurations")
    else:write_json(out/"config.json",config)
    fold_doc=read_json(prepared/(args.task+"_folds.json"))
    path=prepared/cfg["variant"]/(args.task+".gpickle")
    expected_hash=manifest["variants"][cfg["variant"]][args.task+"_sha256"]
    if sha256(path)!=expected_hash:raise ValueError("Graph changed after preparation")
    graph=read_graph(path)
    reference_graph=read_graph(prepared/"A_author"/(args.task+".gpickle"))
    reference_labels={n:int(bool(parse_records(d.get("node_info_vulnerabilities")))) for n,d in reference_graph.nodes(data=True)}
    del reference_graph
    if list(graph.nodes())!=list(range(len(graph))):raise ValueError("Bad node IDs")
    graph_labels={e["contract_name"]:int(e["targets"]) for e in read_json(prepared/"graph_labels.json")}
    folds=fold_doc["folds"]
    if args.folds:folds=[f for f in folds if f["fold"] in args.folds]
    torch.set_num_threads(args.threads)
    results=[]
    for split in folds:
        fold=split["fold"];dest=out/("fold_"+str(fold));dest.mkdir(exist_ok=True)
        if (dest/"result.json").exists():
            result=read_json(dest/"result.json")
            if result["graph_hash"]!=expected_hash or result["split_hash"]!=fold_doc["split_hash"]:
                raise ValueError("Completed fold provenance mismatch")
            print("RESUME completed fold",fold,flush=True);results.append(result);continue
        started=time.monotonic()
        fold_seed=args.seed*10000+fold+ (1000 if args.task=="contract" else 0)
        seed_all(fold_seed)
        model=make_model(args.task,path,args.device)
        init=initialize(model,args.task,prepared,
              prepared.parent/"initializations"/args.task/("seed_"+str(args.seed))/("fold_"+str(fold)),fold_seed)
        if args.experiment!="C_local_relations" and not init["exact_reference_match"]:
            raise AssertionError("Exact paired initialization required")
        hook=model.classify.register_forward_pre_hook(gradient_hook) if cfg["gradient"]=="detached" else None
        seed_all(fold_seed+1000000)
        train_files=split["train_files"];val_files=split["val_files"]
        trset=set(train_files);vaset=set(val_files)
        if trset&vaset or trset|vaset!={d["source_file"] for _,d in graph.nodes(data=True)}:
            raise ValueError("Invalid split")
        train_ids=[n for n,d in graph.nodes(data=True) if d["source_file"] in trset]
        val_ids=[n for n,d in graph.nodes(data=True) if d["source_file"] in vaset]
        if any((graph.nodes[s]["source_file"] in trset)!=(graph.nodes[t]["source_file"] in trset) for s,t in graph.edges()):
            raise ValueError("Cross-split graph edges")
        if args.task=="node":
            targets=torch.tensor(model.node_labels,dtype=torch.long,device=args.device)
            expected=[int(bool(parse_records(graph.nodes[n].get("node_info_vulnerabilities")))) for n in graph.nodes()]
            if targets.cpu().tolist()!=expected:raise AssertionError("Target row mismatch")
            trindex=torch.tensor(train_ids,device=args.device);vaindex=torch.tensor(val_ids,device=args.device)
            ytrain=targets[trindex];yval=targets[vaindex]
        else:
            ytrain=torch.tensor([graph_labels[f] for f in train_files],device=args.device)
            yval=torch.tensor([graph_labels[f] for f in val_files],device=args.device)
        optimizer=torch.optim.Adam(model.parameters(),lr=0.0002 if args.task=="node" else 0.0005,
                                   weight_decay=cfg["weight_decay"])
        max_lr=0.005 if args.task=="node" else 0.01
        if cfg["schedule"]=="current":
            scheduler=torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=max_lr,total_steps=args.epochs,
                     div_factor=25 if args.task=="node" else 20,final_div_factor=1)
        else:
            scheduler=torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=max_lr,total_steps=args.epochs)
        stop=StopMonitor(cfg["patience"],cfg["delta"],cfg["legacy_stop"])
        loss_fn=torch.nn.CrossEntropyLoss()
        (dest/"history.jsonl").write_text("",encoding="utf8")
        history=[];best_epoch=None;gradient_audit=None
        print("\nSTART {} {} seed={} fold={} train/val files={}/{} nodes={}/{}".format(
            args.task,args.experiment,args.seed,fold,len(train_files),len(val_files),len(train_ids),len(val_ids)),flush=True)
        for epoch in range(args.epochs):
            model.train();optimizer.zero_grad()
            if args.task=="node":
                training_logits=model(); train_logits=training_logits[trindex]
            else:train_logits=model(train_files)[0]
            loss=loss_fn(train_logits,ytrain);loss.backward()
            if epoch==0:
                grads={name:(p.grad is not None) for name,p in model.named_parameters()}
                gradient_audit={"classifier_has_grad":any(v for k,v in grads.items() if k.startswith("classify.")),
                                "backbone_has_grad":any(v for k,v in grads.items() if not k.startswith("classify."))}
                if gradient_audit["backbone_has_grad"]!=(cfg["gradient"]=="connected"):
                    raise AssertionError("Gradient intervention failed")
            lr=optimizer.param_groups[0]["lr"]
            optimizer.step()
            if cfg["schedule"]=="current" or args.task=="node":scheduler.step()
            if cfg["validation"]=="legacy":
                val_logits=training_logits[vaindex].detach()
                val_loss=loss_fn(val_logits,yval)
            else:
                model.eval()
                with torch.no_grad():
                    val_logits=model()[vaindex] if args.task=="node" else model(val_files)[0]
                    val_loss=loss_fn(val_logits,yval)
            train_metric=metrics(ytrain.detach().cpu().tolist(),train_logits.detach().argmax(1).cpu().tolist())
            val_metric=metrics(yval.detach().cpu().tolist(),val_logits.detach().argmax(1).cpu().tolist())
            improved,done=stop.step(float(val_loss))
            if improved:
                best_epoch=epoch
                torch.save(model.state_dict(),str(dest/"best.pt"))
            row={"epoch":epoch,"train_loss":float(loss.detach()),"val_loss":float(val_loss.detach()),
                 "lr":lr,"counter":stop.counter,"saved_best":improved,"train":train_metric,"validation":val_metric}
            history.append(row)
            with (dest/"history.jsonl").open("a") as f:f.write(json.dumps(row)+"\n")
            print("fold {} epoch {}/{} lr={:.6g} loss={:.5f}/{:.5f} val BF1={:.4f} MF1={:.4f} patience={}/7{}".format(
                fold,epoch+1,args.epochs,lr,row["train_loss"],row["val_loss"],val_metric["buggy_f1"],
                val_metric["macro_f1"],stop.counter," BEST" if improved else ""),flush=True)
            if done:break
        torch.save(model.state_dict(),str(dest/"last.pt"))
        rows=[];evaluations={}
        for checkpoint in ["best","last"]:
            model.load_state_dict(torch.load(str(dest/(checkpoint+".pt")),map_location=args.device));model.eval()
            with torch.no_grad():
                logits=model()[vaindex] if args.task=="node" else model(val_files)[0]
            pred=logits.argmax(1).cpu().tolist()
            evaluations[checkpoint]=metrics(yval.cpu().tolist(),pred)
            for i,(y,prediction) in enumerate(zip(yval.cpu().tolist(),pred)):
                if checkpoint=="best":
                    if args.task=="node":
                        n=val_ids[i];attrs=graph.nodes[n];file=attrs["source_file"]
                        row={"node":n,"author_full_node":attrs["original_node_id"],"file":file,
                             "node_type":attrs["node_type"],"y":y,"author_y":reference_labels[n],"best":prediction}
                    else:
                        file=val_files[i];row={"file":file,"y":y,"best":prediction}
                    row["origin"]=("clean" if args.task=="contract" and y==0 else
                                   "SolidiFI" if file.startswith("buggy_") else "SmartBugs")
                    rows.append(row)
                else:rows[i]["last"]=prediction
        write_json(dest/"predictions.json",rows)
        result={"fold":fold,"seed":fold_seed,"train_files":train_files,"val_files":val_files,
                "split_hash":fold_doc["split_hash"],"graph_hash":expected_hash,
                "initialization":init,"gradient_audit":gradient_audit,
                "best_epoch":best_epoch,"last_epoch":epoch,"monitored_best_loss":stop.best,
                "selection_note":"Legacy validation monitors pre-update train-mode logits; best.pt saves post-update weights. Final metrics always use eval().",
                "best":evaluations["best"],"last":evaluations["last"],
                "primary_checkpoint":cfg["primary_checkpoint"],"seconds":time.monotonic()-started,
                "against_author_labels":{k:metrics([x.get("author_y",x["y"]) for x in rows],[x[k] for x in rows]) for k in ["best","last"]},
                "checkpoint_hashes":{k:sha256(dest/(k+".pt")) for k in ["best","last"]}}
        write_json(dest/"result.json",result);results.append(result)
        print("FOLD COMPLETE",fold,"best",evaluations["best"],"last",evaluations["last"],flush=True)
        if hook:hook.remove()
        del model,optimizer,scheduler
        gc.collect()
        if torch.cuda.is_available():torch.cuda.empty_cache()
    result={"config":config,"fold_count":len(results),"expected_folds":fold_doc["k_folds"],"folds":results,
            "complete":len(results)==fold_doc["k_folds"]}
    for checkpoint in ["best","last"]:
        result[checkpoint]={metric:float(np.mean([f[checkpoint][metric] for f in results]))
                            for metric in ["buggy_f1","macro_f1"]}
    write_json(out/"result.json",result)
    print("EXPERIMENT COMPLETE",args.task,args.experiment,args.seed,result["best"],result["last"],flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared",type=Path,default=HERE/"artifacts/v1/prepared")
    p.add_argument("--task",choices=["node","contract"],required=True)
    p.add_argument("--experiment",choices=sorted(EXPERIMENTS),required=True)
    p.add_argument("--seed",type=int,default=1)
    p.add_argument("--epochs",type=int,default=50)
    p.add_argument("--device",default="cuda:0" if torch.cuda.is_available() else "cpu")
    p.add_argument("--threads",type=int,default=2)
    p.add_argument("--folds",type=int,nargs="+")
    p.add_argument("--output",type=Path,required=True)
    run(p.parse_args())
