"""Seal the decision checkpoint without asserting final experiment acceptance."""
import sys
from check_delivery import OUT,ROOT,BASE,read,write,digest

def run():
    assert read("checkpoint_79.json")["remaining"]==121
    assert read("checkpoint_doc_check.json")["returncode"]==0
    files={p.relative_to(OUT).as_posix():digest(p) for p in sorted(OUT.rglob("*"))
           if p.is_file() and p.name!="checkpoint_seal.json"}
    assert not any("__pycache__" in k for k in files)
    src=("evaluation/benchmark.py","tests/test_cp41.py","tests/test_cp42.py","CP4_REPORT.md",
         "PROGRESS.md","docs/CHANGE_LOG.md","docs/DECISIONS.md","docs/HANDOVER.md")
    write("checkpoint_seal.json",dict(base=BASE,stage="CP4.2 / movement 79 of 200",
          batch_files_excluding_self=files,deliverables_sha256={k:digest(ROOT/"compile_repair"/k) for k in src}))

if __name__=="__main__":run()
