"""CP3 bounded segments of one complete deterministic schedule; common repair_unit only."""
import argparse,collections,hashlib,json,random,sys,time,subprocess
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from compile_repair.core.store import ArtifactStore,emit,sha256
from compile_repair.core.model import SourceFile,CompilationUnit
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.project import ProjectIndex,resolve_project
from compile_repair.toolchain.solc import load_trusted_compilers
from compile_repair.toolchain.slither import check_profile
from compile_repair.rules.environment import pragma_interval,mando_known_version
from compile_repair.evaluation.report import classify_record,aggregate_failures
from scripts.DFG.frontend import parse
B=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument("--offset",type=int,default=0);p.add_argument("--limit",type=int,required=True)
p.add_argument("--name",required=True);args=p.parse_args()
inventory=[json.loads(x) for x in (B/"unit_inventory.jsonl").read_text().splitlines()]
groups=collections.defaultdict(list)
for row in inventory:
 if row["language_evidence"]["is_solidity"]:groups[row["corpus"]].append(row)
rng=random.Random(0)
for group in sorted(groups):
 groups[group].sort(key=lambda r:(r["entry_sha256"],r["unit_id"]));rng.shuffle(groups[group])
order=[]
while any(groups.values()):
 for group in sorted(groups):
  if groups[group]:order.append(groups[group].pop())
selection=order[args.offset:args.offset+args.limit]
LOCAL=Path(json.loads((B/"unit_inventory_summary.json").read_text())["local_root"])
store=ArtifactStore(LOCAL/args.name)
start=time.monotonic();compilers,frozen,trust=load_trusted_compilers()
profile=check_profile("production")
store.write_json("trust.json",trust)
implementation={str(p.relative_to(ROOT)):sha256(p) for p in (ROOT/"compile_repair").rglob("*.py")
 if not {"tests","artifacts"} & set(p.relative_to(ROOT/"compile_repair").parts)}
store.write_json("schedule.json",{"offset":args.offset,"requested_limit":args.limit,"scheduled":len(selection),
 "eligible_population":len(order),"order_sha256":hashlib.sha256("\n".join(r["unit_id"] for r in order).encode()).hexdigest(),
 "unit_ids":[r["unit_id"] for r in selection],"population_sampling":"none; bounded prefix/continuation of full schedule",
 "seed":0,"order":"per-corpus SHA256 sort, one Random(0) shuffle in sorted corpus order, round-robin pop"})
cache={}; rows=[]; parse_cache={}; language_counts=collections.Counter(); issues=[]
summary={"status":"running","cost_usd":0,"llm_calls":0}
with store.journal("invocations.jsonl") as journal,store.journal("manifest.jsonl") as manifest,store.journal("classifications.jsonl") as classes:
 try:
  for number,item in enumerate(selection,1):
   begun=time.monotonic();path=Path(item["path"]);raw=path.read_bytes()
   assert hashlib.sha256(raw).hexdigest()==item["entry_sha256"],item["unit_id"]
   project=None
   if item["project_root"]:
    root=item["project_root"]
    if root not in cache:cache[root]=ProjectIndex(root)
    project=resolve_project(root,path,index=cache[root])
    sources=project.files
   else:sources=(SourceFile(str(path),item["entry_sha256"],raw,item["kind"]),)
   old_failed=False;old_errors=[]
   for source in sources:
    if source.sha256 not in parse_cache:
     try:parse(source.content.decode("utf8"));parse_cache[source.sha256]=None
     except Exception as exc:parse_cache[source.sha256]=type(exc).__name__
    if parse_cache[source.sha256]:
     old_failed=True;old_errors.append({"source_sha256":source.sha256,"exception_type":parse_cache[source.sha256]})
   try:pragma_interval([s.content for s in sources]);new_read=True;new_error=None
   except Exception as exc:new_read=False;new_error=type(exc).__name__+": "+str(exc)
   known,metadata=mando_known_version(raw,frozen) if item["corpus"]=="MANDO" else (None,[])
   unit=CompilationUnit(item["unit_id"],sources,known,"mando" if item["corpus"]=="MANDO" else None)
   store.write_json("units/"+unit.unit_id+"/input_record.json",dict(item,known_version=known,metadata=metadata))
   record=repair_unit(unit,compilers,store,journal,project=project)
   data=asdict(record);emit(manifest,data)
   classification={"unit_id":unit.unit_id,"corpus":item["corpus"],"entry_sha256":item["entry_sha256"],
     "status":record.status,"reason":record.reason,"selected_version":record.selected_version,
     "failures":classify_record(data),"closure_files":len(sources),
     "old_parse_failed":old_failed,"old_parse_errors":old_errors,"new_interval_read":new_read,
     "new_interval_error":new_error,"old_parse_failed_new_read_succeeded":old_failed and new_read,
     "elapsed_seconds":time.monotonic()-begun,"compiler_calls":sum("solc" in a for a in record.attempts),
     "slither_calls":sum(a.get("slither") is not None for a in record.attempts)}
   rows.append(classification);emit(classes,classification)
   print(json.dumps({k:classification[k] for k in ("unit_id","corpus","status","reason","elapsed_seconds","compiler_calls")}),flush=True)
  summary["status"]="complete_segment"
 except Exception as exc:
  summary.update(status="stopped",exception_type=type(exc).__name__,detail=str(exc),unit_id=item["unit_id"])
  print(json.dumps(summary),flush=True)
summary.update(completed_units=len(rows),elapsed_seconds=time.monotonic()-start,
 compiler_calls=sum(r["compiler_calls"] for r in rows),slither_calls=sum(r["slither_calls"] for r in rows))
taxonomy=json.loads((ROOT/"compile_repair/artifacts/cp3_v1/taxonomy.json").read_text())
store.write_json("failure_summary.json",aggregate_failures(rows,[c["category"] for c in taxonomy["categories"]]))
store.write_json("summary.json",summary)
store.seal(dict(profile,compilers={v:asdict(c) for v,c in compilers.items()}),
 subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT),text=True).strip(),implementation)
print(json.dumps(summary),flush=True)
sys.exit(0 if summary["status"]=="complete_segment" else 2)
