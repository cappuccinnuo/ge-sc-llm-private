"""Read-only checkpoint/forward investigation; no fit, no historical mutation."""
import os,json,gc,math,hashlib,csv,time,datetime
from pathlib import Path
import torch
from scripts.DFG.experiments.overall_cv.common import verify_plan
from scripts.DFG.experiments.e23_pilot.model import make_model,semantic_state
from scripts.DFG.state.stage_f import FORWARD_RELATIONS
torch.set_num_threads(2)
R=Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
B=R/"scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1"
OUT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for x in iter(lambda:f.read(1048576),b""):h.update(x)
 return h.hexdigest()
def write(n,v):(OUT/n).write_text(json.dumps(v,indent=2)+"\n")
plan=verify_plan(B)
protected={str(B/x):sha(B/x) for x in ("plan.json","plan.seal.json","delivery_manifest.json","report.json")}
all_records=[];examples=[]
for tid in ("reentrancy_author_contract","access_control_author_contract"):
 for fold in range(5):
  info=read(B/"prepared"/tid/("fold_"+str(fold))/"task.json")
  files=sorted(info["split"]["val_files"])
  pair={};sem0=None
  for v in ("HCG","HCG_DDG"):
   p=B/"runs"/tid/("fold_"+str(fold))/v/"attempt_001"
   ck=p/"best.pt";protected[str(ck)]=sha(ck)
   rows={x["file"]:x for x in read(p/"cv_validation_predictions.json")}
   binding=read(p/"binding.json")
   assert binding["graph_sha256"]==info["graphs"][v]["sha256"]==sha(info["graphs"][v]["path"])
   d=torch.load(str(ck),map_location="cpu")
   assert d["binding"]["variant"]==v and d["binding"]["split"]["fold"]==fold
   m=make_model("contract",info["graphs"][v]["path"],"cpu")
   m.load_state_dict(d["state_dict"]);m.eval()
   with torch.no_grad():logits,_=m(files);probs=logits.softmax(-1)[:,1];preds=logits.argmax(-1)
   export_error=max(abs(float(probs[i])-rows[f]["best_positive_probability"]) for i,f in enumerate(files))
   assert export_error<1e-5,(tid,fold,v,export_error)
   assert all(int(preds[i])==rows[f]["best"] for i,f in enumerate(files))
   state=semantic_state(m)
   record=dict(variant=v,graph_sha256=binding["graph_sha256"],best_checkpoint_sha256=protected[str(ck)],
      parameters=sum(x.numel() for x in m.parameters()),base_or_enhanced_edges=m.nx_graph.number_of_edges(),
      canonical_relations=len(m.etypes_dict),reload_export_max_probability_error=export_error,
      reload_predictions_match=True,probabilities=probs.tolist(),predictions=preds.tolist(),
      best_epoch=d["epoch"])
   if v=="HCG":
    assert not any(c[1] in FORWARD_RELATIONS for c in m.etypes_dict)
    sem0={k:x.clone() for k,x in state.items()}
   else:
    ddg=[(c,i) for c,i in m.etypes_dict.items() if c[1] in FORWARD_RELATIONS]
    assert ddg
    record["ddg_canonical_count"]=len(ddg)
    record["ddg_dgl_edges"]=sum(m.symmetrical_global_graph.num_edges(c) for c,_ in ddg)
    common=list(sem0);assert set(common)<=set(state)
    record["trained_common_tensors_different"]=sum(not torch.equal(sem0[k],state[k]) for k in common)
    record["trained_common_tensors_total"]=len(common)
    assert record["trained_common_tensors_different"]>0
    with torch.no_grad():
     for layer in m.gcs:
      for c,i in ddg:layer.relation_msg[i].zero_()
     off_logits,_=m(files);off_probs=off_logits.softmax(-1)[:,1]
     record["in_memory_message_zeroing"]={
       "kind":"DDG relation_msg slices zeroed on CPU only; all schema/edges retained",
       "logits_max_abs_change":float((off_logits-logits).abs().max()),
       "probability_mean_abs_change":float((off_probs-probs).abs().mean()),
       "probability_max_abs_change":float((off_probs-probs).abs().max()),
       "probabilities_changed":int((off_probs!=probs).sum()),
       "predictions_changed":int((off_logits.argmax(-1)!=preds).sum()),
       "interpretation":"inference sensitivity diagnostic; not retrained E0 or a formal performance ablation"}
     assert record["in_memory_message_zeroing"]["logits_max_abs_change"]>0
     m.load_state_dict(d["state_dict"]);restored_logits,_=m(files)
     assert torch.equal(logits,restored_logits)
     record["restored_forward_exact"]=True
   pair[v]=record
   del state,m,d;gc.collect()
  a=pair["HCG"];z=pair["HCG_DDG"]
  assert a["graph_sha256"]!=z["graph_sha256"] and a["best_checkpoint_sha256"]!=z["best_checkpoint_sha256"]
  diffs=[abs(x-y) for x,y in zip(a["probabilities"],z["probabilities"])]
  rec=dict(task_id=tid,fold=fold,n=len(files),variants=pair,
    same_classification_count=sum(x==y for x,y in zip(a["predictions"],z["predictions"])),
    changed_probability_count=sum(x!=y for x,y in zip(a["probabilities"],z["probabilities"])),
    mean_absolute_probability_change=sum(diffs)/len(diffs),max_absolute_probability_change=max(diffs))
  all_records.append(rec)
  for i,f in enumerate(files):
   examples.append(dict(task_id=tid,fold=fold,file=f,target=rows[f]["target"],HCG_probability=a["probabilities"][i],
      DDG_probability=z["probabilities"][i],HCG_prediction=a["predictions"][i],DDG_prediction=z["predictions"][i],abs_change=diffs[i]))
  write("progress.json",all_records)
  print("VERIFIED",tid,fold,"same_class",rec["same_classification_count"],"n",len(files),
        "mean_dp",rec["mean_absolute_probability_change"],"zero_msg_effect",z["in_memory_message_zeroing"]["logits_max_abs_change"],flush=True)
  del sem0;gc.collect()
assert len(all_records)==10
assert all(sha(p)==h for p,h in protected.items())
write("recheck.json",dict(status="passed",created_at=datetime.datetime.utcnow().isoformat()+"Z",
  contract_pairs=10,reloaded_checkpoints=20,formal_retraining=0,device="cpu",
  no_historical_changes=True,protected=protected,records=all_records))
with (OUT/"probability_examples.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(examples[0]));w.writeheader();w.writerows(sorted(examples,key=lambda x:-x["abs_change"]))
print("ALL_CONTRACT_PAIRS_PASSED",flush=True)
