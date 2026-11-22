"""Resume only authorized exact inverses, using a byte-verified, read-only canonical solc input for single files."""
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict
from multiprocessing import get_context
import os
from pathlib import Path
import sys
import time

from audit_samples import json_lines, key
from batch import LOCAL, OUT, checked, json, load, receipt_rows, receipt_stream, save, sha
from inverse_scores import inverse
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.benchmark import (
    _materialize_closure, base_contents, environment_observation, score_graphs)
from compile_repair.pipeline import repair_unit
from compile_repair.rules.environment import mando_known_version
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers

BATCH="identity_continuation/"


def setup():
    global BASES, GROUPS, CONTROLS, OLD_GRAPHS, COMPILERS, VERSIONS, AUTH, FAILED
    AUTH=load("restoration_identity_authorization.json")
    checked(OUT/"restoration_identity_request.json",AUTH["request_sha256"])
    stopped=load("inverse_acceptance.json")
    assert not stopped["passed"]
    FAILED=(AUTH["probe_operator"],AUTH["probe_unit"])
    assert key(stopped["first_failure"])==FAILED
    checked(OUT/"inverse_scores.jsonl",stopped["scores_sha256"])
    checked(OUT/"inverse_graphs.jsonl",stopped["graphs_sha256"])
    BASES={r["unit_id"]:r for r in receipt_rows("bases.jsonl.gz")}
    CONTROLS={r["unit_id"]:r for r in json_lines(OUT/"controls.jsonl")}
    OLD_GRAPHS={r["unit_id"]:r for r in json_lines(OUT/"inverse_graphs.jsonl")
                if r["truth_graph_sha256"]==r["graph_sha256"]}
    passing={key(s) for s in json_lines(OUT/"inverse_scores.jsonl") if s["score"]["exact"]}
    assert len(passing)==AUTH["reuse_original_passing_scores"]
    GROUPS=defaultdict(list)
    for sample in json_lines(OUT/"sample_receipts.jsonl"):
        if sample["outcome"]=="included" and key(sample) not in passing:
            GROUPS[sample["unit_id"]].append(sample)
    assert sum(map(len,GROUPS.values()))==AUTH["approved_remaining_total_including_probe"]
    check_profile("production")
    COMPILERS,VERSIONS,_=load_trusted_compilers()


def read_result(base,folder,kind):
    path=folder/"result.json"
    record=json.loads(path.read_bytes());attempt=record["attempts"][-1]
    assert (record["status"],record["selected_version"],record["settings"])==("success",base["version"],base["settings"])
    assert attempt["solc"]["returncode"]==0 and attempt["slither"]["d3"]
    graph_sha=attempt["slither"]["graph_sha256"]
    graph=json.loads(checked(folder/"graph.json",graph_sha))
    receipt=dict(unit_id=base["unit_id"],graph_source=kind,result_path=str(path),result_sha256=sha(path.read_bytes()),
                 graph_sha256=graph_sha,truth_graph_sha256=base["graph_sha256"],solc_returncode=0,d3=True,
                 compiler=base["version"],settings=base["settings"])
    return graph,receipt


def observe(base,repaired):
    uid=base["unit_id"]
    if uid in OLD_GRAPHS:
        ref=OLD_GRAPHS[uid]
        checked(ref["result_path"],ref["result_sha256"])
        return read_result(base,Path(ref["result_path"]).parent,"previous_passed_inverse")
    if uid in CONTROLS:
        row=CONTROLS[uid]
        assert row["passed"] and row["actual_graph_sha256"]==base["graph_sha256"]
        checked(row["result_path"],row["result_sha256"])
        return read_result(base,Path(row["result_path"]).parent,"independently_recompiled_cp4_control")

    store=ArtifactStore(LOCAL/"identity_continuation"/uid)
    entry,project=_materialize_closure(base,repaired,store,"inverse")
    with store.journal("invocations.jsonl") as journal:
        if project is not None:
            environment_observation(base,entry,project,COMPILERS,VERSIONS,store,journal,"inverse")
            return read_result(base,store.path/"units/inverse","compiled_from_inverse_project")

        history_path=Path(base["result"]["result_path"])
        historical=json.loads(checked(history_path,base["result"]["result_sha256"]))
        last=historical["attempts"][-1]
        canon=Path(last["slither"]["command"]["target"])
        expected=last["solc"]["source_sha256"]
        assert last["solc"]["source_path"]==str(canon)
        checked(canon,expected)
        checked(base["graph_path"],base["graph_sha256"])
        raw=entry.read_bytes()
        assert raw==repaired[""]
        mode="mando" if base["corpus"]=="MANDO" else None
        known=mando_known_version(raw,VERSIONS)[0] if mode else None
        unit=CompilationUnit("inverse",(SourceFile(str(entry),sha(raw),raw,base["kind"]),),known,mode)
        comparisons=[]

        def compile_at_truth_name(working,compiler,settings=()):
            data=Path(working).read_bytes()
            if checked(canon,expected)!=data:
                raise ValueError("Historical compiler target differs from the actual inverse working bytes: "+uid)
            result=compile_file(canon,compiler,settings=settings)
            assert result.source_sha256==expected and Path(working).read_bytes()==checked(canon,expected)
            comparisons.append(dict(inverse_working_path=str(working),canonical_input=str(canon),
                sha256=expected,version=compiler.version,settings=list(settings),bytes_equal_before_and_after=True))
            return result

        record=repair_unit(unit,COMPILERS,store,journal,compile_fn=compile_at_truth_name)
        assert record.status=="success" and comparisons
        observed=record.attempts[-1]
        assert observed["solc"]["command"]==last["solc"]["command"] or tuple(observed["solc"]["command"])==tuple(last["solc"]["command"])
        assert observed["slither"]["command"]["target"]==str(canon)
        assert checked(canon,expected)==Path(comparisons[-1]["inverse_working_path"]).read_bytes()
        checked(history_path,base["result"]["result_sha256"]);checked(base["graph_path"],base["graph_sha256"])
        binding=store.write_json("canonical_source.json",dict(unit_id=uid,record_path=str(history_path),
            record_sha256=base["result"]["result_sha256"],history_graph_sha256=base["graph_sha256"],
            source_comparisons=comparisons,old_command_equal=True))
    graph,receipt=read_result(base,store.path/"units/inverse","compiled_from_verified_canonical_inverse")
    receipt.update(binding_path=str(binding),binding_sha256=sha(binding.read_bytes()))
    return graph,receipt


