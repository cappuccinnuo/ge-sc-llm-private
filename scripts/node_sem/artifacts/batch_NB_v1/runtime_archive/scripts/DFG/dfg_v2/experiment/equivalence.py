"""Three-epoch engine validation only; never a nested efficacy estimate.

Replays the historical paper train/val split in BOTH engines to isolate loop
equivalence. The repeated validation-only export role below is intentionally
confined to this diagnostic; production plans validate disjoint nested parts.
"""
import argparse
import copy
import gc
from pathlib import Path
import torch
from scripts.DFG.experiments.common import read_json,write_json,sha256,seed_all,tensor_digest
from scripts.DFG.experiments.paper_run import fit_variant
from scripts.DFG.experiments import paper_protocol as paper
from scripts.DFG.experiments.paper_runtime import Supervision,graph_schema_and_support
from scripts.DFG.experiments.runtime import make_model as old_model
from scripts.DFG.dfg_v2.model import make_model
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision
from scripts.DFG.dfg_v2.tasks import checked_ref
from .checkpoint import build_binding
from .trainer import fit


def _move(model,device):
    model.to(device)
    model.device=str(device)
    model.symmetrical_global_graph=model.symmetrical_global_graph.to(device)
    if hasattr(model,"supervised_node_mask"):
        model.supervised_node_mask=model.supervised_node_mask.to(device)
    return model


def _history(path):
    import json
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def run(manifest,output,device="cpu",historical_history=None):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    manifest=Path(manifest).resolve()
    info=read_json(manifest)
    if info["task_id"]!="reentrancy_author_contract" or info["fold"]!=0:
        raise ValueError("Numerical replay is fixed to reentrancy contract fold0")
    config=copy.deepcopy(info["config"])
    config.update(maximum_training_epochs=3,mode="engine_equivalence",device=device)
    if config["schedule_epochs"]!=50:
        raise ValueError("Numerical replay keeps original 50-step scheduler")
    torch.set_num_threads(config["threads"])
    graph_ref=info["graphs"]["HCG"]
    gp=checked_ref(graph_ref)
    init_ref=info["initialization"]["HCG"]
    initial=torch.load(str(checked_ref(init_ref)),map_location="cpu")
    initial_state=initial["state_dict"]
    if tensor_digest(initial_state)!=init_ref["state_sha256"]:
        raise ValueError("Historical initial tensor digest differs")
    label_ref=dict(path=info["labels_path"],sha256=info["labels_sha256"])
    labels={r["contract_name"]:int(r["targets"]) for r in read_json(checked_ref(label_ref))}
    split=info["split"]
    engines=("old","new") if device=="cpu" else ("new",)
    for engine in engines:
        seed_all(info["seeds"]["constructor"])
        model=(old_model("contract",gp,"cpu") if engine=="old" else
               make_model("contract",gp,"G0",device="cpu"))
        if tensor_digest(model.state_dict())!=init_ref["state_sha256"]:
            raise AssertionError("Fresh constructor no longer matches frozen historical initial")
        model.load_state_dict(initial_state)
        model=_move(model,device)
        registration=graph_schema_and_support(model.nx_graph,split)
        seed_all(info["fit_seed"])
        if engine=="old":
            parts={n:Supervision(model,"contract",split[n+"_files"]) for n in ("train","val")}
            binding=dict(protocol=paper.NAME,protocol_version=paper.VERSION,
                initialization_version=paper.INITIALIZATION_VERSION,
                forward_scope=paper.FORWARD_SCOPE,score_role=paper.SCORE_ROLE,
                registered_schema=registration["schema"],purpose="engine_equivalence_only")
            fit_variant(model,parts,"contract",labels,config,output/engine,binding,list(model.nx_graph),registration)
        else:
            parts={n:DfgV2Supervision(model,"contract",split[k+"_files"])
                for n,k in (("inner_train","train"),("inner_val","val"),("outer_test","val"))}
            # No v2 relations in G0. Production support never accepts duplicated parts.
            audit=dict(schema=registration["schema"],profile="G0",relations=[],
                v2_training_edges=0,purpose="engine_equivalence_only")
            binding=build_binding(model,task_id="reentrancy_contract",fold=0,seed=1,profile="G0",
                reducer="mean",graph_ref=graph_ref,
                fold_ref=dict(path=info["source_splits_path"],sha256=info["source_splits_sha256"]),
                label_ref=label_ref,initial_sha256=init_ref["sha256"],config=config,
                split=split,support=audit)
            binding["purpose"]="engine_equivalence_only_repeated_val_export_not_outer_test"
            binding["initial_state_sha256"]=init_ref["state_sha256"]
            fit(model,parts,"contract",labels,config,output/engine,binding,model.original_graph_node_ids,audit)
        del model,parts
        gc.collect()
        if device!="cpu":
            torch.cuda.empty_cache()
    new=_history(output/"new"/"history.jsonl")
    if device=="cpu":
        old=_history(output/"old"/"history.jsonl")
        tolerance=1e-6
        reference=dict(path=str(output/"old"/"history.jsonl"),sha256=sha256(output/"old"/"history.jsonl"))
    else:
        if historical_history is None:
            raise ValueError("GPU replay requires frozen historical history")
        hp=Path(historical_history).resolve()
        receipt=read_json(hp.parent/"receipt.json")
        if receipt["artifacts"].get("history.jsonl")!=sha256(hp):
            raise ValueError("Historical history receipt mismatch")
        old=_history(hp)[:3]
        tolerance=1e-4
        reference=dict(path=str(hp),sha256=sha256(hp))
    if len(old)!=3 or len(new)!=3:
        raise AssertionError("Expected exactly three replay epochs")
    differences=[dict(epoch=a["epoch"],train=abs(a["train_loss"]-b["train_loss"]),
        validation=abs(a["cv_validation_loss"]-b["inner_val_loss"]))
        for a,b in zip(old,new)]
    maximum=max(max(r["train"],r["validation"]) for r in differences)
    report=dict(status="accepted" if maximum<=tolerance else "failed",device=device,
        tolerance=tolerance,maximum_absolute_loss_difference=maximum,differences=differences,
        historical_config_sha256=sha256(manifest),initial=init_ref,reference=reference,
        train_files=len(split["train_files"]),validation_files=len(split["val_files"]),
        schedule_epochs=50,epochs=3,purpose="numerical_engine_validation_not_nested_result",
        not_counted_as_formal_fit=True)
    write_json(output/"equivalence.json",report)
    if maximum>tolerance:
        raise AssertionError("Numerical engine tolerance exceeded")
    print(report,flush=True)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--device",choices=("cpu","cuda:0"),default="cpu")
    p.add_argument("--historical-history")
    a=p.parse_args()
    run(a.manifest,a.output,a.device,a.historical_history)


if __name__=="__main__":
    main()
