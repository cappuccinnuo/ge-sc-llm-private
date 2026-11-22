"""Execute the frozen CP4 plan once, with bounded in-flight work and an append-only receipt."""
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import multiprocessing
import os
import sys
import time

from batch import BASE, HERE, LOCAL, OUT, ROOT, SEED, json, load, receipt_rows, save, sha
from compile_repair.core.store import emit
from compile_repair.evaluation.benchmark import assess_mutation
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers
from plan_samples import sites_for


def perform(plan):
    base=BASES[plan["unit_id"]];op=plan["operator"]
    sources,sites=sites_for(base)
    if op not in sites:
        raise RuntimeError("Frozen applicability differs: "+op+"/"+base["unit_id"])
    out=LOCAL/"samples"/op/base["unit_id"]
    return assess_mutation(base,op,SEED,sources,sites[op],COMPILERS,VERSIONS,out)


def main():
    global BASES, COMPILERS, VERSIONS
    start=time.monotonic()
    profile=check_profile("production")
    COMPILERS,VERSIONS,trust=load_trusted_compilers()
    BASES={r["unit_id"]:r for r in receipt_rows("bases.jsonl.gz")}
    rows=list(receipt_rows("sample_plan.jsonl.gz"))
    sampling=load("sampling.json")
    assert len(rows)==len({(r["operator"],r["unit_id"]) for r in rows})==sampling["planned"]
    assert sha((OUT/"sample_plan.jsonl.gz").read_bytes())==sampling["plan_sha256"]
    assert load("control_acceptance.json")["passed"]==200 and not (LOCAL/"samples").exists()
    schedule=iter(sorted(rows,key=lambda r:sha((r["operator"]+":"+r["unit_id"]).encode())))
    workers=min(6,len(os.sched_getaffinity(0)))
    snapshot=LOCAL/"execution_source"
    snapshot.mkdir(parents=True)
    scripts={}
    for p in [ROOT/"compile_repair/evaluation/benchmark.py",HERE/"plan_samples.py",HERE/"run_samples.py"]:
        raw=p.read_bytes();(snapshot/p.name).write_bytes(raw);scripts[str(p.relative_to(ROOT))]=sha(raw)
    save("execution_settings.json",dict(profile=profile,compiler_trust=trust,workers=workers,code_commit=BASE,
         implementation=scripts,snapshot=str(snapshot),seed=SEED,scheduling="SHA256(operator:unit_id); bounded active sample count"))
    completed=0;failure=None
    with (OUT/"sample_receipts.jsonl").open("x",encoding="utf8") as stream:
        with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context("fork")) as pool:
            pending={}
            def submit():
                row=next(schedule,None)
                if row is not None:
                    pending[pool.submit(perform,row)]=row
            for _ in range(workers):
                submit()
            while pending:
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    row=pending.pop(future)
                    try:
                        obs=future.result()
                    except Exception as exc:
                        item=dict(row,exception=type(exc).__name__,message=str(exc))
                        if failure is None:
                            failure=item
                        emit(stream,dict(item,outcome="stopped_exception"))
                    else:
                        emit(stream,obs)
                        completed+=1
                        if completed%500==0:print(completed,"/",len(rows),round(time.monotonic()-start,1),flush=True)
                if failure is None:
                    for _ in done:submit()
    save("execution.json",dict(planned=len(rows),completed=completed,first_exception=failure,
         elapsed_seconds=round(time.monotonic()-start,3),receipt_sha256=sha((OUT/"sample_receipts.jsonl").read_bytes())))
    print("completed",completed,"first exception",failure,flush=True)
    return 2 if failure else 0


if __name__=="__main__":
    sys.exit(main())
