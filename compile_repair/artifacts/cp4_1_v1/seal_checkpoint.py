"""Seal the migration-scoring stop as a reproducible point for incremental continuation."""
from batch import *

def main():
    for n in ("population.json","migration_stop_scope.json","migration_stop_inventory.json","runtime_recovery.json"):
        load(n)
    doc=load("migration_stop_doc_check.json")
    assert doc["returncode"]==0 and len(doc["documents"])==6
    for rec in doc["documents"]:
        assert rec["passed"]
        checked(ROOT/rec["path"],rec["sha256"])
    tests={}
    for name in ("production","mando","dfg"):
        j=load("final_tests/"+name+"_tests.json")
        assert j["returncode"]==0
        tests[name]=j["summary"]
    scope=load("migration_stop_scope.json")
    for file,digest in scope["production_sha256"].items():checked(ROOT/file,digest)
    index=load("migration_stop_inventory.json")
    checked(OUT/"migration_stop_receipts.jsonl.gz",index["sha256"])
    for key,info in index["by_cohort"].items():
        checked(OUT/(key+"_scores.jsonl.gz"),info["first_pass_score_file_sha256"])
    files={}
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            assert not p.is_symlink() and p.suffix in {".json",".gz",".py",".tsv",".log",".md"},p
            files[str(p.relative_to(OUT))]=dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
    extra={}
    mod=ROOT/"compile_repair"
    for p in sorted([mod/"tests/test_cp41.py"]+list((mod/"tests/fixtures/cp4_1").rglob("*"))):
        if p.is_file():extra[str(p.relative_to(ROOT))]=sha(p.read_bytes())
    saved("migration_stop_seal.json",dict(stage="CP4.1",state="migration_scoring_stopped_pending_user_decision",
        prior_commit=BASE,profile="production",changed_fixture_sha256=extra,tests=tests,
        batch_files_excluding_this_seal=files,docs_sha256={r["path"]:r["sha256"] for r in doc["documents"]},
        older_artifacts_changed=0,training_runs=0,downloads=0,cost_usd=0))
    print("checkpoint sealed",len(files),"batch files and",len(extra),"test/fixture files")
if __name__=="__main__": main()
