"""Seal the approved work and provisional full observations; no CP3 completion claim."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];B=Path(__file__).resolve().parent;OLD=B.with_name("cp3_continue_v1")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(name,value):
 with (B/name).open("x",encoding="utf8") as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write("\n")
def git(*a):return subprocess.check_output(["git"]+list(a),cwd=str(ROOT)).decode().strip()
assert git("branch","--show-current")=="compile-repair"
assert git("rev-parse","HEAD")=="dc6c5fb44041e1023daef1bfd7d9760f534c7f0a"
assert not git("diff","--cached","--name-only")
assert json.loads((B/"frozen_audit.json").read_text())["passed"]
assert json.loads((B/"whitespace_review_v2.json").read_text())["passed"]
docs=json.loads((B/"doc_check_v3.json").read_text());assert docs["passed"]
for p,h in docs["document_sha256"].items():assert sha(ROOT/p)==h,p
base=json.loads((B/"baseline.json").read_text())
allowed={"compile_repair/toolchain/slither.py","compile_repair/pipeline.py","compile_repair/evaluation/report.py","compile_repair/tests/test_project.py","compile_repair/docs/DECISIONS.md","compile_repair/docs/HANDOVER.md","compile_repair/docs/CHANGE_LOG.md","compile_repair/PROGRESS.md","compile_repair/CP3_REPORT.md"}
for p,v in base["files"].items():
 if p not in allowed:assert sha(ROOT/p)==v["sha256"],p
assert sha(OLD/"working_inventory.json")==base["previous_working_inventory_sha256"]
for p in (B/"before").rglob("*"):
 if p.is_file():
  rel="compile_repair/"+p.relative_to(B/"before").as_posix()
  assert sha(p)==base["files"][rel]["sha256"],rel
for rel in ["docs/HANDOVER.md","docs/DECISIONS.md","docs/CHANGE_LOG.md","PROGRESS.md","CP3_REPORT.md"]:
 old=(B/"before"/rel).read_bytes();now=(ROOT/"compile_repair"/rel).read_bytes()
 marker=b"## 6. " if rel.endswith("HANDOVER.md") else b"## 2. " if rel.endswith("DECISIONS.md") else None
 assert (now[now.index(marker):].startswith(old[old.index(marker):]) if marker else now.startswith(old)),rel
provenance=json.loads((B/"result_provenance.json").read_text())
for run in provenance["run_inventory"]:
 for p,h in run["implementation_sha256"].items():assert sha(ROOT/p)==h,p
files={p.relative_to(B).as_posix():{"sha256":sha(p),"bytes":p.stat().st_size} for p in sorted(B.rglob("*")) if p.is_file()}
seal={"schema":"cp3-binding-checkpoint-evidence-v1","status":"awaiting_leading_dash_entry_decision","cp3_complete":False,"current_tests_and_protection_checks_passed":True,"all_cp3_acceptance_passed":False,"pending":"11 leading-hyphen project entries are mistaken for compiler options; correction/revalidation awaits approval","files":files,"latest_document_check":"doc_check_v3.json","whitespace_check":"whitespace_review_v2.json","raw_corpus_storage":"outside repository; result_provenance binds selected results and both new run seals","code_commit_at_start":git("rev-parse","HEAD"),"commit_performed_at_seal_time":False,"push_performed":False,"cost_usd":0}
put("evidence_seal.json",seal)
prior=json.loads((OLD/"working_inventory.json").read_text())
names=set(prior["files"])|{(OLD/"working_inventory.json").relative_to(ROOT).as_posix()}
names.update(p.relative_to(ROOT).as_posix() for p in B.rglob("*") if p.is_file())
assert all(p.startswith("compile_repair/") for p in names)
tracked_changes=set(git("diff","--name-only","HEAD").splitlines())
assert tracked_changes <= names
inventory={"schema":"cp3-binding-checkpoint-delivery-v1","self":(B/"delivery_inventory.json").relative_to(ROOT).as_posix(),"status":"awaiting_leading_dash_entry_decision","cp3_complete":False,"files":{p:{"sha256":sha(ROOT/p),"bytes":(ROOT/p).stat().st_size} for p in sorted(names)},"file_count_including_self":len(names)+1,"evidence_seal_sha256":sha(B/"evidence_seal.json"),"latest_document_check":"doc_check_v3.json","staging_policy":"Exact listed paths and this inventory only; historical untracked data and external source/graph files excluded. Index and commit receipts stored outside sealed batch."}
put("delivery_inventory.json",inventory)
print(json.dumps({"sealed_members":len(files),"delivery_files_including_inventory":len(names)+1,"evidence_seal_sha256":sha(B/"evidence_seal.json"),"delivery_inventory_sha256":sha(B/"delivery_inventory.json"),"cp3_complete":False}))
