"""CP3 codegen premise probes; settings below are observations, not repair rules."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT))
from compile_repair.toolchain.solc import load_trusted_compilers,command,verify_binary
from compile_repair.toolchain.slither import check_profile,node_facts,contract_coverage
from crytic_compile import CryticCompile
from slither import Slither
B=Path(__file__).resolve().parent
F=ROOT/"compile_repair/tests/fixtures/cp3_diagnostics/stack_deep.sol"
cs=load_trusted_compilers()[0]; profile=check_profile("production")
out=B/"codegen"; out.mkdir()
rows=[]
with (B/"codegen_invocations.jsonl").open("x",encoding="utf8") as journal:
 def save(row):
  rows.append(row); journal.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n"); journal.flush()
 for v in ["0.4.26","0.5.17","0.6.12","0.7.6","0.8.38"]:
  c=cs[v]; verify_binary(c)
  options=[("ast_only",["--combined-json","ast" if v=="0.8.38" else "ast,compact-format"]),
           ("optimized",command(F,c)[2:]+["--optimize"])]
  if v=="0.8.38":
   options.extend([("via_ir",command(F,c)[2:]+["--via-ir"]),
                   ("via_ir_optimized",command(F,c)[2:]+["--via-ir","--optimize"])])
  for label,tail in options:
   argv=[c.path,str(F)]+tail; start=time.monotonic()
   r=subprocess.run(argv,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
   output=out/(v+"_"+label+".json");output.write_bytes(r.stdout)
   (out/(v+"_"+label+".stderr")).write_bytes(r.stderr)
   base=dict(fixture=str(F.relative_to(ROOT)),source_sha256=hashlib.sha256(F.read_bytes()).hexdigest(),version=v,
    compiler_path=c.path,compiler_sha256=c.sha256,variant=label,cost_usd=0)
   save(dict(base,kind="solc",command=argv,cwd=str(ROOT),returncode=r.returncode,stderr=r.stderr.decode(errors="replace"),
             stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),elapsed_seconds=time.monotonic()-start))
   if r.returncode!=0: continue
   kwargs={"solc":c.path,"solc_disable_warnings":True}
   if label=="ast_only":
    target=str(output); kwargs["solc_ast"]=True
   else:
    target=str(F); kwargs["solc_args"]=" ".join(x for x in tail if x in ("--via-ir","--optimize"))
   start=time.monotonic(); analysis=dict(base,kind="slither",**profile,command={"target":target,"kwargs":kwargs},
        api_subprocess_returncodes_observed=False,preceding_observed_solc_returncode=0,constructed=False,d3=False)
   try:
    crytic=CryticCompile(target,**kwargs)
    analysis["platform"]=crytic.platform.NAME
    s=Slither(crytic,**kwargs);analysis["constructed"]=True
    facts=node_facts(s,[F]); coverage=contract_coverage(s,[F])
    analysis.update(d3_a=facts["mapping_complete"],d3_b=coverage["complete"],
                    d3=facts["mapping_complete"] and coverage["complete"],node_counts=facts["counts"],coverage=coverage)
   except Exception as e:
    analysis.update(exception_type=type(e).__name__,detail=str(e))
   analysis["elapsed_seconds"]=time.monotonic()-start; save(analysis)
  verify_binary(c)
summary={"status":"observed","compiler_calls":sum(r["kind"]=="solc" for r in rows),
 "slither_calls":sum(r["kind"]=="slither" for r in rows),"observations":[{k:r.get(k) for k in
 ("kind","version","variant","returncode","constructed","d3","exception_type")} for r in rows],
 "production_settings_whitelist_changed":False,"custom_ast_adapter_implemented":False,
 "scope":"Native installed CryticCompile/Slither constructors only. Failure does not prove an AST adapter impossible.",
 "source_sha256":hashlib.sha256(F.read_bytes()).hexdigest(),"cost_usd":0}
(B/"codegen_probe_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary),flush=True)
