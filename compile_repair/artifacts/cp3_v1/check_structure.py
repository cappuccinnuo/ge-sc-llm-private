"""Reproduce historical structure counts only; never import frozen evidence code."""
import collections, hashlib, json, os, re, time
from pathlib import Path
B=Path("compile_repair/artifacts/cp3_v1")
request=json.loads(Path("compile_repair/artifacts/cp3_preflight_v1/authorization_request.json").read_text())
receipt=json.loads((B/"taxonomy_initial_receipt.json").read_text())
assert hashlib.sha256((B/"taxonomy.json").read_bytes()).hexdigest()==receipt["taxonomy_sha256"]
roots={x["name"]:Path(x["destination"]) for x in request["corpora"]}
start=time.time()
# The regexes below reproduce cr_pre_v2's text-only counting, not CP3 version selection.
IMPORT=re.compile(r'^\s*import\s+[^;]*?["\x27]([^"\x27]+)["\x27]',re.M)
PRAGMA=re.compile(r"pragma\s+solidity\s+([^;]*);")
FIRST=re.compile(r"(\d+)\.(\d+)\.(\d+)")
CFG={"hardhat.config.js","hardhat.config.ts","truffle-config.js","truffle.js","foundry.toml","package.json","remappings.txt","brownie-config.yaml"}
counts=collections.Counter();minors=collections.Counter();imports=collections.Counter();projects=[]
dapp=roots["DAppSCAN"]/"DAppSCAN-source/contracts"
for project in sorted(p for p in dapp.iterdir() if p.is_dir()):
 sols=[];configs=set();has_node=False
 for parent,dirs,names in os.walk(str(project)):
  if "node_modules" in Path(parent).parts:
   has_node=True;continue
  for n in names:
   if n.endswith(".sol"):sols.append(Path(parent)/n)
   if n in CFG:configs.add(n)
 nimp=unresolved=0
 for p in sols:
  text=p.read_text(encoding="utf8",errors="ignore")
  pragmas=PRAGMA.findall(text)
  m=FIRST.search(pragmas[0]) if pragmas else None
  minors[(".".join(m.groups()[:2]) if m else "unparsed") if pragmas else "none"]+=1
  for name in IMPORT.findall(text):
   nimp+=1
   if name.startswith("."):
    target=Path(os.path.normpath(str(p.parent/name)))
    if target.exists():imports["relative_found"]+=1
    else:imports["relative_missing"]+=1;unresolved+=1
   else:
    package="/".join(name.split("/")[:2]) if name.startswith("@") else name.split("/")[0]
    imports["package:"+package if package.startswith("@") or package in ("openzeppelin-solidity","zeppelin-solidity") else "bare_other"]+=1
    unresolved+=1
 counts["projects"]+=1;counts["sol_files"]+=len(sols);counts["projects_with_imports"]+=bool(nimp)
 counts["projects_with_node_modules_dir"]+=has_node;counts["projects_without_any_cfg"]+=not configs
 for config in configs:counts["cfg:"+config]+=1
 projects.append(dict(project=project.name,sol=len(sols),imports=nimp,unresolved_imports_static=unresolved,configs=sorted(configs),node_modules=has_node))
counts["projects_with_unresolved_static_imports"]=sum(x["unresolved_imports_static"]>0 for x in projects)
reference_path=Path("compile_repair/artifacts/cr_pre_v2/dappscan_stats.json")
reference=json.loads(reference_path.read_text())
observed={"summary":dict(counts),"pragma_minor_of_first_version":dict(minors),"import_kinds_top":dict(imports.most_common(25)),"projects":projects}
checks={k:observed[k]==reference[k] for k in reference}
with (B/"dappscan_structure.json").open("x",encoding="utf8") as f:json.dump(observed,f,ensure_ascii=False,indent=2);f.write("\n")
dapp_result={"passed":all(checks.values()),"checks":checks,"summary":dict(counts),"reference_sha256":hashlib.sha256(reference_path.read_bytes()).hexdigest(),"method":"historical regex-only structure comparison; not CP3 interval statistics"}
# Only input values participate; keep row multiplicity and original order.
soc={}; sequences={}
for p in sorted((roots["SOChecker"]/"evaluation/RQ1").glob("*.json")):
 value=json.loads(p.read_bytes())
 records=list(value.values()) if isinstance(value,dict) else value
 if not isinstance(records,list) or not all(isinstance(r,dict) and isinstance(r.get("input"),str) for r in records):
  raise ValueError("Unexpected SOChecker record structure: "+p.name)
 seq=[hashlib.sha256(r["input"].encode("utf8")).hexdigest() for r in records]
 sequences[p.name]=seq
 soc[p.name]={"input_rows":len(seq),"unique_inputs":len(set(seq)),"historical_contract_or_function":sum("contract " in r["input"] or "function " in r["input"] for r in records),"input_order_sha256":hashlib.sha256("\n".join(seq).encode("ascii")).hexdigest()}
ours=sequences["ours.json"];base=collections.Counter(ours)
for name,seq in sequences.items():
 c=collections.Counter(seq)
 soc[name].update(input_set_equal=set(seq)==set(ours),input_multiset_equal=c==base,input_order_equal=seq==ours,only_this_multiset=dict(c-base),only_ours_multiset=dict(base-c))
soc_result={"passed":len(ours)==897 and soc["ours.json"]["historical_contract_or_function"]==656 and all(x["input_multiset_equal"] for x in soc.values()),"files":soc,"classification_input":"ours.json; no merging or deduplication"}
trace=roots["Trace"]/"datasets"
trace_result={"on_chain_sol":len(list((trace/"on-chain").rglob("*.sol"))),"repo_level_projects":len([p for p in (trace/"repo-level").iterdir() if p.is_dir()]),"repo_level_sol":len(list((trace/"repo-level").rglob("*.sol"))),"cves_sol":len(list((trace/"CVEs").rglob("*.sol")))}
trace_result["passed"]=trace_result=={"on_chain_sol":5000,"repo_level_projects":83,"repo_level_sol":3092,"cves_sol":15}
result={"taxonomy_precedes_statistics_sha256":receipt["taxonomy_sha256"],"DAppSCAN":dapp_result,"SOChecker":soc_result,"Trace":trace_result,"elapsed_seconds":time.time()-start,"passed":all(x["passed"] for x in (dapp_result,soc_result,trace_result)),"scope":"read-only content structure check; no compiling, no source changes"}
with (B/"structure_acceptance.json").open("x",encoding="utf8") as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")
print(json.dumps({"passed":result["passed"],"DAppSCAN":dapp_result,"SOChecker":{k:{a:b for a,b in v.items() if not a.startswith("only_")} for k,v in soc.items()},"Trace":trace_result},ensure_ascii=False))
if not result["passed"]:raise SystemExit(2)
