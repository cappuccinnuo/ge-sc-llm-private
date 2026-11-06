from pathlib import Path
from collections import defaultdict
import json,csv,hashlib
ROOT=Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
R=ROOT/"scripts/node_sem/artifacts/batch_NB_v1"
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def checked(r):
 assert sha(r["path"])==r["sha256"]
 return Path(r["path"])
out=R/"analysis_supplement";out.mkdir()
groups=defaultdict(lambda:dict(samples=0,saturated=0,models=0))
sources=[]
for parent in [R.parent/"batch_NA_v1/attention",R/"diagnostics"]:
 c=read(parent/"complete.json");assert c["passed"]
 sources.append(ref(parent/"complete.json"))
 for item in c["artifacts"]:
  x=read(checked(item));task,graph,name,fold=x["job_id"].split("__")
  if name not in ["S2","S3","S4","S4g","S4m"]:continue
  assert x["model_unchanged"] and x["optimizer_steps"]==0
  g=groups[(task,name)];g["models"]+=1
  for rel in x["relations"]:
   v=rel["multi_neighbor_max_weight_distribution"];n=v["samples"]
   if n:
    count=n*v["fraction_ge_099"];assert abs(count-round(count))<1e-6
    g["samples"]+=n;g["saturated"]+=int(round(count))
summary=[]
for (task,name),g in sorted(groups.items()):
 assert g["models"]==(10 if task.endswith("_node") else 5)
 summary.append(dict(task=task,name=name,**g,fraction=g["saturated"]/g["samples"] if g["samples"] else None))
(out/"attention_summary.json").write_text(json.dumps(dict(passed=True,sources=sources,summary=summary),indent=2)+"\n")
with (out/"attention_summary.csv").open("w") as f:
 w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
cn={"reentrancy_contract":"重入合约","access_control_contract":"访问控制合约","reentrancy_node":"重入节点","access_control_node":"访问控制节点"}
text="\n\n### 12. 门控结论与首层注意力汇总\n\nS4g没有普遍退化为仅使用CODE：四任务CODE平均门控权重约0.357–0.495，CODE权重≥0.9的观测比例约24.87%–39.33%；CTX和STATIC仍有明显权重。但这没有转化成稳定F1收益，不能把门控数值直接当成有效性证明。\n\n下表仅统计首层、每个canonical relation内入度≥2的目标，给出最大注意力权重≥0.99的“模型×关系×目标×head”观测比例。排除了单邻居必然为1的情况；同一目标可重复出现，不作为独立样本。\n\n|任务|S2|S3|S4|S4g|S4m|\n|---|---:|---:|---:|---:|---:|\n"
for task in cn:
 vals=[next(x["fraction"] for x in summary if x["task"]==task and x["name"]==name) for name in ["S2","S3","S4","S4g","S4m"]]
 text+="|"+cn[task]+"|"+"|".join("{:.4%}".format(x) for x in vals)+"|\n"
text+="\nS2/S4使用N-A已封存注意力摘要（逐项SHA核验），没有重载缺失的N-A权重；S3/S4g/S4m来自本轮90次读取。证据见analysis_supplement/attention_summary.json及CSV。注意力饱和比例不是性能/因果指标，不能据此修改当前模型。\n\n另外独立复核360份history/best/last元数据，全部best等于严格最低inner_val loss所在轮，loss有限、last与日志最后一轮一致；selection_audit.json留证。这里是日志复核，不把它说成当前重载了480份缺失N-A模型。\n"
paths=[ROOT/"scripts/node_sem/NS_P6_REPORT.md",ROOT/"docs/training_changes_2026-10-07.md"]
manifest=[]
for p in paths:
 old=p.read_bytes()
 with p.open("ab") as f:f.write(text.encode("utf8"))
 manifest.append(dict(path=str(p),before_bytes=len(old),before_sha256=hashlib.sha256(old).hexdigest(),after_sha256=sha(p)))
short="\n补充：S4g的CODE平均门控为0.357–0.495，没有普遍退化为CODE-only；多邻居首层注意力比例已按同口径汇总，N-A部分只读历史摘要。360份训练日志再次核实best严格按最低inner_val loss选择，未按外层F1选checkpoint。详细表见NS_P6_REPORT完成节第12项。\n"
for p in [ROOT/"HANDOVER.md",ROOT/"scripts/node_sem/PROGRESS.md"]:
 old=p.read_bytes()
 with p.open("ab") as f:f.write(short.encode("utf8"))
 manifest.append(dict(path=str(p),before_bytes=len(old),before_sha256=hashlib.sha256(old).hexdigest(),after_sha256=sha(p)))
(out/"documentation_append.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(text)
