"""CP3 diagnostic and duplicate-directive observations; no production repairs."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from compile_repair.toolchain.solc import load_trusted_compilers,compile_file,command,error_first_line,version_tuple
from compile_repair.toolchain.slither import run_slither,check_profile
B=Path(__file__).resolve().parent
F=ROOT/"compile_repair/tests/fixtures/cp3_diagnostics"
out=B/"diagnostics";out.mkdir()
compilers,_,trust=load_trusted_compilers()
versions=sorted((v for v in compilers if (0,4,12)<=version_tuple(v)<(0,9,0)),key=version_tuple)
assert len(versions)==92
sample=["0.4.12","0.4.17","0.4.24","0.4.26","0.5.0","0.5.17","0.6.0","0.6.12","0.7.0","0.7.6","0.8.0","0.8.38"]
rows=[];profile=check_profile("production")
with (B/"diagnostic_invocations.jsonl").open("x",encoding="utf8") as journal:
 def save(row):
  rows.append(row);journal.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n");journal.flush()
 for v in versions:
  names=["missing_semicolon","duplicate_contract","duplicate_license","duplicate_pragma"]
  if v in sample:names+=["missing_base","undeclared","type_mismatch","duplicate_function","duplicate_event","conflicting_pragma","duplicate_abicoder","docstring","syntax","truncated","parser_other","package_import","relative_import","warning","stack_deep"]
  for name in names:
   p=F/(name+".sol");result=compile_file(p,compilers[v]);d=asdict(result)
   (out/(v+"_"+name+".stderr")).write_text(result.stderr,encoding="utf8")
   save(dict(kind="combined_json",fixture=name,**d))
   if result.timed_out:raise RuntimeError("Unexpected small-fixture compiler timeout")
  if v in sample:
   for name in ("missing_semicolon","missing_base","undeclared","type_mismatch","duplicate_contract","docstring","syntax"):
    p=F/(name+".sol");input_data={"language":"Solidity","sources":{p.name:{"content":p.read_text()}},"settings":{"outputSelection":{"*":{"":["ast"]}}}}
    raw=json.dumps(input_data).encode();argv=[compilers[v].path,"--standard-json"];t=time.monotonic()
    run=subprocess.run(argv,input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=str(F),timeout=30)
    (out/(v+"_"+name+".standard.json")).write_bytes(run.stdout)
    errors=json.loads(run.stdout.decode()).get("errors",[])
    save(dict(kind="standard_json_diagnostic_only",fixture=name,version=v,compiler_sha256=compilers[v].sha256,command=argv,cwd=str(F),input_sha256=hashlib.sha256(raw).hexdigest(),returncode=run.returncode,errors=errors,stdout_sha256=hashlib.sha256(run.stdout).hexdigest(),stderr=run.stderr.decode(errors="replace"),elapsed_seconds=time.monotonic()-t,cost_usd=0))
 print(json.dumps({"diagnostics":len(rows),"versions":len(versions),"phase":"tuple_call"}),flush=True)
 for v in ("0.4.12","0.4.24","0.4.26"):
  for name in ("tuple_call","tuple_call_equivalent"):
   compiled=compile_file(F/(name+".sol"),compilers[v]);save(dict(kind="tuple_compile",fixture=name,**asdict(compiled)))
   analysis=run_slither(compiled,profile="production") if compiled.returncode==0 else None
   if analysis is not None:save(dict(kind="tuple_slither",fixture=name,**{k:x for k,x in analysis.items() if k not in ("graph","nodes")}))
   expected=(name=="tuple_call_equivalent")
   passed=(compiled.returncode==0 and analysis["d3"]) if expected else (compiled.returncode!=0 if v=="0.4.12" else compiled.returncode==0 and not analysis["d3"] and analysis.get("exception_type")=="AssertionError")
   if not passed:raise RuntimeError("Tuple-call premise mismatch: "+v+" "+name)
result={"passed":True,"combined_json_calls":sum(r["kind"]=="combined_json" for r in rows),"standard_json_diagnostic_calls":sum(r["kind"]=="standard_json_diagnostic_only" for r in rows),"tuple_premise_combinations":6,"compiler_versions":versions,"profile":profile,"production_code_modified":False,"source_repairs":0,"cost_usd":0}
with (B/"diagnostic_probe_acceptance.json").open("x") as f:json.dump(result,f,indent=2);f.write("\n")
print(json.dumps(result),flush=True)
