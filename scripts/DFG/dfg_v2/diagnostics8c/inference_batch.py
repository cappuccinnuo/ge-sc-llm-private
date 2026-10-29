"""Serial inference-only controller; preserves the frozen 150-fit batch."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from .common import read, write_new, checked_plan, attempt_for
from scripts.DFG.integration.io import sha256
from scripts.DFG.dfg_v2.tasks import checked_ref


def prepare(plan_path, output):
    from scripts.labeling_v2.safe_graph import read_graph
    from scripts.DFG.dfg_v2.experiment.run import _prepared
    from .inference import replacement_map, rewrite_code
    import hashlib
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    plan = checked_plan(plan_path)
    gate = read(output / "gate.json")
    if not gate.get("archive_parity", {}).get("passed") or gate["plan_sha256"] != sha256(plan_path):
        raise ValueError("Unmodified prediction gate required")
    verification = read(output.parent / "verification_v2/verification.json")
    if verification["verified"] != 150 or verification["plan_sha256"] != sha256(plan_path):
        raise ValueError("Complete historical verification required")
    jobs = [job for job in plan["jobs"] if plan["tasks"][job["task_id"]]["record"]["task"] == "node"]
    if len(jobs) != 100:
        raise ValueError("Expected 100 frozen best inference jobs")
    # A worker completed during a lexical robustness fix. Reuse only if every
    # current exact text patch matches its recorded before/after SHA evidence.
    first_path = output / "jobs/reentrancy_node_0_G0.json"
    first = read(first_path)
    task, info, entry = _prepared(plan, first["job"])
    graph = read_graph(checked_ref(entry["graph"]))
    maps = {file:replacement_map(checked_ref(task["record"]["sources"][file]).read_text())
            for file in info["split"]["outer_test_files"]}
    observed = {}
    for node, attrs in graph.nodes(data=True):
        file = attrs["source_file"]
        if file not in maps:
            continue
        code = attrs["code"]
        revised, edits = rewrite_code(code, maps[file])
        if edits:
            observed[(file,node)] = (hashlib.sha256(code.encode()).hexdigest(),
                                     hashlib.sha256(revised.encode()).hexdigest(),len(edits))
    archived = {(r["file"],r["original_graph_node_id"]):
                (r["code_before_sha256"],r["code_after_sha256"],r["replacements"])
                for r in first["changed_nodes"]}
    if observed != archived:
        raise ValueError("Initial diagnostic text intervention differs from final implementation")
    code_refs = {p.name:sha256(p) for p in Path(__file__).parent.glob("*.py")}
    record = dict(version="prompt8c-inference-only-v1", training_count=0,
        plan=dict(path=str(plan_path),sha256=sha256(plan_path)),
        gate=dict(path=str(output/"gate.json"),sha256=sha256(output/"gate.json")),
        verification=dict(path=str(output.parent/"verification_v2/verification.json"),
                          sha256=sha256(output.parent/"verification_v2/verification.json")),
        code=code_refs,jobs=jobs,
        reused_initial_probe=dict(path=str(first_path),sha256=sha256(first_path),
            current_intervention_exact=True,nodes=len(observed),
            reason="Exact per-node rewritten text SHA matches final pydot lexical fix; unchanged model forward"),
        policy="serial fresh processes, eval/no_grad only, fail-stop; no optimizer, no retraining")
    write_new(output / "execution_plan.json",record)
    write_new(output / "execution_plan.seal.json",dict(sha256=sha256(output/"execution_plan.json")))
    return record


def execute(output):
    output=Path(output).resolve()
    planfile=output/"execution_plan.json"
    record=read(planfile)
    if sha256(planfile) != read(output/"execution_plan.seal.json")["sha256"]:
        raise ValueError("Inference plan changed")
    plan_path=checked_ref(record["plan"])
    checked_ref(record["gate"])
    checked_ref(record["verification"])
    # These files contain the executed path. Other diagnostic modules may
    # finish concurrently, but cannot change this controller/worker/helpers.
    for name in ("inference.py","inference_batch.py","common.py"):
        if sha256(Path(__file__).with_name(name)) != record["code"][name]:
            raise ValueError("Inference implementation changed")
    statuses=[]
    for i,job in enumerate(record["jobs"]):
        name="{task_id}_{fold}_{profile}".format(**job)
        target=output/"jobs"/(name+".json")
        if target.exists():
            row=read(target)
            if row["job"] != job or row["plan_sha256"] != record["plan"]["sha256"]:
                raise ValueError("Existing diagnostic identity mismatch")
            if str(target) == record["reused_initial_probe"]["path"]:
                checked_ref(record["reused_initial_probe"])
            elif row.get("implementation_sha256") != record["code"]["inference.py"]:
                raise ValueError("Existing diagnostic implementation differs")
            print("reused %d/100 %s"%(i+1,name),flush=True)
            continue
        command=[sys.executable,"-B","-m","scripts.DFG.dfg_v2.diagnostics8c.inference",
            "--plan",str(plan_path),"--task",job["task_id"],"--fold",str(job["fold"]),
            "--profile",job["profile"],"--gate",record["gate"]["path"],"--out",str(target)]
        log=output/"logs"/(name+".log");log.parent.mkdir(exist_ok=True)
        started=time.monotonic()
        with log.open("x") as stream:
            process=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
        status=dict(job=job,returncode=process.returncode,seconds=time.monotonic()-started,
                    command=command,log_sha256=sha256(log))
        write_new(output/"status"/(name+".json"),status)
        statuses.append(status)
        if process.returncode:
            raise RuntimeError("Diagnostic worker failed; no automatic retry: "+name)
        print("inferred %d/100 %s %.1fs"%(i+1,name,status["seconds"]),flush=True)
    write_new(output/"execution_complete.json",dict(jobs=100,new_statuses=statuses,training_count=0))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["prepare","execute"])
    parser.add_argument("--out",required=True)
    parser.add_argument("--plan")
    args=parser.parse_args()
    if args.action=="prepare":prepare(args.plan,args.out)
    else:execute(args.out)
