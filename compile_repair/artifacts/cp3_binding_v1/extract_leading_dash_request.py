import json,hashlib
from pathlib import Path
b=Path("compile_repair/artifacts/cp3_binding_v1");old=b.with_name("cp3_continue_v1")
runs=[Path("/home/zhao/SmartContract/compile-repair-local/cp3_binding_v1")/name for name in ["revalidate_projects_343","segment_00872_31071"]]
items={r["unit_id"]:r for r in map(json.loads,(old/"unit_inventory.jsonl").open())}
affected=[]
for run in runs:
 for line in (run/"classifications.jsonl").open():
  if "unrecognised option" not in line:continue
  row=json.loads(line)
  if not any("unrecognised option" in (f.get("template") or f.get("error_template") or f.get("reason") or "") for f in row["failures"]):continue
  uid=row["unit_id"];item=items[uid];p=run/"units"/uid/"result.json";raw=p.read_bytes();data=json.loads(raw)
  rel=Path(item["path"]).relative_to(item["project_root"]).as_posix();assert rel.startswith("-")
  calls=[a["solc"] for a in data["attempts"] if a.get("solc")]
  affected.append({"unit_id":uid,"corpus":item["corpus"],"entry_path":item["path"],"project_root":item["project_root"],"entry_relative":rel,"entry_sha256":item["entry_sha256"],"result_path":str(p),"result_sha256":hashlib.sha256(raw).hexdigest(),"status":data["status"],"reason":data["reason"],"compiler_calls":len(calls),"observed_versions":[a["version"] for a in data["attempts"] if a.get("solc")],"first_compilation":{k:v for k,v in calls[0].items() if k!="stdout"}})
print("affected",len(affected),flush=True)
assert len(affected)==11
locations=[]
for i,line in enumerate(Path("compile_repair/toolchain/project.py").read_text().splitlines(),1):
 if line.startswith(("def project_command(","def slither_arguments(")):locations.append({"path":"compile_repair/toolchain/project.py","line":i,"definition":line})
req={"schema":"cp3-leading-dash-entry-review-request-v1","date":"2026-11-18","author":"Codex","status":"awaiting_user_decision","finding":"Project entries starting with a hyphen are passed unchanged to compiler and Slither target; solc interprets the entry as an option. This is invocation assembly failure, not a Solidity source error.","affected_units":affected,"failure_summary_sha256":hashlib.sha256((b/"failure_summary.json").read_bytes()).hexdigest(),"current_observed_totals":{"eligible":31071,"success":21150,"remaining_failures":9921,"acceptance":"provisional; CP3 final acceptance blocked by 11 invocation failures"},"code_locations":locations,"proposed_change":{"scope":["compile_repair/toolchain/project.py","compile_repair/tests/test_project.py","compile_repair/tests/fixtures/ hand-written leading-hyphen project","new evidence and mandatory documentation"],"behavior":"Use one shared entry-argument normalizer: prefix ./ only if project.entry starts with -. Both solc argv and Slither target use it. All other target strings, source bytes, version/settings policy, D3 and binding gate remain unchanged.","tests":"Hand-written leading-hyphen entry with existing compilers 0.4.12, 0.4.24, 0.5.17 and 0.8.38; assert matching targets, compiler success, D3 and binding acceptance; existing plain-entry argv unchanged.","revalidation":"Preserve current full batch and summaries. Revalidate exactly these 11 units in a fresh batch under original candidate policy, stop on unexpected outcomes, then replace only those rows in a new summary with explicit provenance. No full-corpus rerun.","no_install_download_llm_or_global_solc_change":True,"cost_usd_limit":0},"approval_basis":"PROMPTS 4.1 requires stopping/reporting when evidence affects the plan and no automatic experimental retry; user requires consultation before plan changes."}
with (b/"leading_dash_review_request.json").open("x") as f:json.dump(req,f,indent=2,ensure_ascii=False);f.write("\n")
print(json.dumps({"written":str(b/"leading_dash_review_request.json"),"units":len(affected),"unit_ids":[r["unit_id"] for r in affected],"relative_example":affected[0]["entry_relative"],"compiler_calls":sum(r["compiler_calls"] for r in affected),"command_keys":list(affected[0]["first_compilation"])},ensure_ascii=False),flush=True)
