"""Verify protected pre-H1 assets; only four authorized Markdown append operations may differ."""
from pathlib import Path
import json,hashlib,subprocess,time
P=Path(__file__).resolve().parent
def sha(path,limit=None):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  if limit is not None:h.update(f.read(limit))
  else:
   for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
 return h.hexdigest()
def main():
 before=json.loads((P/"protected_before.json").read_text());bad=[];docs=[];same=0
 docpaths={r["path"] for r in json.loads((P/"documentation_phase1.json").read_text())}
 for path,record in before["files"].items():
  f=Path(path)
  if not f.exists():bad.append({"path":path,"problem":"missing"});continue
  current=sha(f)
  if path in docpaths:
   valid=f.stat().st_size>=record["bytes"] and sha(f,record["bytes"])==record["sha256"]
   docs.append({"path":path,"original_prefix_preserved":valid,"sha256":current,"bytes":f.stat().st_size})
   if not valid:bad.append({"path":path,"problem":"original_document_prefix_changed"})
  elif current!=record["sha256"]:bad.append({"path":path,"problem":"hash_changed"})
  else:same+=1
 trees=[]
 for root in before["complete_trees"]:
  old={p for p in before["files"] if p.startswith(root+"/")}
  now={str(f) for f in Path(root).rglob("*") if f.is_file()}
  trees.append({"path":root,"before":len(old),"after":len(now),"added":sorted(now-old),"removed":sorted(old-now)})
  if now!=old:bad.append({"path":root,"problem":"tree_membership_changed"})
 heads={};status={}
 for root,head in before["heads"].items():
  current=subprocess.check_output(["git","-C",root,"rev-parse","HEAD"],text=True).strip();heads[root]=current
  if current!=head:bad.append({"path":root,"problem":"HEAD_changed"})
  status[root]=subprocess.check_output(["git","-C",root,"status","--short","--untracked-files=normal"],text=True)
 result=dict(status="passed" if not bad else "failed",files_checked=len(before["files"]),unchanged_non_document_files=same,
   authorized_append_only_documents=docs,complete_trees=trees,heads=heads,git_status_after=status,problems=bad)
 (P/"protected_after.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
 print(json.dumps(result,indent=2)[:14000])
 if bad:raise SystemExit(1)
if __name__=="__main__":main()
