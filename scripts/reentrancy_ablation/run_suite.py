"""Sequential background orchestration; live logs and resumable per-fold outputs."""
import argparse, subprocess, os, time
from common import *

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=HERE/"artifacts/v1")
    p.add_argument("--seed",type=int,default=1)
    p.add_argument("--experiments",nargs="+")
    args=p.parse_args();root=confined(args.root);prepared=root/"prepared"
    m=read_json(prepared/"manifest.json")
    jobs=[("node",n) for n in ["A_author","B_local_labels","D_local_features","C_local_relations",
                              "T_validation_legacy","T_lr_legacy","T_upstream_behavior"]]
    jobs += [("contract",n) for n in ["A_author","D_local_features","C_local_relations",
                              "T_gradient_detached","T_lr_legacy","T_delta_legacy","T_upstream_behavior"]]
    if args.experiments:jobs=[j for j in jobs if j[1] in args.experiments]
    if m["feature_variant_identical"]:jobs=[j for j in jobs if j[1]!="D_local_features"]
    state={"started_utc":utc(),"pid":os.getpid(),"seed":args.seed,"jobs":jobs,"completed":[],"status":"running"}
    state_path=root/("suite_seed_"+str(args.seed)+".json")
    root.mkdir(parents=True,exist_ok=True);write_json(state_path,state)
    for task,experiment in jobs:
        dest=root/"runs"/task/experiment/("seed_"+str(args.seed));dest.mkdir(parents=True,exist_ok=True)
        state["current"]={"task":task,"experiment":experiment,"output":str(dest),"started_utc":utc()}
        write_json(state_path,state)
        cmd=[sys.executable,"-u",str(HERE/"run_experiment.py"),"--prepared",str(prepared),
             "--task",task,"--experiment",experiment,"--seed",str(args.seed),"--output",str(dest)]
        print("JOB",task,experiment,flush=True)
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONHASHSEED=str(args.seed))
        with (dest/"train.log").open("a",buffering=1) as log:
            process=subprocess.Popen(cmd,cwd=str(REPO),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                     universal_newlines=True,env=env,bufsize=1)
            state["current"]["pid"]=process.pid;write_json(state_path,state)
            for line in process.stdout:
                log.write(line);print(line,end="",flush=True)
            code=process.wait()
        if code:
            state["status"]="failed";state["exit_code"]=code;state["finished_utc"]=utc()
            write_json(state_path,state);raise SystemExit(code)
        state["completed"].append([task,experiment]);write_json(state_path,state)
    state["status"]="complete";state["finished_utc"]=utc();state["current"]=None
    write_json(state_path,state)
    print("SUITE COMPLETE",flush=True)

if __name__=="__main__":main()
