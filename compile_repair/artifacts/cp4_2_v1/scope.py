"""Check the CP4.2 production scope and frozen code references from the dedicated worktree."""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
BASE="30df6664b2b042685a5a8134278f80915a5cb58e"
MODULE="compile_repair/evaluation/benchmark.py"
MIG=OUT.parent/"cp4_1_v1/migration_continuation"


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)


def owners(code):
    result={}
    def walk(node,parent):
        for child in ast.iter_child_nodes(node):
            name=parent
            if isinstance(child,(ast.FunctionDef,ast.ClassDef)):
                name=(parent+"." if parent else "")+child.name
                for i in range(child.lineno,child.end_lineno+1):result[i]=name
            walk(child,name)
    walk(ast.parse(code),"")
    return result


def main():
    prior=json.loads((MIG/"final_scope.json").read_bytes())["production_sha256"]
    tracked=set(git("ls-files","compile_repair/*.py").decode().splitlines())
    names=sorted(n for n in tracked if "/tests/" not in n and "/artifacts/" not in n)
    now={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    assert len(now)==len(prior)==17 and set(now)==set(prior)
    assert [n for n in now if now[n]!=prior[n]]==[MODULE]
    assert not git("diff","--name-only",BASE,"--",".",":(exclude)compile_repair").strip()
    assert not git("diff","--name-only",BASE,"--","compile_repair/artifacts",":(exclude)compile_repair/artifacts/cp4_2_v1").strip()
    env="/home/zhao/miniconda3/envs/mando/bin/python"
    command=[env,"-B","-c","import json;from scripts.DFG.dfg_v2.experiment.run import _code_refs;print(json.dumps(_code_refs()))"]
    ref=json.loads(subprocess.check_output(command,cwd=ROOT))
    assert ref==json.loads((OUT.parent/"cp3_continue_v1/baseline.json").read_bytes())["code_refs"]
    old,new=owners(git("show",BASE+":"+MODULE)),owners((ROOT/MODULE).read_bytes())
    count=defaultdict(Counter)
    diff=git("diff","--no-color","-U0",BASE,"--",MODULE).decode()
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",diff,re.M):
        a,na,b,nb=m.groups()
        for st,num,lookup,op in ((a,na,old,"deleted"),(b,nb,new,"added")):
            for i in range(int(st),int(st)+int(num or 1)):count[lookup.get(i,"module")][op]+=1
    nadd,ndel,_=git("diff","--numstat",BASE,"--",MODULE).decode().split()
    assert int(nadd)==sum(c["added"] for c in count.values()) and int(ndel)==sum(c["deleted"] for c in count.values())
    with (OUT/(sys.argv[1] if len(sys.argv)>1 else "scope.json")).open("x",encoding="utf8") as fp:
        json.dump(dict(base=BASE,production_files=len(now),changed_production=[MODULE],added=int(nadd),deleted=int(ndel),by_function=count,
                       unchanged_dfg_code_refs=len(ref),production_sha256=now),fp,indent=2);fp.write("\n")
    print(nadd,ndel,len(ref))
if __name__=="__main__":main()
