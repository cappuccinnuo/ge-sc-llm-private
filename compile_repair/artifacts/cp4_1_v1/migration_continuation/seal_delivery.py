"""Seal the scientific and documentation receipts without copying external project inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
from final_acceptance import DEST, HERE, checked, sha

ROOT=DEST.parents[3]
BASE="0f690e6f2152d4bb6390f56ffb9de91e06a893ea"
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()==BASE
    auth=json.loads((HERE/"migration_stop_seal.json").read_bytes())
    for name,info in auth["batch_files_excluding_this_seal"].items():
        checked(HERE/name,info["sha256"])
    assert json.loads((DEST/"doc_check.json").read_bytes())["returncode"]==0
    assert json.loads((DEST/"acceptance.json").read_bytes())["complete"]
    scope=json.loads((DEST/"final_scope.json").read_bytes())
    assert scope["before_production"]==scope["after_production"]==17 and scope["dfg_refs_match"]
    tests={}
    for path in sorted((DEST/"definition_continuation/suites").glob("*_tests.json")):
        r=json.loads(path.read_bytes())
        assert r["returncode"]==0
        tests[path.stem]=r["summary"]
    assert len(tests)==3
    files={}
    for path in sorted(DEST.rglob("*")):
        assert not path.is_symlink() and "__pycache__" not in path.parts
        if path.is_file() and path.name!="seal.json":
            rel=path.relative_to(DEST).as_posix()
            files[rel]=dict(sha256=digest(path),bytes=path.stat().st_size)
    paths=("evaluation/benchmark.py","tests/test_cp41.py","CP4_REPORT.md","PROGRESS.md",
           "docs/CHANGE_LOG.md","docs/HANDOVER.md","docs/DECISIONS.md","PROMPTS.md")
    sealed=dict(stage="CP4.1", state="self-check complete; independent review is next", previous_checkpoint=BASE,
                original_cp41_seal_sha256=digest(HERE/"migration_stop_seal.json"),old_batch_files_checked=len(auth["batch_files_excluding_this_seal"]),
                tests=tests,tracked_project_sha256={p:digest(ROOT/"compile_repair"/p) for p in paths},
                continuation_files_excluding_this_seal=files, corpus_sources_in_git=0, training_runs=0,llm_calls=0,cost_usd=0)
    with (DEST/"seal.json").open("x",encoding="utf8") as fp:
        json.dump(sealed,fp,indent=2,ensure_ascii=False);fp.write("\n")
    print("Sealed",len(files),"continuation files and verified",sealed["old_batch_files_checked"],"old batch files")
if __name__=="__main__":main()
