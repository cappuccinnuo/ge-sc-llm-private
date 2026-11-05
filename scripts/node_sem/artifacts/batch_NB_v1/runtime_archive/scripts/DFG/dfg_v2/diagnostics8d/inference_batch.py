"""Exclusive serial inference-only plan for the three approved Prompt8D views."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from scripts.DFG.dfg_v2.diagnostics8c.common import read, write_new, checked_plan
from scripts.DFG.integration.io import sha256
from scripts.DFG.dfg_v2.tasks import checked_ref
from .prepared import MODES, ref

BOUND_CODE = ("inference.py", "inference_batch.py", "prepared.py", "renaming.py")


def expected_jobs(plan):
    node_jobs = [j for j in plan["jobs"] if plan["tasks"][j["task_id"]]["record"]["task"] == "node"]
    keys = [(j["task_id"], j["fold"], j["seed"], j["profile"]) for j in node_jobs]
    if len(keys) != 100 or len(set(keys)) != 100:
        raise ValueError("Expected original complete 100-model node matrix")
    return [dict(mode=mode, job=job) for mode in MODES for job in node_jobs]


def prepare(plan_path, prepared_path, old_root, output, approval_path):
    plan_path, prepared_path, old_root, output, approval_path = map(Path,
        (plan_path, prepared_path, old_root, output, approval_path))
    plan = checked_plan(plan_path)
    approval = read(approval_path)
    if approval.get("approved_inference_jobs") != 300 or approval.get("formal_training_authorized") is not False:
        raise ValueError("Three-view inference approval missing")
    prepared = read(prepared_path)
    if prepared["source_plan"] != ref(plan_path):
        raise ValueError("Prepared graph/token plan differs")
    if sha256(prepared_path) != read(prepared_path.with_name("manifest.seal.json"))["sha256"]:
        raise ValueError("Prepared token seal differs")
    gate_path = old_root / "D/gate.json"
    verification_path = old_root / "verification_v2/verification.json"
    gate, verification = read(gate_path), read(verification_path)
    if not gate.get("archive_parity", {}).get("passed") or gate["plan_sha256"] != sha256(plan_path):
        raise ValueError("Unmodified archive parity gate missing")
    if verification["verified"] != 150 or verification["plan_sha256"] != sha256(plan_path):
        raise ValueError("Historical complete150 verification missing")
    current_gate_path = output.parent / "current_identity_gate.json"
    current_gate = read(current_gate_path)
    if (not current_gate.get("archive_parity", {}).get("passed")
            or current_gate.get("plan_sha256") != sha256(plan_path)
            or current_gate.get("gate_only") is not True):
        raise ValueError("Current environment archive parity gate failed")
    output.mkdir(parents=True, exist_ok=False)
    record = dict(current_environment_gate=ref(current_gate_path), version="prompt8d-serial-inference-v1", source_plan=ref(plan_path),
        prepared=ref(prepared_path), gate=ref(gate_path), verification=ref(verification_path),
        approval=ref(approval_path), training_count=0, optimizer_steps=0,
        code={n:sha256(Path(__file__).with_name(n)) for n in BOUND_CODE},
        old_worker=ref(Path(__file__).parent.parent/"diagnostics8c/inference.py"),
        jobs=expected_jobs(plan), policy="one GPU process; error stops, no automatic retry or CPU fallback")
    write_new(output/"execution_plan.json", record)
    write_new(output/"execution_plan.seal.json", dict(sha256=sha256(output/"execution_plan.json")))
    return record


def validate_completed(report, job, mode, record):
    if (report.get("job") != job or report.get("intervention") != mode
            or report.get("plan_sha256") != record["source_plan"]["sha256"]
            or report.get("implementation_sha256") != record["code"]["inference.py"]
            or report.get("gate_sha256") != record["gate"]["sha256"]
            or report.get("prepared", {}).get("manifest") != record["prepared"]
            or report.get("optimizer_steps") != 0):
        raise ValueError("Existing inference identity/binding mismatch")
    for flag in ("weights_unchanged", "graph_edges_unchanged",
                 "unchanged_features_verified", "frozen_nx_attributes_untouched"):
        if report.get(flag) is not True:
            raise ValueError("Inference invariant failed: " + flag)


def execute(output):
    output=Path(output).resolve()
    plan_path=output/"execution_plan.json"
    record=read(plan_path)
    if sha256(plan_path) != read(output/"execution_plan.seal.json")["sha256"]:
        raise ValueError("Inference execution seal mismatch")
    for key in ("source_plan", "prepared", "gate", "verification", "approval", "old_worker", "current_environment_gate"):
        checked_ref(record[key])
    for name, expected in record["code"].items():
        if sha256(Path(__file__).with_name(name)) != expected:
            raise ValueError("Inference implementation changed: " + name)
    if record["jobs"] != expected_jobs(checked_plan(record["source_plan"]["path"])):
        raise ValueError("Inference job list changed")
    records=[]
    for index, item in enumerate(record["jobs"]):
        job, mode=item["job"], item["mode"]
        name="{task_id}_{fold}_{profile}".format(**job)
        folder=output/mode
        target=folder/"jobs"/(name+".json")
        status_path=folder/"status"/(name+".json")
        if target.exists():
            report=read(target)
            validate_completed(report, job, mode, record)
            status=read(status_path)
            if status["returncode"] != 0 or status["result"] != ref(target):
                raise ValueError("Existing success receipt differs")
            records.append(status)
            print("reused %d/300 %s/%s"%(index+1,mode,name),flush=True)
            continue
        if status_path.exists() or (folder/"logs"/(name+".log")).exists():
            raise RuntimeError("Previous attempt exists; no implicit retry: "+mode+"/"+name)
        command=[sys.executable,"-B","-m","scripts.DFG.dfg_v2.diagnostics8d.inference",
            "--plan",record["source_plan"]["path"],"--prepared",record["prepared"]["path"],
            "--task",job["task_id"],"--fold",str(job["fold"]),"--profile",job["profile"],
            "--mode",mode,"--gate",record["gate"]["path"],"--out",str(target)]
        log=folder/"logs"/(name+".log");log.parent.mkdir(parents=True,exist_ok=True)
        started=time.monotonic()
        with log.open("x") as stream:
            process=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
        status=dict(job=job,mode=mode,command=command,returncode=process.returncode,
                    seconds=time.monotonic()-started,log=ref(log))
        if process.returncode == 0:
            validate_completed(read(target),job,mode,record)
            status["result"]=ref(target)
        write_new(status_path,status)
        records.append(status)
        if process.returncode:
            raise RuntimeError("Diagnostic worker failed; no retry: "+mode+"/"+name)
        print("inferred %d/300 %s/%s %.1fs"%(index+1,mode,name,status["seconds"]),flush=True)
    write_new(output/"execution_complete.json",dict(jobs=300,statuses=records,
        training_count=0,optimizer_steps=0,plan=ref(plan_path)))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("prepare","execute"))
    p.add_argument("--out",required=True)
    for name in ("plan","prepared","old-root","approval"):
        p.add_argument("--"+name)
    a=p.parse_args()
    if a.action=="prepare":
        prepare(a.plan,a.prepared,a.old_root,a.out,a.approval)
    else:
        execute(a.out)
