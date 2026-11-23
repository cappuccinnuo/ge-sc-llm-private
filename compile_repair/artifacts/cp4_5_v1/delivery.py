"""Check append-only reports and seal the exact bytes delivered at this CP4.5 checkpoint."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
MODULE=OUT.parents[1]
ROOT=MODULE.parent
BASE="c8ca807a7dde289eb9cb8f4b1818c54d083691d0"
DOCS=["CP4_REPORT.md","PROGRESS.md","docs/CHANGE_LOG.md","docs/DECISIONS.md","docs/HANDOVER.md"]
CODE=["evaluation/benchmark.py"]+["tests/test_cp"+n+".py" for n in ("42","43","44","45")]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, data):
    with (OUT/name).open("x",encoding="utf8") as f:
        json.dump(data,f,indent=2,sort_keys=True,ensure_ascii=False)
        f.write("\n")

def docs():
    args=[]
    for n in DOCS:
        path="compile_repair/"+n
        if n in DOCS[:3]:
            old=subprocess.check_output(["git","show",BASE+":"+path],cwd=ROOT)
            assert (MODULE/n).read_bytes().startswith(old),n
            path+=":"+str(len(old))
        args.append(path)
    args.append((OUT/"README.md").relative_to(ROOT).as_posix())
    cmd=["/home/zhao/miniconda3/envs/mando/bin/python","-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+args
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,check=False)
    checks=[json.loads(line) for line in r.stdout.splitlines()]
    write("doc_check.json",dict(command=cmd,returncode=r.returncode,records=checks,stderr=r.stderr.decode()))
    assert r.returncode==0 and len(checks)==6 and all(x["passed"] for x in checks)
    print("6 documents passed")

def seal():
    assert json.loads((OUT/"doc_check.json").read_bytes())["returncode"]==0
    for suite in ("production","mando","dfg"):
        assert json.loads((OUT/("suites/"+suite+"_tests.json")).read_bytes())["returncode"]==0
    scope=json.loads((OUT/"scope.json").read_bytes())
    assert scope["production_files"]==17 and scope["unchanged_dfg_code_refs"]==354
    assert all(sha(ROOT/n)==v for n,v in scope["production_sha256"].items())
    paths=sorted(OUT.rglob("*"))
    assert not any(p.is_symlink() or "__pycache__" in p.parts for p in paths)
    write("seal.json",dict(base=BASE,batch={p.relative_to(OUT).as_posix():sha(p) for p in paths if p.is_file()},
                           deliverables={n:sha(MODULE/n) for n in CODE+DOCS}))

def verify_index():
    sealed=json.loads((OUT/"seal.json").read_bytes())
    files={OUT/k:v for k,v in sealed["batch"].items()}
    files.update({MODULE/k:v for k,v in sealed["deliverables"].items()})
    files[OUT/"seal.json"]=sha(OUT/"seal.json")
    staged=set(subprocess.check_output(["git","diff","--cached","--name-only"],cwd=ROOT).decode().splitlines())
    assert staged=={path.relative_to(ROOT).as_posix() for path in files},staged
    for path,h in files.items():
        blob=subprocess.check_output(["git","show",":"+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        assert sha(path)==hashlib.sha256(blob).hexdigest()==h,path
    print(len(staged),"staged files matched the seal")

if __name__=="__main__":
    {"docs":docs,"seal":seal,"verify_index":verify_index}[sys.argv[1]]()
