"""Stage F read-only frozen input catalogue and artifact utilities."""
import csv, hashlib, json, pickle, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
ORIGINAL=Path("/home/zhao/SmartContract/ge-sc-llm")
OUT=Path(__file__).resolve().parent
PLAN=ORIGINAL/"scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c/plan.json"
D1=ROOT/"scripts/DFG/experiments/audit/ddg_v11_correctness/D1_PROVENANCE.json"
def sha(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def dump(path,data):
 with Path(path).open("x",encoding="utf8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
def csv_out(path,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with Path(path).open("x",newline="",encoding="utf8") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})
def catalogue():
 plan=read(PLAN);prov=read(D1);inputs={str(PLAN):sha(PLAN),str(D1):sha(D1)}
 seal=read(PLAN.with_name("plan.seal.json"));assert seal["sha256"]==sha(PLAN)
 jobs=plan["jobs"];cohorts={}
 for cohort in ("reentrancy_author","access_control_author"):
  cj=[j for j in jobs if j["cohort"]==cohort]
  paths={j["prepared"] for j in cj};assert len(paths)==1
  prep=Path(next(iter(paths)));m=read(prep/"manifest.json")
  inputs[str(prep/"manifest.json")]=sha(prep/"manifest.json")
  taskfiles={};graphs={}
  for task in ("contract","node"):
   js=[j for j in cj if j["task"]==task];assert len(js)==(5 if task=="contract" else 10)
   splitpaths={j["splits"] for j in js};assert len(splitpaths)==1
   sp=Path(next(iter(splitpaths)));split=read(sp);inputs[str(sp)]=sha(sp)
   assert split["prepared_manifest_sha256"]==sha(prep/"manifest.json")
   spec=prov["graphs"][cohort+"_"+task];assert sha(spec["path"])==spec["sha256"]
   inputs[spec["path"]]=spec["sha256"]
   with open(spec["path"],"rb") as f:g=pickle.load(f)
   names={d["source_file"] for _,d in g.nodes(data=True)}
   assert names==set(split["files"])
   taskfiles[task]=sorted(names);graphs[task]=g
  assert set(taskfiles["node"])<=set(taskfiles["contract"])==set(m["sources"])
  for n,s in m["sources"].items():assert sha(s["path"])==s["sha256"];inputs[s["path"]]=s["sha256"]
  cohorts[cohort]={"manifest":m,"files":taskfiles,"graphs":graphs,"prepared":str(prep)}
 return cohorts,inputs
def check_inputs(inputs):
 for p,h in inputs.items():assert sha(p)==h,("input drift",p)
