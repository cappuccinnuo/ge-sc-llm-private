"""Finish CP5.2 once all measured stages, source guards and hard authorizations agree."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUN=HERE/"continuation"
load=lambda p:json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def invoke(name,*args):
    subprocess.run([sys.executable,"-B",str(HERE/name),*args],cwd=ROOT,check=True)


def main():
    assert not (RUN/"measurement_stop.json").exists()
    jobs=load(RUN/"schedule_start.json")["tasks"]
    assert len(jobs)==9
    for job in jobs:
        assert load(RUN/(job[0]+"_exit.json"))["returncode"]==0
    modules=load(HERE/"frozen_suites/source_freeze.json")["modules"]
    assert len(modules)==18 and all(sha(ROOT/k)==v for k,v in modules.items())
    assert load(RUN/"fresh_solc_verified.json")["verified"]==711
    assert load(HERE/"mando/summary.json")["passed"]
    invoke("summarize_acceptance.py")
    invoke("seal_invocations.py")
    invoke("pack_tables.py")
    invoke("finish_records.py")
    invoke("check_docs.py","pre_doc_check")
    log=ROOT/"compile_repair/docs/CHANGE_LOG.md"
    old="文档按各自追加边界执行 doc_check，命令、逐文件结果及最终 SHA256 见本批 final_doc_check.json。"
    new="文档按各自追加边界执行 doc_check，初验 6/6 通过。最终复核的命令、逐文件结果及 SHA256 见本批 final_doc_check.json。"
    text=log.read_text(encoding="utf8")
    assert text.count(old)==1
    log.write_bytes(text.replace(old,new).encode("utf8"))
    invoke("check_docs.py","final_doc_check")
    subprocess.run(["git","diff","--check"],cwd=ROOT,check=True)
    tracked=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=ROOT,text=True).splitlines()
    assert all(n.startswith("compile_repair/") for n in tracked)
    safe_logs={"focused_tests.log","production_tests.log","development_partial_ir.log","external_part0.log",
               "historical_scores.log","schedule.log","frozen_suites/production_tests.log",
               "frozen_suites/mando_tests.log","frozen_suites/dfg_tests.log","continuation/schedule.log"}
    files={}
    for path in sorted(HERE.rglob("*")):
        if not path.is_file():continue
        rel=path.relative_to(HERE).as_posix()
        if path.suffix in {".py",".md",".json",".gz"} or rel in safe_logs:
            files[rel]=dict(bytes=path.stat().st_size,sha256=sha(path))
    with (HERE/"seal.json").open("x",encoding="utf8") as f:
        json.dump(dict(base=load(HERE/"baseline.json")["base_commit"],portable_files_excluding_seal=files,
                  raw_local_receipts_index="record_archives.json",source_scope=tracked,cost_usd=0),
                  f,sort_keys=True,indent=2);f.write("\n")
    print("Verified measured stages",len(jobs),"and portable files",len(files),flush=True)


if __name__=="__main__":
    main()
