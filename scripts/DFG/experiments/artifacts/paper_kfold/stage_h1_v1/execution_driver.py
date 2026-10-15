"""Operational driver: wait for the CPU preparation, then sealed serial H1 only."""
import os,sys,time,json,subprocess,csv
from pathlib import Path
ROOT=Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
OUT=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/stage_h1_v1"
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONUNBUFFERED="1",PYTHONPATH=str(ROOT),
 TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2")
records=[]
def load(p):return json.loads(Path(p).read_text())
def run(command,filename):
    start=time.monotonic()
    with (OUT/filename).open("x") as stream:
        result=subprocess.run(command,cwd=str(ROOT),env=env,stdout=stream,stderr=subprocess.STDOUT)
    records.append({"command":command,"returncode":result.returncode,"seconds_monotonic":time.monotonic()-start,"log":filename})
    (OUT/"driver_execution.json").write_text(json.dumps({"status":"running","commands":records},indent=2))
    if result.returncode:raise RuntimeError("STOP: "+filename+" failed, no automatic retry")
try:
    while not (OUT/"preparation_execution.json").exists():
        os.kill(3827273,0)
        time.sleep(5)
    assert load(OUT/"preparation_execution.json")["returncode"]==0
    assert load(OUT/"integration_tests.json")["returncode"]==0
    assert load(OUT/"original_resource_test.json")["returncode"]==0
    assert load(OUT/"baseline_preflight.json")["status"]=="passed"
    rows=[];nodes=[];enh=[];manifests=load(OUT/"input_manifest.json")["tasks"]
    assert len(manifests)==30
    for spec in manifests:
        info=load(spec["manifest"])
        for variant,support in info["support"].items():
            assert support["supported"] and support["no_samples_or_edges_removed"]
            prefix={"task_id":spec["task_id"],"fold":spec["fold"],"variant":variant}
            for row in support["relations"]:rows.append(dict(prefix,**row))
            for row in support["nodes"]:nodes.append(dict(prefix,**row))
            for rel,count in support["enhancement_support"].items():enh.append(dict(prefix,relation=rel,**count))
    for filename,values in (("canonical_support.csv",rows),("node_type_support.csv",nodes),("enhancement_support.csv",enh)):
        with (OUT/filename).open("x",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    base=[sys.executable,"-B","-m","scripts.DFG.experiments.e23_cv.control"]
    run(base+["seal"],"seal.log")
    run(base+["verify"],"initial_verification.log")
    run(base+["run"],"controller.log")
    run(base+["verify"],"final_verification.log")
    run(base+["summarize"],"summary_execution.log")
    (OUT/"driver_execution.json").write_text(json.dumps({"status":"complete","commands":records,"h2_executed":False},indent=2))
    print("H1 COMPLETE: report analysis still required",flush=True)
except BaseException as exc:
    (OUT/"driver_execution.json").write_text(json.dumps({"status":"stopped","exception":repr(exc),"commands":records,"automatic_retry":False},indent=2))
    raise