def measured(uid,samples,existing=None):
    base=BASES[uid];original=base_contents(base)
    truth=json.loads(checked(base["graph_path"],base["graph_sha256"]))
    graph=receipt=None
    if existing:
        result=Path(existing["result_path"])
        checked(result,existing["result_sha256"])
        graph=json.loads(checked(result.with_name("graph.json"),existing["graph_sha256"]))
        receipt=existing
    scores=[]
    for row in samples:
        damaged,repaired,first,second=inverse(base,original,row)
        if graph is None:graph,receipt=observe(base,repaired)
        score=score_graphs(truth,graph,original,damaged,repaired,first,second,receipt["solc_returncode"],receipt["d3"])
        item=dict(unit_id=uid,operator=row["operator"],score=score,mutation_sha256=row["mutation_sha256"],
                  actual_graph_sha256=receipt["graph_sha256"])
        scores.append(item)
        if not score["exact"]:break
    return receipt,scores


def probe():
    uid=FAILED[1];row=next(r for r in GROUPS[uid] if key(r)==FAILED)
    try:
        graph,scores=measured(uid,[row])
        truth=Path(BASES[uid]["graph_path"]);actual=Path(graph["result_path"]).with_name("graph.json")
        equal=truth.read_bytes()==actual.read_bytes()
        passed=equal and scores[0]["score"]["exact"]
        receipt=dict(passed=passed,graph_bytes_equal=equal,graph=graph,score=scores[0])
    except Exception as exc:
        receipt=dict(passed=False,exception=type(exc).__name__,message=str(exc))
    save(BATCH+"probe.json",receipt)
    print("same-path probe",receipt["passed"],flush=True)
    return 0 if receipt["passed"] else 2


def remaining_unit(uid):
    samples=[r for r in GROUPS[uid] if key(r)!=FAILED]
    return measured(uid,samples,PROBE["graph"] if uid==FAILED[1] else None)


def continuation():
    global PROBE
    PROBE=load(BATCH+"probe.json")
    assert PROBE["passed"] and PROBE["graph_bytes_equal"] and PROBE["score"]["score"]["exact"]
    schedule=iter(sorted(uid for uid,rows in GROUPS.items() if any(key(r)!=FAILED for r in rows)))
    workers=min(5,len(os.sched_getaffinity(0)))
    start=time.monotonic();scored=bases=1;failure=None
    with receipt_stream(BATCH+"scores.jsonl.gz") as scores,receipt_stream(BATCH+"graphs.jsonl.gz") as graphs:
        scores(PROBE["score"]);graphs(PROBE["graph"])
        with ProcessPoolExecutor(max_workers=workers,mp_context=get_context("fork")) as pool:
            pending={}
            def submit():
                uid=next(schedule,None)
                if uid is not None:pending[pool.submit(remaining_unit,uid)]=uid
            for _ in range(workers):submit()
            while pending:
                done,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in done:
                    uid=pending.pop(future)
                    try:
                        graph,items=future.result()
                    except Exception as exc:
                        if failure is None:failure=dict(unit_id=uid,exception=type(exc).__name__,message=str(exc))
                    else:
                        if uid!=FAILED[1]:
                            graphs(graph);bases+=1
                        for item in items:
                            scores(item);scored+=1
                            if not item["score"]["exact"] and failure is None:failure=item
                        if bases%500==0:print("bases",bases,"scores",scored,flush=True)
                if failure is None:
                    for _ in done:submit()
    expected=AUTH["approved_remaining_total_including_probe"]
    passed=failure is None and scored==expected and bases==len(GROUPS)
    save(BATCH+"acceptance.json",dict(passed=passed,expected=expected,scored=scored,bases=bases,
         previous_passes=AUTH["reuse_original_passing_scores"],first_failure=failure,workers=workers,
         scores_sha256=sha((OUT/BATCH/"scores.jsonl.gz").read_bytes()),
         graphs_sha256=sha((OUT/BATCH/"graphs.jsonl.gz").read_bytes()),
         elapsed_seconds=round(time.monotonic()-start,3)))
    print("continuation",scored,"of",expected,"passed",passed,"failure",failure,flush=True)
    return 0 if passed else 2


if __name__=="__main__":
    setup()
    if sys.argv[1]=="--probe":sys.exit(probe())
    if sys.argv[1]=="--continue":sys.exit(continuation())
    raise ValueError("Expected --probe or --continue")
