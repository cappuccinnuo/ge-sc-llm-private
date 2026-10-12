"""Train existing author and local narrow graph versions, then evaluate best and last.
Codex 2026-10-10. Does not change original graph, annotation or training code.
"""
import csv,hashlib,json,os,re,shlex,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone

REPO=Path("/home/zhao/SmartContract/ge-sc-llm")
RUN=Path(__file__).resolve().parent
PYTHON="/home/zhao/miniconda3/envs/mando/bin/python"
PREVIOUS=REPO/"Test_code/label_pipeline/training_runs/20261010_public_endpoints_v1"
sys.path.insert(0,str(REPO/"scripts/labeling_v2"))
from safe_graph import read_graph
from label_rules import parse_records

def now():return datetime.now(timezone.utc).isoformat()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for block in iter(lambda:f.read(1048576),b""):h.update(block)
 return h.hexdigest()
def save(name,value):
 p=RUN/name;t=p.with_suffix(p.suffix+".tmp")
 t.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n");t.replace(p)

def jobs():
 configs=[
 ("reentrancy","author","experiments/ge-sc-data/source_code/reentrancy/upstream_contractlevel_tok.gpickle","experiments/ge-sc-data/source_code/reentrancy/upstream_linelevel_cfg_cg_tok.gpickle","data/upstream_mando_llm/graph_detection/reentrancy_graph_labels.json"),
 ("reentrancy","narrow","experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_narrow.gpickle","experiments/ge-sc-data/source_code/reentrancy/linelevel_narrow.gpickle","experiments/ge-sc-data/source_code/reentrancy/graph_labels.json"),
 ("access_control","author","scripts/access_control_test/artifacts/author_graph_v1/hcg_author_tok.gpickle",str(RUN/"inputs/access_control_author_linelevel_57.gpickle"),"data/upstream_mando_llm/graph_detection/access_control_graph_labels.json"),
 ("access_control","narrow","scripts/access_control_test/artifacts/dataset_a_source_range_v1/tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle","scripts/access_control_test/artifacts/dataset_a_source_range_v1/linelevel_tokenizer_ids.gpickle","scripts/access_control_test/artifacts/dataset_a_source_range_v1/graph_labels.json")]
 result=[]
 for cat,variant,full,line,label in configs:
  label=REPO/label
  target={d["contract_name"]:int(d["targets"]) for d in json.loads(label.read_text())}
  for task,graph,folds,entry in [("contractlevel",full,5,"graph_classifier.py"),("linelevel",line,10,"node_classifier.py")]:
   graph=REPO/graph
   g=read_graph(graph)
   files={d["source_file"] for _,d in g.nodes(data=True)}
   expected=set(target) if task=="contractlevel" else {f for f,y in target.items() if y}
   assert files==expected,(cat,variant,task,files^expected)
   assert all("token" in d and len(d["token"])==512 for _,d in g.nodes(data=True))
   stats=dict(nodes=len(g),edges=g.number_of_edges(),files=len(files),
    positive_nodes=sum(bool(parse_records(d.get("node_info_vulnerabilities"))) for _,d in g.nodes(data=True)))
   name=cat+"_"+variant+"_"+task
   model=RUN/"models"/name/(cat+"_hgt.pth")
   sources=REPO/"experiments/ge-sc-data/source_code"/cat/"source_files"
   command=[PYTHON,"-u","-B",str(REPO/entry),"--compressed_graph",str(graph),"--bug_type",cat,
    "--dataset",str(sources),"--testset",str(sources),"--node_feature","inside_token",
    "--output_models",str(model),"--log_dir",str(RUN/"tensorboard"/name),
    "--num_epochs","50","--k_folds",str(folds),"--patience","7","--seed","1","--verbose_epochs","--no_progress"]
   if task=="contractlevel":command+=["--label",str(label)]
   else:command+=["--split_by","contract"]
   evaluation=[PYTHON,"-u","-B",str(REPO/"scripts/eval_best_last.py"),"--task","contract" if task=="contractlevel" else "line",
    "--graph",str(graph),"--run_dir",str(model.parent),"--node_feature","inside_token"]
   if task=="contractlevel":evaluation+=["--label",str(label)]
   result.append(dict(name=name,category=cat,variant=variant,task=task,folds=folds,command=command,evaluation_command=evaluation,
     graph=str(graph),graph_sha256=sha(graph),label=str(label),label_sha256=sha(label),stats=stats,
     output_model=str(model),log=str(RUN/"logs"/(name+".log")),evaluation_log=str(RUN/"logs"/(name+"_best_last.log")),status="pending"))
   del g
 return result

def run_process(command,path,env,prefix,job,state,phase):
 with Path(path).open("w",encoding="utf-8",buffering=1) as log:
  log.write("COMMAND: "+" ".join(shlex.quote(x) for x in command)+"\n")
  p=subprocess.Popen(command,cwd=str(REPO),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,bufsize=1)
  job["pid"]=p.pid;job["phase"]=phase;save("run_manifest.json",state)
  for line in p.stdout:
   log.write(line)
   if any(s in line for s in ["Start training fold","restore best epoch","Average ","Traceback","Error:","mean Buggy-F1","Split mode:"]):
    print(prefix+": "+line.rstrip(),flush=True)
  return p.wait()

