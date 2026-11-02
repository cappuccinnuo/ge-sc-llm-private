"""Final NS-P2b integrity and documentation acceptance, without model fitting."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
from scripts.node_sem.doc_check import check
from scripts.node_sem import RUNTIME_MODULES

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
started=read(OUT/"started.json")
allowed={"HANDOVER.md","docs/training_changes_2026-10-07.md",
         "scripts/node_sem/PROGRESS.md","scripts/node_sem/NS_P2_REPORT.md",
         "scripts/node_sem/offline/README.md"}
changed=[]
for name,digest in started["tracked_sha256"].items():
    if sha(ROOT/name)!=digest:changed.append(name)
assert set(changed)<=allowed,changed
assert "doc_check.py" not in RUNTIME_MODULES
rewritten=read(OUT/"document_rewrite.json")
archive=read(OUT/"corrupted_docs/index.json")
for a,record in zip(archive,rewritten["replacements"]):
    assert sha(a["archive_path"])==a["corrupted_sha256"]
    b=(ROOT/a["path"]).read_bytes()
    if a["start_byte"]:
        start=a["start_byte"];end=start+record["replacement_bytes"]
        append=rewritten["append_offsets"][a["path"]]
        assert hashlib.sha256(b[:start]).hexdigest()==a["prefix_sha256"]
        assert hashlib.sha256(b[end:append]).hexdigest()==a["suffix_sha256"]
        assert len(b[end:append])==a["suffix_bytes"]
    else:
        assert sha(ROOT/a["path"])==record["after_replacement_sha256"]
docs=["scripts/node_sem/NS_P2_REPORT.md","scripts/node_sem/NS_P2B_REPORT.md",
      "scripts/node_sem/PROGRESS.md","HANDOVER.md","docs/training_changes_2026-10-07.md"]
env=dict(os.environ,CUDA_VISIBLE_DEVICES="",PYTHONDONTWRITEBYTECODE="1")
commands=[
 [sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+docs,
 [sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+
 [path+":"+str(rewritten["append_offsets"][path]) for path in docs[2:]],
 [sys.executable,"-B","-m","scripts.node_sem.doc_check","scripts/node_sem/offline/README.md"],
]
with (OUT/"doc_check.log").open("x",encoding="utf8") as stream:
    for cmd in commands:
        run=subprocess.run(cmd,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
        assert run.returncode==0
json_checked=[]
for p in sorted(OUT.rglob("*.json")):
    read(p);check(p);json_checked.append(p.name)
# Explicit old feature vector references, even when their NPZs are ignored by Git.
numbering=read(OUT/"numbering_effect.json")
feature_checks=[]
for task,record in numbering["tasks"].items():
    for view,refs in record["input_refs"].items():
        for name,ref in refs.items():
            assert sha(ref["path"])==ref["sha256"]
            feature_checks.append(dict(task=task,view=view,kind=name,ref=ref))
assert sum(d["carrier_loaded_views"] for d in numbering["tasks"].values())==8
assert read(OUT/"legacy_acceptance.json")["runtime_equal"]
tests=read(OUT/"tests.json")
assert tests["failed"]==0 and tests["skipped"]==0 and tests["passed"]==3113
check_git=subprocess.run(["git","-c","core.whitespace=cr-at-eol","diff","--check"],
                         cwd=ROOT,text=True,capture_output=True)
assert check_git.returncode==0,check_git.stdout+check_git.stderr
result=dict(passed=True,head=started["head"],tracked_files_checked=len(started["tracked_sha256"]),
    changed_tracked_files=changed,only_allowed_document_changes=True,
    full_docs_checked=docs,append_boundaries_checked=docs[2:],
    document_prefix_and_suffix_bytes_preserved=True,archive_sha_valid=True,
    json_checked=json_checked,old_feature_references_checked=len(feature_checks),
    modalities_loaded=8,legacy_8h_passed=True,training_runtime_checker_excluded=True,
    tests_passed=tests["passed"],tests_failed=0,tests_skipped=0,
    old_features_regenerated=False,gpu_used=False,training_runs=0,
    source_production_code_changed=False,git_diff_check_passed=True,
    artifact_inputs=feature_checks)
with (OUT/"final_validation.json").open("x",encoding="utf8") as stream:
    json.dump(result,stream,indent=2,ensure_ascii=True)
print(json.dumps({k:v for k,v in result.items() if k not in ("artifact_inputs","json_checked")},ensure_ascii=True))
