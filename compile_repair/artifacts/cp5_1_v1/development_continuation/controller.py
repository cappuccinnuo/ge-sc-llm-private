"""Execute the authorized continuation and each initially planned offline acceptance stage once."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from population import LOCAL, OUT, ROOT, load, save, sha256


def main():
    py = Path("/home/zhao/miniconda3/envs/compile-repair-production/bin/python")
    assert Path(sys.executable).resolve() == py.resolve()
    verify = load(HERE/"prefix_verification.json")
    consent = load(HERE/"authorization.json")
    assert verify["rows"] == 6940 and verify["prefix_sha256"] == consent["prefix_sha256"]
    assert not (OUT/"policy.json").exists() and (OUT/"stage_runs.jsonl").stat().st_size == 0
    logs = LOCAL / "development_continuation"
    logs.mkdir(parents=True,exist_ok=True)
    steps = [
        ("development_native", HERE/"resume_development.py"),
        ("registered_stages", HERE/"registered_stages.py"),
        ("final_audit", OUT/"audit.py", "final"),
        ("ir_review", OUT/"review_ir_logs.py"),
        ("invocation_seals", OUT/"seal_results.py", "units"),
        ("archives", OUT/"record_archives.py", "pack"),
        ("documentation", OUT/"finish_docs.py"),
        ("doc_check", OUT/"check_docs.py", "final_doc_check"),
        ("seal", OUT/"seal_results.py", "batch"),
    ]
    save(HERE/"controller_claim.json",dict(pid=os.getpid(),boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
         authorization_sha256=sha256(HERE/"authorization.json"),prefix_verification_sha256=sha256(HERE/"prefix_verification.json"),
         scripts={script.name:sha256(script) for name,script,*args in steps},started=time.time(), network=False))
    with (logs/"controller.jsonl").open("x",encoding="utf8") as journal:
        def mark(**item):
            journal.write(json.dumps(dict(time=time.time(),**item),sort_keys=True)+"\n")
            journal.flush()
            os.fsync(journal.fileno())
        for name,script,*args in steps:
            log=logs/(name+".log")
            with log.open("xb") as output:
                mark(stage=name,status="start",command=[str(py),"-B","-u",str(script),*args])
                result=subprocess.run([str(py),"-B","-u",str(script),*args],cwd=ROOT,
                                      stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT)
            mark(stage=name,status="complete" if result.returncode==0 else "stopped",returncode=result.returncode,
                 output_sha256=sha256(log))
            if result.returncode:
                raise SystemExit(result.returncode)
        mark(stage="all",status="complete",batch_seal_sha256=sha256(OUT/"seal.json"))


if __name__ == "__main__":
    main()
