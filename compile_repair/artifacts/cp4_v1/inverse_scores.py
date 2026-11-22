"""Invert each actual sampled edit and score against an independently observed repaired graph."""
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from collections import defaultdict
from multiprocessing import get_context
import os
from pathlib import Path
import sys
import time

from batch import BASE, LOCAL, OUT, ROOT, checked, json, load, receipt_rows, save, sha
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore, emit
from compile_repair.evaluation.benchmark import (
    _materialize_closure, base_contents, environment_observation, score_graphs)
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers


def inverse(base, source, sample):
    path=Path(sample["mutation_path"])
    manifest=json.loads(checked(path,sample["mutation_sha256"]))
    assert manifest["base_unit"]==base["unit_id"] and manifest["operator"]==sample["operator"]
    assert manifest["original_sha256"]=={n:sha(data) for n,data in source.items()}
    edit=manifest["edit"];name=edit["file"];a,b=edit["start"],edit["end"]
    old=source[name][a:b]
    assert sha(old)==edit["original_bytes_sha256"]
    new=checked(edit["new_bytes_path"],edit["new_bytes_sha256"])
    data,damage=apply_patches(source[name],[Patch(a,b,old,new,sample["operator"])])
    damaged=dict(source)
    if edit["action"]=="delete_file":
        assert not data and not (path.parent/"damaged"/name).exists()
        del damaged[name]
    else:
        damaged[name]=data
    assert {n:sha(raw) for n,raw in damaged.items()}==manifest["damaged_sha256"]
    for n,h in manifest["damaged_sha256"].items():
        checked(path.parent/"damaged"/(n or "input.sol"),h)
    restored,repair=apply_patches(data,[Patch(a,a+len(new),new,old,"inverse")])
    repaired=dict(damaged);repaired[name]=restored
    assert repaired==source
    return damaged,repaired,{name:damage},{name:repair}


def graph_after_inverse(base, repaired):
    uid=base["unit_id"]
    if uid in CONTROLS:
        row=CONTROLS[uid]
        assert row["passed"] and row["actual_graph_sha256"]==base["graph_sha256"]
        rec=Path(row["result_path"]);m=json.loads(checked(rec,row["result_sha256"]))
        graph_sha=row["actual_graph_sha256"];kind="independently_recompiled_cp4_control"
    else:
        store=ArtifactStore(LOCAL/"exact"/uid)
        path,project=_materialize_closure(base,repaired,store,"inverse")
        with store.journal("invocations.jsonl") as journal:
            result=environment_observation(base,path,project,COMPILERS,VERSIONS,store,journal,"inverse")
        rec=store.path/"units/inverse/result.json";m=json.loads(rec.read_bytes())
        if result.status!="success":
            raise ValueError("Byte-exact restored source failed its environment run: "+str(rec))
        graph_sha=m["attempts"][-1]["slither"]["graph_sha256"];kind="compiled_from_inverse"
    att=m["attempts"][-1]
    assert m["selected_version"]==base["version"] and m["settings"]==base["settings"] and att["solc"]["returncode"]==0
    assert att["slither"]["d3"] and graph_sha==att["slither"]["graph_sha256"]
    actual=json.loads(checked(rec.with_name("graph.json"),graph_sha))
    receipt=dict(unit_id=uid,graph_source=kind,result_path=str(rec),result_sha256=sha(rec.read_bytes()),
                 graph_sha256=graph_sha,truth_graph_sha256=base["graph_sha256"],solc_returncode=att["solc"]["returncode"],
                 d3=att["slither"]["d3"],compiler=base["version"],settings=base["settings"])
    return actual,receipt


def task(uid):
    base=BASES[uid];original=base_contents(base)
    truth=json.loads(checked(base["graph_path"],base["graph_sha256"]))
    actual=None;checks=[]
    for sample in GROUPS[uid]:
        damaged,repaired,first,second=inverse(base,original,sample)
        if actual is None:
            actual,receipt=graph_after_inverse(base,repaired)
        score=score_graphs(truth,actual,original,damaged,repaired,first,second,receipt["solc_returncode"],receipt["d3"])
        checks.append(dict(unit_id=uid,operator=sample["operator"],score=score,
                           mutation_sha256=sample["mutation_sha256"],actual_graph_sha256=receipt["graph_sha256"]))
        if not score["exact"]:
            break
    return receipt,checks


def main():
    global BASES, CONTROLS, GROUPS, COMPILERS, VERSIONS
    run=load("execution.json")
    assert run["completed"]==run["planned"] and run["first_exception"] is None
    assert sha((OUT/"sample_receipts.jsonl").read_bytes())==run["receipt_sha256"]
    check_profile("production");COMPILERS,VERSIONS,_=load_trusted_compilers()
    BASES={r["unit_id"]:r for r in receipt_rows("bases.jsonl.gz")}
    CONTROLS={r["unit_id"]:r for r in (json.loads(l) for l in (OUT/"controls.jsonl").open())}
    GROUPS=defaultdict(list)
    for row in (json.loads(l) for l in (OUT/"sample_receipts.jsonl").open()):
        if row["outcome"]=="included":
            GROUPS[row["unit_id"]].append(row)
    schedule=iter(sorted(GROUPS))
    expected=sum(map(len,GROUPS.values()));workers=min(5,len(os.sched_getaffinity(0)))
    start=time.monotonic();tested=0;bases=0;failure=None
    with (OUT/"inverse_scores.jsonl").open("x") as scores,(OUT/"inverse_graphs.jsonl").open("x") as graphs:
        with ProcessPoolExecutor(max_workers=workers,mp_context=get_context("fork")) as pool:
            pending={}
            def submit():
                uid=next(schedule,None)
                if uid is not None:pending[pool.submit(task,uid)]=uid
            for _ in range(workers):submit()
            while pending:
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    uid=pending.pop(future)
                    try:
                        receipt,checks=future.result()
                    except Exception as exc:
                        if failure is None:failure=dict(unit_id=uid,type=type(exc).__name__,message=str(exc))
                    else:
                        emit(graphs,receipt);bases+=1
                        for row in checks:
                            emit(scores,row);tested+=1
                            if not row["score"]["exact"] and failure is None:failure=row
                        if bases%500==0:print("bases",bases,"scores",tested,flush=True)
                if failure is None:
                    for _ in done:submit()
    save("inverse_acceptance.json",dict(expected=expected,scored=tested,unique_bases=bases,passed=(failure is None and expected==tested),
         first_failure=failure,elapsed_seconds=round(time.monotonic()-start,3),workers=workers,
         scores_sha256=sha((OUT/"inverse_scores.jsonl").read_bytes()),graphs_sha256=sha((OUT/"inverse_graphs.jsonl").read_bytes())))
    print("scored",tested,"expected",expected,"failure",failure,flush=True)
    return 0 if failure is None and tested==expected else 2


if __name__=="__main__":
    sys.exit(main())