def summarize(j):
 log=Path(j["log"]).read_text();ev=Path(j["evaluation_log"]).read_text()
 metrics={}
 for kind in ("best","last"):
  match=re.search(kind+r": mean Buggy-F1\s+([0-9.]+)\s+mean Macro-F1\s+([0-9.]+)",ev)
  if not match:raise RuntimeError("Missing evaluation summary "+kind)
  metrics[kind+"_buggy_f1"]=float(match[1]);metrics[kind+"_macro_f1"]=float(match[2])
 for name in ("Buggy","Macro"):
  match=re.search(r"Average "+name+r" F1 score of folds:\s*([0-9.]+)",log)
  assert match and abs(float(match[1])-metrics["best_"+name.lower()+"_f1"])<0.001
 model=Path(j["output_model"]);selections=[]
 for fold in range(j["folds"]):
  p=model.parent/(model.stem+"_fold"+str(fold));s=json.loads((p/"selection.json").read_text())
  assert (p/"best.pt").is_file() and (p/"last.pt").is_file()
  assert not(set(s["train_files"])&set(s["val_files"]))
  prev=PREVIOUS/"models"/(j["category"]+"_"+j["task"])/(model.stem+"_fold"+str(fold))/"selection.json"
  ref=json.loads(prev.read_text())
  assert set(s["train_files"])==set(ref["train_files"]),(j["name"],fold,"training fold differs")
  assert set(s["val_files"])==set(ref["val_files"]),(j["name"],fold,"validation fold differs")
  selections.append(dict(fold=fold,best_epoch=s["best_epoch"],last_epoch=s["last_epoch"],best_buggy_f1=s["best_val_buggy_f1"]*100,best_macro_f1=s["best_val_macro_f1"]*100))
 assert sha(j["graph"])==j["graph_sha256"] and sha(j["label"])==j["label_sha256"]
 result=dict(category=j["category"],variant=j["variant"],task=j["task"],folds=j["folds"],stats=j["stats"],
  graph=j["graph"],training_log=j["log"],evaluation_log=j["evaluation_log"],folds_match_previous_public_run=True,
  wall_seconds=j["wall_seconds"],fold_results=selections,**metrics)
 match=re.search(r"validation nodes whose exact \(code, label\) pair was in their training fold: (\d+)/(\d+) \(([0-9.]+)%\)",log)
 if match:result["exact_code_label_overlap"]=dict(nodes=int(match[1]),total=int(match[2]),percent=float(match[3]))
 return result

def main():
 if (RUN/"run_manifest.json").exists():raise RuntimeError("Run already exists")
 (RUN/"logs").mkdir()
 all_jobs=jobs()
 code_paths=[REPO/"graph_classifier.py",REPO/"node_classifier.py",REPO/"scripts/eval_best_last.py"]+sorted((REPO/"sco_models").rglob("*.py"))
 hashes={str(p.relative_to(REPO)):sha(p) for p in code_paths}
 state=dict(created_by="Codex",started_at=now(),status="running",settings=dict(max_epochs=50,patience=7,seed=1,
   feature="512-wide existing CodeT5p tokenizer IDs",split_unit="contract",
   original_interpretation="Author downloaded CFG+CG structure/labels; token features were encoded locally",
   narrow_interpretation="Existing local narrow end_if graph and historical local labels",
   evaluation="mean validation-fold F1; best by minimum validation loss; last at training stop"),
   code_sha256=hashes,jobs=all_jobs,results=[])
 save("run_manifest.json",state)
 (RUN/"commands.sh").write_text("# Codex: exact commands, existing graphs unmodified\ncd "+shlex.quote(str(REPO))+"\n\n"+
  "\n\n".join(" ".join(shlex.quote(x) for x in j["command"])+"\n"+" ".join(shlex.quote(x) for x in j["evaluation_command"]) for j in all_jobs)+"\n")
 env=dict(os.environ,PYTHONUNBUFFERED="1",PYTHONDONTWRITEBYTECODE="1")
 for j in all_jobs:
  start=time.monotonic();j.update(status="running",started_at=now());save("run_manifest.json",state)
  print("START "+j["name"]+" LOG="+j["log"],flush=True)
  try:
   rc=run_process(j["command"],j["log"],env,j["name"],j,state,"training")
   j["train_exit_code"]=rc
   if rc:raise RuntimeError("Training failed: "+str(rc))
   rc=run_process(j["evaluation_command"],j["evaluation_log"],env,j["name"],j,state,"evaluation")
   j["eval_exit_code"]=rc
   if rc:raise RuntimeError("Evaluation failed: "+str(rc))
   j["wall_seconds"]=round(time.monotonic()-start,2)
   state["results"].append(summarize(j));j["status"]="complete"
   save("summary.json",state["results"])
   with (RUN/"summary.csv").open("w",newline="") as f:
    keys=["category","variant","task","folds","best_buggy_f1","best_macro_f1","last_buggy_f1","last_macro_f1","wall_seconds"]
    w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore");w.writeheader();w.writerows(state["results"])
  except Exception as e:
   j["status"]="failed";j["error"]=repr(e);print("FAILED "+j["name"]+": "+repr(e),flush=True)
  j["ended_at"]=now();save("run_manifest.json",state)
 changed=[p for p,h in hashes.items() if sha(REPO/p)!=h]
 state.update(status="complete" if all(j["status"]=="complete" for j in all_jobs) and not changed else "incomplete",
   ended_at=now(),changed_training_files=changed)
 save("run_manifest.json",state)
 print("FINISHED "+state["status"],flush=True)
 if (RUN/"summary.csv").exists():print((RUN/"summary.csv").read_text(),flush=True)
 return 0 if state["status"]=="complete" else 1
if __name__=="__main__":sys.exit(main())
