"""Explicit Prompt 8H cache-only runtime amendment; never rewrites a plan seal."""
from pathlib import Path
from .prepare import read,ref,checked
from .protocol import PROTOCOL_NAME

VERSION="prompt8h-cache-runtime-amendment-v1"
NAME="runtime_cache_fix_v1.json"
EXECUTION="scripts/DFG/dfg_v2/benchmark_v2/execution.py"
ADDITIONS={
 "scripts/DFG/dfg_v2/benchmark_v2/acceptance_cache.py",
 "scripts/DFG/dfg_v2/benchmark_v2/runtime_amendment.py",
}

def _cache_amendment_ref(plan_path,plan,actual=None):
    if actual is None:
        from ..experiment.run import _code_refs
        actual=_code_refs()
    if actual==plan["runtime"]:
        return None
    path=Path(plan_path).parent/NAME
    if not path.is_file():
        raise ValueError("Frozen runtime differs without approved cache amendment")
    doc=read(path)
    seal=read(path.with_name(path.stem+".seal.json"))
    if seal.get("amendment")!=ref(path):
        raise ValueError("Runtime amendment seal differs")
    if doc.get("version")!=VERSION or doc.get("plan")!=ref(plan_path):
        raise ValueError("Runtime amendment plan/version differs")
    if plan.get("protocol")!=PROTOCOL_NAME or doc.get("runtime")!=actual:
        raise ValueError("Runtime differs from approved cache amendment")
    old=plan["runtime"]
    changed={name for name in old if actual.get(name)!=old[name]}
    added=set(actual)-set(old)
    if changed!={EXECUTION} or added!=ADDITIONS:
        raise ValueError("Cache amendment cannot change numerical or unrelated source")
    before=checked(doc["before_execution"])
    if doc["before_execution"]["sha256"]!=old[EXECUTION]:
        raise ValueError("Original executor evidence differs")
    if doc.get("plan_seal")!=ref(Path(plan_path).with_name("plan.seal.json")):
        raise ValueError("Original plan seal differs")
    approval=read(checked(doc["approval"]))
    if (approval.get("plan")!=ref(plan_path) or approval.get("approved") is not True
        or approval.get("new_fits")!=169 or approval.get("reuse_existing_fit") is not True):
        raise ValueError("Cache repair/resume authorization differs")
    proof=read(checked(doc["proof"]))
    if (proof.get("passed") is not True or proof.get("runtime")!=actual
        or proof.get("numeric_functions_unchanged") is not True):
        raise ValueError("Cache repair proof/runtime differs")
    if len(doc.get("legacy_successes",[]))!=1:
        raise ValueError("Exactly the pre-amendment successful fit may be reused")
    for entry in doc["legacy_successes"]:
        checked(entry)
    return ref(path)

def amendment_ref(plan_path,plan,actual=None):
    if actual is None:
        from ..experiment.run import _code_refs
        actual=_code_refs()
    from .retry import NAME as RESUME_NAME,verify_resume
    if (Path(plan_path).parent/RESUME_NAME).is_file():
        return verify_resume(plan_path,plan,actual,_cache_amendment_ref)
    return _cache_amendment_ref(plan_path,plan,actual)

def verify_start(plan_path,plan,start,receipt_path):
    current=amendment_ref(plan_path,plan)
    declared=start.get("benchmark_runtime_amendment")
    if current is not None:
        doc=read(checked(current))
        from .retry import VERSION as RESUME_VERSION
        if doc.get("version")==RESUME_VERSION and declared!=current:
            prior=read(checked(doc["prior_successes"]))
            if ref(receipt_path) not in prior["receipts"] or declared not in (None,doc["parent_amendment"]):
                raise ValueError("Fit lacks approved resume binding")
            return
    if current is None:
        if declared is not None:
            raise ValueError("Unexpected runtime amendment on original runtime")
        return
    if declared is None:
        doc=read(checked(current))
        if ref(receipt_path) not in doc["legacy_successes"]:
            raise ValueError("New fit lacks approved runtime binding")
    elif declared!=current:
        raise ValueError("Fit runtime amendment binding differs")
