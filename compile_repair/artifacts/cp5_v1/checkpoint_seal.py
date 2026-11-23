"""Bind partial evidence, documentation and the exact implementation to the CP5 stop."""
import ast
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cp=ROOT/"compile_repair"
    prod=[p for p in cp.rglob("*.py") if not {"artifacts","tests","docs"}.intersection(p.relative_to(cp).parts)]
    replay=json.loads((OUT/"final_mando/summary.json").read_bytes())
    assert replay["passed"] and replay["modules_match"] and len(prod)==18
    assert {p.relative_to(ROOT).as_posix():sha(p) for p in prod} == replay["implementation_sha256"]
    for p in (OUT/"run_benchmark.py",OUT/"run_external.py"):
        ast.parse(p.read_bytes())
    docs=json.loads((OUT/"checkpoint_doc_final.json").read_bytes())
    assert len(docs["records"])==6 and all(r["passed"] for r in docs["records"])
    assert all(sha(ROOT/p)==h for p,h in docs["sha256"].items())
    paths=list(p for p in OUT.rglob("*") if p.is_file())
    assert not any(p.is_symlink() or p.suffix in (".tgz",".sol",".pyc") for p in paths)
    files={p.relative_to(OUT).as_posix():sha(p) for p in sorted(paths)}
    receipt=dict(status="partial",files=files,base="26f44492c093311257f7b3de41ba3bee2e703ea3",
                 implementation=replay["implementation_sha256"],documents=docs["sha256"],
                 open_items=["registry transfer continuation","optimizer validator scope",
                             "complete archive index","development version policy","benchmark and external acceptance"],
                 external_paths={"releases":"corpora/compile-repair-npm-cp5-v1","measurements":"compile-repair-local/cp5_v1"})
    with (OUT/"checkpoint_seal.json").open("x",encoding="utf8") as fp:
        json.dump(receipt,fp,indent=2,sort_keys=True)
        fp.write("\n")
    assert all(sha(OUT/p)==h for p,h in files.items())
    print(len(files),"files verified",sha(OUT/"checkpoint_seal.json"))


if __name__=="__main__":
    main()
