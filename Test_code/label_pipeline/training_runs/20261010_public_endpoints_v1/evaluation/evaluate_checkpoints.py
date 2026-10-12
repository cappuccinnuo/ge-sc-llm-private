"""Read-only checkpoint evaluation and label/duplication diagnostics; Codex 2026-10-10.
Never retrains, changes a graph, or selects epochs using these diagnostics.
Author-label rescoring is an evaluation-only sensitivity check, not author-label training.
"""
import csv,gc,hashlib,json,sys
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
import torch
from sklearn.metrics import f1_score,confusion_matrix

REPO=Path("/home/zhao/SmartContract/ge-sc-llm")
RUN=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(REPO/"scripts/labeling_v2"))
from sco_models.model_hgt import HGTVulGraphClassifier,HGTVulNodeClassifier
from safe_graph import read_graph
from label_rules import parse_records

def score(y,p):
 y=np.asarray(y,dtype=int);p=np.asarray(p,dtype=int)
 if not len(y):return {"n":0}
 return dict(n=len(y),positives=int(y.sum()),
  buggy_f1=float(f1_score(y,p,average="binary",zero_division=0)*100),
  macro_f1=float(f1_score(y,p,average="macro",labels=[0,1],zero_division=0)*100),
  confusion_matrix=confusion_matrix(y,p,labels=[0,1]).tolist())

def log(s):
 print(s,flush=True)
 with (OUT/"evaluate.log").open("a") as f:f.write(s+"\n")

