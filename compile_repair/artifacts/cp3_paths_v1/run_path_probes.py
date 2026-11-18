"""Authorized four-version root, leading-dash and ordinary nested-entry probes."""
import collections, hashlib, json, re, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
B=Path(__file__).resolve().parent
LOCAL=Path("/home/zhao/SmartContract/compile-repair-local/cp3_paths_v1")
LOCAL.mkdir(parents=True, exist_ok=True)
tmp=LOCAL/"pytest_path_probes_v1"
assert not tmp.exists()
argv=["/home/zhao/miniconda3/envs/compile-repair-production/bin/python","-B","-m","pytest","-q","-x",
      "-p","no:cacheprovider","compile_repair/tests/test_project.py","-k",
      "leading_dash_entry_same_target or production_project_same_parameters or ordinary_nested_entry",
      "--basetemp="+str(tmp)]
start=time.monotonic()
with (B/"path_probes.stdout").open("xb") as out,(B/"path_probes.stderr").open("xb") as err:
    result=subprocess.run(argv,cwd=str(ROOT),stdout=out,stderr=err)
files=[]; versions=collections.Counter()
for folder in sorted(tmp.iterdir()):
    if folder.is_symlink() or not folder.is_dir():continue
    for kind in ["compiled.json","analysis.json"]:
        source=folder/"project"/kind
        if not source.is_file():continue
        dest=B/"probes"/folder.name/kind
        dest.parent.mkdir(parents=True,exist_ok=True)
        raw=source.read_bytes()
        with dest.open("xb") as f:f.write(raw)
        data=json.loads(raw)
        if kind=="compiled.json":versions[data["compiler"]["version"]]+=1
        files.append({"path":str(dest.relative_to(ROOT)),"sha256":hashlib.sha256(raw).hexdigest()})
output=(B/"path_probes.stdout").read_text()
passed=re.findall(r"(\d+) passed",output)
receipt={"command":argv,"cwd":str(ROOT),"returncode":result.returncode,
         "elapsed_seconds":time.monotonic()-start,"passed":int(passed[-1]) if passed else 0,
         "files":files,"compiled_probe_versions":dict(versions),"cost_usd":0,"expected_passed":12}
receipt["accepted"]=result.returncode==0 and receipt["passed"]==12 and len(files)==16 and versions==dict.fromkeys(["0.4.12","0.4.24","0.5.17","0.8.38"],2)
with (B/"path_probes.json").open("x") as f:json.dump(receipt,f,indent=2);f.write("\n")
print(json.dumps({k:v for k,v in receipt.items() if k!="files"}),flush=True)
print(output[-3000:],flush=True)
sys.exit(0 if receipt["accepted"] else 2)
