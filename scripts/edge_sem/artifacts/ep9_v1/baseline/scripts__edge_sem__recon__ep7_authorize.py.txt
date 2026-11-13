"""Write EP7 approvals only from a separately supplied explicit user record."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
from ..io import ROOT,read,write,ref,checked
from ..protocol_p2 import DECISIONS,require_registration_commit
from .. import execution as ex
from .ep7_common import OUT

def record(approval_file,registration_commit):
    request=read(approval_file)
    required=("D1_D2_D3_confirmed","gpu_probes_authorized","norm_pilot_authorized","formal_20_fits_authorized")
    if not request.get("user_request") or not all(request.get(k) is True for k in required):
        raise PermissionError("Explicit decisions and execution scopes are required")
    acceptance=read(OUT/"cpu_acceptance.json")
    if acceptance.get("passed") is not True or read(OUT/"cpu_acceptance.seal.json")["acceptance"]!=ref(OUT/"cpu_acceptance.json"):
        raise ValueError("CPU acceptance absent")
    if read(OUT/"sealed_plan_cpu.json").get("passed") is not True:raise ValueError("Sealed plan construction gate missing")
    registration=ROOT/"scripts/edge_sem/artifacts/protocol_p2/registration.json"
    require_registration_commit(ref(registration),registration_commit)
    decision=registration.with_name("decisions.json")
    value=dict(date=datetime.now(timezone.utc).isoformat(),user_request=request["user_request"],
        approval_record=ref(approval_file),decisions={k:dict(status="confirmed",value=v) for k,v in DECISIONS.items()})
    write(decision,value);write(decision.with_suffix(".seal.json"),dict(decisions=ref(decision)))
    for scope,previous in (("gpu_probes",()),("norm_pilot",("gpu_probes",)),("formal",("gpu_probes","norm_pilot"))):
        path=OUT/scope/"plan.json";plan=ex.load(path)
        value=dict(execution_authorized=True,user_request=request["user_request"],
            approval_record=ref(approval_file),date=value["date"],scope=scope,
            plan=ref(path),jobs=[ex.job_id(j) for j in plan["jobs"]],decisions=ref(decision),
            registration_commit=registration_commit,
            prerequisites=[ref(OUT/name/"plan.json") for name in previous],
            cpu_acceptance=ref(OUT/"cpu_acceptance.json"),sealed_plan_cpu=ref(OUT/"sealed_plan_cpu.json"),
            automatic_retry=False)
        approval=path.with_name("execution_authorization.json")
        write(approval,value);write(approval.with_suffix(".seal.json"),dict(authorization=ref(approval)))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--approval-file",required=True);p.add_argument("--registration-commit",required=True)
    a=p.parse_args();record(a.approval_file,a.registration_commit)