def main():
 manifest=json.loads((RUN/"run_manifest.json").read_text())
 results=json.loads((OUT/"results.json").read_text()) if (OUT/"results.json").exists() else []
 device="cuda:0" if torch.cuda.is_available() else "cpu"
 for job in manifest["jobs"]:
  if any(r["name"]==job["name"] for r in results):
   log("ALREADY EVALUATED "+job["name"]);continue
  log("START "+job["name"])
  is_node=job["task"]=="linelevel"
  cls=HGTVulNodeClassifier if is_node else HGTVulGraphClassifier
  model=cls(job["graph"],feature_extractor=None,node_feature="inside_token",device=device).to(device)
  records=[]
  all_y=[];all_pred={"best":[],"last":[]}
  all_author=[];all_seen=[];all_family=[];all_lookup=[];all_type=[]
  base=Path(job["graph"]).parent
  if is_node:
   graph=model.nx_graph
   n=len(graph)
   assert list(graph.nodes())==list(range(n))
   y=np.asarray(model.node_labels,dtype=int)
   files=np.array([graph.nodes[i]["source_file"] for i in range(n)])
   code=np.array([graph.nodes[i].get("code") or "" for i in range(n)],dtype=object)
   types=np.array([graph.nodes[i]["node_type"] for i in range(n)])
   line_ids=json.loads((base/"line_node_ids.json").read_text())
   assert [m["line_node_id"] for m in line_ids]==list(range(n))
   old_to_line={m["input_node_id"]:m["line_node_id"] for m in line_ids}
   author_y=y.copy()
   differences=json.loads((base/"label_differences.json").read_text())
   for d in differences:
    idx=old_to_line[d["node_id"]]
    assert y[idx]==d["public"] and files[idx]==d["source_file"]
    author_y[idx]=d["author"]
   assert int(author_y.sum())=={"reentrancy":6570,"access_control":2977}[job["category"]]
   stats=json.loads((base/"manifest.json").read_text())
   old=read_graph(Path(stats["graph_input"]))
   changed_old=sum(bool(parse_records(old.nodes[m["input_node_id"]].get("node_info_vulnerabilities")))!=bool(y[m["line_node_id"]]) for m in line_ids)
   label_info=dict(old_input_positive=stats["stats"]["input"]["positive_nodes"],
     current_positive=int(y.sum()),author_positive=int(author_y.sum()),
     changed_from_old_input=int(changed_old),differing_from_author=int((y!=author_y).sum()))
   del old
   oof_seen=np.zeros(n,dtype=int)
   oof_pred={kind:np.zeros(n,dtype=int) for kind in ("best","last")}
  else:
   labels=json.loads(Path(job["label_manifest"]).read_text())
   targets={d["contract_name"]:int(d["targets"]) for d in labels}
   label_info=None
  for fold in range(job["folds"]):
   model_path=Path(job["output_model"])
   folder=model_path.parent/(model_path.stem+"_fold"+str(fold))
   sel=json.loads((folder/"selection.json").read_text())
   val_files=sel["val_files"];train_files=sel["train_files"]
   assert not(set(val_files)&set(train_files))
   if is_node:
    ids=np.flatnonzero(np.isin(files,val_files))
    train_ids=np.flatnonzero(np.isin(files,train_files))
    assert len(ids)+len(train_ids)==n
    targets_now=y[ids]
    train_codes=set(code[train_ids])
    seen=np.array([x in train_codes for x in code[ids]])
    lookup=defaultdict(Counter)
    for i in train_ids:lookup[code[i]][int(y[i])]+=1
    majority=int(y[train_ids].mean()>0.5)
    lookup_pred=[(int(lookup[c][1]>lookup[c][0]) if c in lookup else majority) for c in code[ids]]
    all_author.extend(author_y[ids]);all_seen.extend(seen)
    all_family.extend(["SolidiFI" if Path(f).name.startswith("buggy_") else "SmartBugs" for f in files[ids]])
    all_lookup.extend(lookup_pred);all_type.extend(types[ids])
    oof_seen[ids]+=1
   else:targets_now=np.array([targets[f] for f in val_files])
   all_y.extend(targets_now)
   record=dict(fold=fold,best_epoch=sel["best_epoch"],last_epoch=sel["last_epoch"],val_files=val_files)
   for kind in ("best","last"):
    model.load_state_dict(torch.load(str(folder/(kind+".pt")),map_location=device))
    model.eval()
    with torch.no_grad():
     logits=model()[ids] if is_node else model(val_files)[0]
     pred=logits.argmax(dim=1).cpu().numpy()
    record[kind]=score(targets_now,pred)
    all_pred[kind].extend(pred)
    if is_node:
     oof_pred[kind][ids]=pred
     record[kind+"_author_labels"]=score(author_y[ids],pred)
    if kind=="best":
     assert abs(record[kind]["buggy_f1"]-sel["best_val_buggy_f1"]*100)<1e-5
     assert abs(record[kind]["macro_f1"]-sel["best_val_macro_f1"]*100)<1e-5
   records.append(record)
   log("{} fold {}: best {:.4f}/{:.4f}; last {:.4f}/{:.4f}".format(job["name"],fold,
       record["best"]["buggy_f1"],record["best"]["macro_f1"],record["last"]["buggy_f1"],record["last"]["macro_f1"]))
  result=dict(name=job["name"],category=job["category"],task=job["task"],folds=records,label_info=label_info)
  Y=np.array(all_y);A=np.array(all_author);S=np.array(all_seen);F=np.array(all_family);T=np.array(all_type)
  for kind in ("best","last"):
   pred=np.array(all_pred[kind])
   result[kind]=dict(mean_buggy_f1=float(np.mean([x[kind]["buggy_f1"] for x in records])),
     mean_macro_f1=float(np.mean([x[kind]["macro_f1"] for x in records])),pooled_oof=score(Y,pred))
   if is_node:
    result[kind]["author_label_rescore_mean_buggy_f1"]=float(np.mean([x[kind+"_author_labels"]["buggy_f1"] for x in records]))
    result[kind]["author_label_rescore_mean_macro_f1"]=float(np.mean([x[kind+"_author_labels"]["macro_f1"] for x in records]))
    result[kind]["subgroups_pooled"]={name:score(Y[mask],pred[mask]) for name,mask in
     [("seen_exact_code",S),("unseen_exact_code",~S),("SolidiFI",F=="SolidiFI"),("SmartBugs",F=="SmartBugs"),
      ("labels_agree",Y==A),("labels_disagree",Y!=A)]}
    result[kind]["node_types_pooled"]={t:score(Y[T==t],pred[T==t]) for t in sorted(set(T))}
  if is_node:
   assert set(oof_seen)=={1}
   result["lookup_baseline_pooled"]=score(Y,all_lookup)
   result["seen_exact_code_percent"]=float(S.mean()*100)
   np.savez_compressed(str(OUT/(job["name"]+"_oof.npz")),node_ids=np.arange(n),source_files=files,
    public_labels=y,author_labels=author_y,best=oof_pred["best"],last=oof_pred["last"])
  results.append(result)
  (OUT/"results.json").write_text(json.dumps(results,indent=2)+"\n")
  del model
  gc.collect();torch.cuda.empty_cache()
  log("COMPLETE "+job["name"]+" "+str(result["best"]["mean_buggy_f1"])+" "+str(result["last"]["mean_buggy_f1"]))
 with (OUT/"best_last_summary.csv").open("w",newline="") as f:
  w=csv.writer(f);w.writerow(["category","task","checkpoint","mean_buggy_f1","mean_macro_f1"])
  for r in results:
   for kind in ("best","last"):w.writerow([r["category"],r["task"],kind,r[kind]["mean_buggy_f1"],r[kind]["mean_macro_f1"]])
 log("ALL COMPLETE")
if __name__=="__main__":main()
