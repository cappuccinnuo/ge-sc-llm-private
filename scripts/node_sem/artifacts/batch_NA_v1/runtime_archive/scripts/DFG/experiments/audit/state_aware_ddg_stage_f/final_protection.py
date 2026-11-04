"""Verify all old assets and authorized append-only documents at Stage F delivery."""
from common import ROOT,ORIGINAL,OUT,sha,read,dump
from pathlib import Path
import subprocess
def main():
 before=read(OUT/"protected_before.json");updates=read(OUT/"documentation_update.json")
 allowed={r["path"]:r for r in updates};issues=[];changed=[];unchanged=0;prefix=[]
 for name,record in before["files"].items():
  p=Path(name)
  if not p.is_file():issues.append({"missing":name});continue
  current=sha(p)
  if current==record["sha256"]:unchanged+=1;continue
  changed.append(name)
  if name not in allowed:issues.append({"unexpected_change":name});continue
  kind="worktree" if str(ROOT) in name else "original"
  backup=OUT/(kind+"_"+p.name+".before")
  ok=p.read_bytes().startswith(backup.read_bytes()) and sha(backup)==record["sha256"] and current==allowed[name]["after_sha256"]
  prefix.append({"path":name,"unchanged_old_prefix":ok})
  if not ok:issues.append({"document_prefix_or_hash_mismatch":name})
 all_new=[]
 for tree in before["complete_trees"]:
  for p in Path(tree).rglob("*"):
   if p.is_file() and "__pycache__" not in p.parts and str(p) not in before["files"]:
    all_new.append(str(p))
    try:p.relative_to(ROOT/"scripts/DFG/state/stage_f")
    except ValueError:issues.append({"unexpected_new_in_protected_tree":str(p)})
 git=[]
 for root in (ROOT,ORIGINAL):
  head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(root)).decode().strip()
  diff=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(root)).decode().splitlines()
  check=subprocess.run(["git","diff","--check"],cwd=str(root),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
  if head!=before["heads"][str(root)]:issues.append({"head_changed":str(root)})
  if set(diff)!={"HANDOVER.md","docs/training_changes_2026-10-07.md"}:issues.append({"unexpected_tracked_diff":diff,"root":str(root)})
  if check.returncode:issues.append({"git_diff_check_failed":check.stdout})
  git.append({"root":str(root),"head":head,"tracked_diff":diff,"diff_check_exit":check.returncode,"diff_check_output":check.stdout})
 assert len(prefix)==4
 result={"status":"passed" if not issues else "requires_review","old_files_checked":len(before["files"]),"old_files_unchanged":unchanged,
 "authorized_document_appends":prefix,"new_files_in_protected_trees":all_new,"allowed_new_subtree":str(ROOT/"scripts/DFG/state/stage_f"),
 "git":git,"issues":issues,"no_training_or_old_artifact_mutation":not issues}
 dump(OUT/"protected_after.json",result);print(__import__("json").dumps(result))
 assert not issues,issues
if __name__=="__main__":main()
