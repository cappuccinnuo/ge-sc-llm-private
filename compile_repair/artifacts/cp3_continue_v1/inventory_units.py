"""Immutable CP3 compile-unit inventory from verified acquisition manifests."""
import collections,gzip,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from compile_repair.evaluation.survey import solidity_snippet_evidence
B=Path(__file__).resolve().parent
LOCAL=ROOT.parent/"compile-repair-local"/B.name
LOCAL.mkdir(parents=True,exist_ok=False)
(LOCAL/"snippets").mkdir()
units=[]; files_checked=0
def sha(raw): return hashlib.sha256(raw).hexdigest()
def add(row):
 row["unit_id"]="cp3_%05d"%(len(units)+1);units.append(row)
for corpus in ["DAppSCAN","Trace","SOChecker"]:
 manifest=ROOT/"compile_repair/artifacts/cp3_v1/acquisition"/corpus/"manifest.jsonl.gz"
 with gzip.open(manifest,"rt") as f: rows=[json.loads(x) for x in f]
 for r in rows:
  p=Path(r["absolute_path"]);raw=p.read_bytes()
  if sha(raw)!=r["sha256"]: raise ValueError("Acquired input changed: "+str(p))
  files_checked+=1
  if corpus=="SOChecker":
   if p.name!="ours.json":continue
   data=json.loads(raw);records=list(data.values()) if isinstance(data,dict) else data
   assert len(records)==897
   for i,record in enumerate(records):
    source=record["input"].encode("utf8")
    path=LOCAL/"snippets"/("%04d.sol"%i)
    with path.open("xb") as f:f.write(source)
    add({"corpus":"SOChecker","kind":"snippet","path":str(path),"entry_sha256":sha(source),
         "container_path":str(p),"container_sha256":r["sha256"],"input_index":i,
         "language_evidence":solidity_snippet_evidence(source),"project_root":None})
  elif p.suffix==".sol":
   parts=r["path"].split("/")
   if corpus=="DAppSCAN":
    project_relative="/".join(parts[:3]);group="DAppSCAN"
   elif parts[1]=="repo-level":
    project_relative="/".join(parts[:3]);group="Trace_repo"
   else:project_relative=None;group="Trace_"+parts[1].replace("-","_")
   repository_root=p
   for _ in parts:repository_root=repository_root.parent
   project=str(repository_root/project_relative) if project_relative else None
   add({"corpus":group,"kind":"project" if project else "file","path":str(p),
        "entry_sha256":r["sha256"],"project_root":project,
        "repository_commit":r["commit"],"language_evidence":{"is_solidity":True,"basis":".sol corpus entry"}})
recon=json.loads((ROOT/"compile_repair/artifacts/cp0_v2/recon.json").read_text())
for r in recon["inputs"]:
 p=ROOT/r["path"];raw=p.read_bytes()
 if sha(raw)!=r["sha256"]:raise ValueError("MANDO source changed")
 add({"corpus":"MANDO","kind":"file","path":str(p),"entry_sha256":r["sha256"],
      "project_root":None,"language_evidence":{"is_solidity":True,"basis":"frozen MANDO .sol entry"}})
with (B/"unit_inventory.jsonl").open("x") as f:
 for row in units:f.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+"\n")
summary={"unit_counts":dict(collections.Counter(r["corpus"] for r in units)),
 "eligible_counts":dict(collections.Counter(r["corpus"] for r in units if r["language_evidence"]["is_solidity"])),
 "excluded_non_solidity":dict(collections.Counter(r["corpus"] for r in units if not r["language_evidence"]["is_solidity"])),
 "project_counts":{c:len({r["project_root"] for r in units if r["corpus"]==c}) for c in ["DAppSCAN","Trace_repo"]},
 "language_bases":dict(collections.Counter(r["language_evidence"]["basis"] for r in units if r["corpus"]=="SOChecker")),
 "verified_acquired_files":files_checked,"canonical_sochecker_inputs":897,"local_root":str(LOCAL),
 "sampling":"none; this is the complete input inventory","cost_usd":0}
with (B/"unit_inventory_summary.json").open("x") as f:json.dump(summary,f,indent=2);f.write("\n")
print(json.dumps(summary),flush=True)
