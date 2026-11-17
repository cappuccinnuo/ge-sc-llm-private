"""Seal only CP3's authorized acquisition checkpoint; never push or alter corpora."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    with path.open("x",encoding="utf8") as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2);f.write("\n")
baseline=json.loads((OUT/"baseline.json").read_text())
assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip()==baseline["head"]
assert not subprocess.check_output(["git","diff","--cached","--name-only"],cwd=str(ROOT)).strip()
subprocess.run(["git","diff","--check"],cwd=str(ROOT),check=True)
doc=json.loads((OUT/"doc_check_v2_invocation.json").read_text())
assert doc["all_passed"] and doc["rows"]==6
for p,h in doc["document_sha256"].items():assert sha(ROOT/p)==h,p
assert json.loads((OUT/"test_acceptance.json").read_text())["passed"]
audit=json.loads((OUT/"frozen_audit.json").read_text())
assert audit["passed"] and audit["production_file_count"]==14
structure=json.loads((OUT/"structure_acceptance.json").read_text())
assert not structure["passed"] and structure["DAppSCAN"]["passed"] and structure["Trace"]["passed"]
assert json.loads((OUT/"structure_review_request.json").read_text())["status"]=="pending_user_decision"
assert sha(OUT/"authorization.json")=="f42f045ba9c235674cc3fea3a4b42a7d28945daaf56b1b43ba9ae8aef869a87a"
# Final documentation edits must still preserve all old history.
for p in baseline["docs"]:
    old=subprocess.check_output(["git","show",baseline["head"]+":"+p],cwd=str(ROOT))
    now=(ROOT/p).read_bytes()
    if p.endswith("HANDOVER.md"):
        marker=b"## 6. ";assert now[now.index(marker):].startswith(old[old.index(marker):])
    elif p.endswith("DECISIONS.md"):
        marker=b"## 2. "
        assert now[:now.index(marker)].startswith(old[:old.index(marker)])
        assert now[now.index(marker):].startswith(old[old.index(marker):])
    else:assert now.startswith(old)
fixture_paths=sorted((ROOT/"compile_repair/tests/fixtures/cp3_project").rglob("*.sol"))
assert len(fixture_paths)==3
fixtures={str(p.relative_to(ROOT)):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in fixture_paths}
write(OUT/"fixture_manifest.json",fixtures)
files={str(p.relative_to(OUT)):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(OUT.rglob("*")) if p.is_file()}
seal={"schema":"cp3-partial-checkpoint-seal-v1","status":"stopped_on_structure_mismatch",
      "cp3_complete":False,"parent_commit":baseline["head"],"files":files,
      "fixtures":fixtures,"production_changed":False,"llm_calls":0,"cost_usd":0,
      "pending_decision":"structure_review_request.json"}
write(OUT/"evidence_seal.json",seal)
paths=set(ROOT/p for p in baseline["docs"])
paths.update(fixture_paths);paths.update(p for p in OUT.rglob("*") if p.is_file())
inventory={"schema":1,"self":str((OUT/"delivery_inventory.json").relative_to(ROOT)),
 "files":{str(p.relative_to(ROOT)):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(paths)},
 "evidence_seal_sha256":sha(OUT/"evidence_seal.json"),
 "file_count_including_self":len(paths)+1,
 "staging_policy":"Only exact inventory paths plus self; never add external corpora or old untracked artifacts."}
write(OUT/"delivery_inventory.json",inventory)
# Reread bytes before any staging command.
for p,row in inventory["files"].items():assert sha(ROOT/p)==row["sha256"],p
for p,row in seal["files"].items():assert sha(OUT/p)==row["sha256"],p
print(json.dumps({"files":inventory["file_count_including_self"],"evidence_seal_sha256":inventory["evidence_seal_sha256"],
 "status":seal["status"],"cp3_complete":False}))
