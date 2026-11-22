"""Run the fixed unmodified controls once, stopping on the first unequal observation."""
import subprocess
import time
from dataclasses import asdict
from batch import BASE, HERE, LOCAL, OUT, ROOT, checked, json, load, save, sha
from compile_repair.core.store import ArtifactStore, emit
from compile_repair.evaluation.benchmark import control_observation
from compile_repair.toolchain.solc import load_trusted_compilers
from compile_repair.toolchain.slither import check_profile

start=time.monotonic()
plan=load("control_plan.json")
assert len(plan["units"])==len({r["unit_id"] for r in plan["units"]})==200
tools=check_profile("production")
compilers, frozen_versions, trust=load_trusted_compilers()
store=ArtifactStore(LOCAL/"controls")
rows=[]; stop=None
with store.journal("invocations.jsonl") as journal,(OUT/"controls.jsonl").open("x",encoding="utf8") as receipts:
    for row in plan["units"]:
        try:
            result=control_observation(row,compilers,frozen_versions,store,journal)
        except Exception as exc:
            result=dict(unit_id=row["unit_id"],corpus=row["corpus"],passed=False,exception=type(exc).__name__,message=str(exc))
        rows.append(result);emit(receipts,result)
        if not result["passed"]:
            stop=result;break
        if len(rows)%25==0:print("controls",len(rows),flush=True)
implementation={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in (ROOT/"compile_repair").rglob("*.py")
                if not {"artifacts","tests"}&set(p.relative_to(ROOT).parts)}
seal=store.seal(dict(tools,compilers={k:asdict(v) for k,v in compilers.items()},trust=trust),BASE,implementation)
status="stop_control_mismatch" if stop else "complete"
save("control_acceptance.json",dict(status=status,expected=200,attempted=len(rows),passed=sum(r["passed"] for r in rows),
     first_mismatch=stop,plan_sha256=sha((OUT/"control_plan.json").read_bytes()),
     receipts_sha256=sha((OUT/"controls.jsonl").read_bytes()),external_seal_path=str(store.path/"seal.json"),
     external_seal_sha256=sha((store.path/"seal.json").read_bytes()),elapsed_seconds=round(time.monotonic()-start,3)))
print(status,len(rows),stop,flush=True)
raise SystemExit(2 if stop else 0)
