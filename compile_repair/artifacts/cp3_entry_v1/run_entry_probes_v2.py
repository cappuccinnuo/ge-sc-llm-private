"""Approved leading-hyphen probes plus unchanged plain-entry checks; stop on failure."""
import hashlib, json, re, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
B=Path(__file__).resolve().parent
LOCAL=Path("/home/zhao/SmartContract/compile-repair-local/cp3_entry_v1")
LOCAL.mkdir(parents=True, exist_ok=True)
tmp=LOCAL/"pytest_entry_probes_v2"
assert not tmp.exists()
argv=["/home/zhao/miniconda3/envs/compile-repair-production/bin/python","-B","-m","pytest","-q","-x",
      "-p","no:cacheprovider","compile_repair/tests/test_project.py","-k",
      "leading_dash_entry_same_target or production_project_same_parameters","--basetemp="+str(tmp)]
start=time.monotonic()
with (B/"entry_probes_v2.stdout").open("xb") as out,(B/"entry_probes_v2.stderr").open("xb") as err:
    result=subprocess.run(argv,cwd=str(ROOT),stdout=out,stderr=err)
files=[]
for kind in ["compiled.json","analysis.json"]:
    for source in sorted(tmp.glob("test_leading_dash*/project/"+kind)):
        dest=B/"probes_v2"/source.parent.parent.name/kind
        dest.parent.mkdir(parents=True,exist_ok=True)
        raw=source.read_bytes()
        with dest.open("xb") as stream:stream.write(raw)
        files.append({"path":str(dest.relative_to(ROOT)),"sha256":hashlib.sha256(raw).hexdigest()})
text=(B/"entry_probes_v2.stdout").read_text()
passed=re.findall(r"(\d+) passed",text)
receipt={"command":argv,"cwd":str(ROOT),"returncode":result.returncode,
         "elapsed_seconds":time.monotonic()-start,"passed":int(passed[-1]) if passed else 0,
         "files":files,"cost_usd":0,"expected_passed":8}
receipt["accepted"]=result.returncode==0 and receipt["passed"]==8 and len(files)==8
with (B/"entry_probes_v2.json").open("x") as f:json.dump(receipt,f,indent=2);f.write("\n")
print(json.dumps(receipt),flush=True)
print(text[-2000:],flush=True)
sys.exit(0 if receipt["accepted"] else 2)
