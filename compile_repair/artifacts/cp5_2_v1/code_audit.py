"""Verify the frozen production scope and the DFG references using their normal entry point."""
import ast
import json
import subprocess
import sys
from pathlib import Path
from measure import ART, HERE, ROOT, load, save, sha256

base = load(HERE/"baseline.json")["base_commit"]
freeze = load(HERE/"frozen_suites/source_freeze.json")["modules"]
assert len(freeze)==18 and all(sha256(ROOT/k)==v for k,v in freeze.items())


def functions(data):
    found={}
    for node in ast.parse(data).body:
        if isinstance(node,ast.FunctionDef):
            found[node.name]=ast.dump(node)
        if isinstance(node,ast.ClassDef):
            for method in node.body:
                if isinstance(method,ast.FunctionDef):
                    found[node.name+"."+method.name]=ast.dump(method)
    return found


changed={}
for path in freeze:
    old=subprocess.check_output(["git","show",base+":"+path],cwd=ROOT)
    new=(ROOT/path).read_bytes()
    if old==new:continue
    before,after=functions(old),functions(new)
    counts=subprocess.check_output(["git","diff","--numstat",base,"--",path],cwd=ROOT,text=True).split()
    changed[path]=dict(added=int(counts[0]),removed=int(counts[1]),sha256=freeze[path],
        functions=sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)))
assert set(changed)=={"compile_repair/"+p for p in ("pipeline.py","rules/dependencies.py","toolchain/slither.py","evaluation/benchmark.py")}
mando = Path.home()/"miniconda3/envs/mando/bin/python"
refs=json.loads(subprocess.check_output([str(mando),"-B","-c",
    "import json;from scripts.DFG.dfg_v2.experiment.run import _code_refs;print(json.dumps(_code_refs()))"],cwd=ROOT))
assert refs==load(ART/"cp3_continue_v1/baseline.json")["code_refs"] and len(refs)==354
suites={name:load(HERE/"frozen_suites"/(name+"_tests.json")) for name in ("production","mando","dfg")}
assert all(v["returncode"]==0 and load(HERE/"frozen_suites"/(k+"_guard.json"))["hashes"]==freeze for k,v in suites.items())
save(HERE/"code_audit.json",dict(base=base,production_files=len(freeze),changed=changed,dfg_refs_equal=len(refs),
     suites=suites,cpu=True,downloads=0,llm_calls=0,cost_usd=0))
