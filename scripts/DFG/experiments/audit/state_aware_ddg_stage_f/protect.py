"""Explicit complete snapshot scopes for Stage F; excludes only new Stage F output."""
from pathlib import Path
import subprocess,json,sys
from common import ROOT,ORIGINAL,OUT,sha,dump,read
def initial():
 paths=set();trees=[]
 previous=ROOT/"scripts/DFG/experiments/audit/state_aware_ddg_prototype_v1/protected_before.json"
 paths.update(Path(p) for p in read(previous)["files"])
 for r in (ROOT,ORIGINAL):
  tracked=subprocess.check_output(["git","ls-files","-z"],cwd=str(r)).decode().split("\0")
  paths.update(r/p for p in tracked if p)
 for r,rel in [(ORIGINAL,"scripts/DFG/experiments/artifacts"),(ORIGINAL,"scripts/DFG/experiments/audit"),
               (ROOT,"scripts/DFG/experiments/audit/ddg_v11_correctness"),(ROOT,"scripts/DFG/experiments/audit/state_aware_ddg_prototype_v1"),
               (ROOT,"scripts/DFG/state")]:
  p=r/rel;trees.append(str(p));paths.update(q for q in p.rglob("*") if q.is_file() and "__pycache__" not in q.parts)
 heads={str(r):subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(r)).decode().strip() for r in (ROOT,ORIGINAL)}
 for kind,r in (("original",ORIGINAL),("worktree",ROOT)):
  for rel in ("HANDOVER.md","docs/training_changes_2026-10-07.md"):
   with (OUT/(kind+"_"+Path(rel).name+".before")).open("xb") as f:f.write((r/rel).read_bytes())
 dump(OUT/"protected_before.json",{"heads":heads,"complete_trees":trees,"files":{str(p):{"sha256":sha(p),"bytes":p.stat().st_size} for p in sorted(paths)}})
 print("protected",len(paths),flush=True)
if __name__=="__main__":initial()
