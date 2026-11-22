"""Verify fixed run boundaries and record per-function production changes against the input commit."""
import ast
from collections import Counter, defaultdict
import re
from batch import *

def git(*args):
    return subprocess.check_output(["git","--no-optional-locks",*args],cwd=str(ROOT))

def owners(text):
    result={}
    def walk(node,namespace=""):
        for child in ast.iter_child_nodes(node):
            nested=namespace
            if isinstance(child,(ast.FunctionDef,ast.ClassDef,ast.AsyncFunctionDef)):
                nested=namespace+"."+child.name if namespace else child.name
                for i in range(child.lineno,child.end_lineno+1):
                    result[i]=nested
            walk(child,nested)
    walk(ast.parse(text))
    return result

def counts(path):
    before=git("show",BASE+":"+path).decode("utf8")
    now=(ROOT/path).read_text(encoding="utf8")
    left,right=owners(before),owners(now)
    changes=defaultdict(Counter)
    data=git("diff","--no-ext-diff","--no-color","-U0",BASE,"--",path).decode("utf8")
    for row in data.splitlines():
        match=re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",row)
        if match:
            a,n,b,m=match.groups()
            for start,span,lookup,op in ((a,n,left,"deleted"),(b,m,right,"added")):
                start=int(start);span=int(span) if span is not None else 1
                for i in range(start,start+span):
                    changes[lookup.get(i,"<module>")][op]+=1
    added,deleted,_=git("diff","--numstat",BASE,"--",path).decode().rstrip().split("\t")
    assert int(added)==sum(x["added"] for x in changes.values())
    assert int(deleted)==sum(x["deleted"] for x in changes.values())
    return dict(added=int(added),deleted=int(deleted),functions=dict(sorted(changes.items())))

def main():
    mod=ROOT/"compile_repair"
    paths=list(mod.glob("*.py"))
    for name in ("core","toolchain","rules","evaluation","rag","agents"):
        paths.extend((mod/name).rglob("*.py"))
    prod={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths)}
    base=json.loads(frozen(OLD/"acceptance.json"))["scope"]["production_sha256"]
    assert len(base)==len(prod)==17 and set(prod)==set(base)
    delta=[n for n in prod if prod[n]!=base[n]]
    assert set(delta)=={"compile_repair/evaluation/benchmark.py","compile_repair/evaluation/report.py","compile_repair/toolchain/solc.py"}
    refs_script="import json;from scripts.DFG.dfg_v2.experiment.run import _code_refs;print(json.dumps(_code_refs()))"
    refs=json.loads(subprocess.check_output(["/home/zhao/miniconda3/envs/mando/bin/python","-B","-c",refs_script],cwd=str(ROOT)))
    sealed=json.loads(frozen(ART/"cp3_continue_v1/baseline.json"))["code_refs"]
    assert refs==sealed
    outside=git("diff","--name-only",BASE,"--",".",":(exclude)compile_repair")
    prior=git("diff","--name-only",BASE,"--","compile_repair/artifacts",":(exclude)compile_repair/artifacts/cp4_1_v1")
    assert not outside and not prior
    saved(sys.argv[1] if len(sys.argv)>1 else "scope.json",dict(base_commit=BASE,before_production=len(base),after_production=len(prod),
        changed_production=delta,production_sha256=prod,change_by_function={n:counts(n) for n in delta},
        frozen_dfg_code_refs=len(refs),dfg_refs_match=True,changed_outside=[],changed_older_artifacts=[]))
    print(len(prod),"production files;",len(refs),"frozen DFG refs")
if __name__=="__main__":main()
