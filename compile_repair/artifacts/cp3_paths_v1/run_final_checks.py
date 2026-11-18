"""Final prescribed no-cache checks; no retries and stop on first unexpected result."""
import json, os, re, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
B=Path(__file__).resolve().parent
LOCAL=Path("/home/zhao/SmartContract/compile-repair-local/cp3_paths_v1")
checks=[("production","compile-repair-production","compile_repair/tests",731,6),
        ("mando","mando","compile_repair/tests",271,466),
        ("dfg","mando","scripts/DFG/dfg_v2/tests",2653,0)]
assert json.loads((B/"path_probes.json").read_text())["accepted"]
assert json.loads((B/"driver_comparison_recovery.json").read_text())["accepted"]
assert json.loads((LOCAL/"continue_remaining_102/summary.json").read_text())["status"]=="complete_segment"
for label,env,suite,passed,skipped in checks:
    assert not (LOCAL/("pytest_"+label+"_final_v1")).exists(), "Refuse existing pytest directory"
    argv=["/home/zhao/miniconda3/envs/"+env+"/bin/python","-B","-m","pytest","-q",
          "-p","no:cacheprovider",suite,"--basetemp="+str(LOCAL/("pytest_"+label+"_final_v1"))]
    prefix="pytest_"+label+"_final_v1"
    start=time.monotonic()
    with (B/(prefix+".stdout")).open("xb") as out,(B/(prefix+".stderr")).open("xb") as err:
        result=subprocess.run(argv,cwd=str(ROOT),stdout=out,stderr=err)
    output=(B/(prefix+".stdout")).read_text()
    observed_passed=re.findall(r"(\d+) passed",output)
    observed_skipped=re.findall(r"(\d+) skipped",output)
    counts={"passed":int(observed_passed[-1]) if observed_passed else 0,
            "skipped":int(observed_skipped[-1]) if observed_skipped else 0}
    receipt={"command":argv,"cwd":str(ROOT),"returncode":result.returncode,
             "elapsed_seconds":time.monotonic()-start,"counts":counts,
             "expected":{"passed":passed,"skipped":skipped},"cost_usd":0}
    receipt["accepted"]=result.returncode==0 and counts==receipt["expected"]
    with (B/(prefix+".json")).open("x") as f:
        json.dump(receipt,f,indent=2);f.write("\n")
    print(json.dumps(receipt),flush=True)
    if not receipt["accepted"]:
        sys.exit(2)
