"""CP2 exact 6c occurrence replay; frozen compiler/extractor imports only."""
import gzip
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from compile_repair.core.store import ArtifactStore,emit,sha256
from compile_repair.evaluation.survey import checked_json,SIX_C,REPORT_SHA,SEAL_SHA
from compile_repair.toolchain.solc import load_trusted_compilers,compile_file,verify_binary
from compile_repair.toolchain.slither import check_profile
from scripts.DFG.dfg_v2.validate_slither import _compile,slither_full_facts

OUT=Path(__file__).resolve().parent
ART=ROOT/"compile_repair/artifacts"


def occurrence_keys(extraction,target,source_sha):
    """Use the reviewed CP0 field list, retaining every duplicate occurrence."""
    counts=Counter()
    for row in extraction["occurrences"]:
        # Validate/bind filenames before projecting out path and source length.
        for field in ("function","node","declaration"):
            span=row.get(field)
            if span is not None and span.get("filename")!=target:
                raise ValueError("Unbound occurrence filename: "+repr(span))
        value=[row["layer"],row["function_name"],
               row["function"]["start"] if row["function"] else None,
               row["modifier"],row["context_contract"],row["context_declarer"],
               row["inherited_context"],row["node"]["start"] if row["node"] else None,
               row["declaration"]["start"] if row["declaration"] else None,
               row["canonical_name"],row["fact"],row["tags"]]
        counts[json.dumps([source_sha,value],sort_keys=True)]+=1
    return counts


def historical_target(reference):
    """Retain the exact input pathname recorded by 6c, after corpus binding."""
    extraction=reference["slither_extraction"]
    paths={span["filename"] for row in extraction["occurrences"]
           for field in ("function","node","declaration")
           for span in [row.get(field)] if span is not None}
    paths.update(row["source"]["filename"] for row in extraction["functions"] if row.get("source"))
    if len(paths)!=1:raise ValueError("6c target is not uniquely recorded")
    path=Path(next(iter(paths))).resolve()
    allowed=Path("/home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code").resolve()
    if allowed not in path.parents:raise ValueError("6c target outside original corpus")
    if sha256(path)!=reference["source_sha256"]:raise ValueError("6c original target changed")
    return path


def execute():
    assert Path.cwd()==ROOT
    profile=check_profile("regression_6c")
    report=checked_json(SIX_C/"slither_full/report.json",REPORT_SHA)
    seal=checked_json(SIX_C/"slither_full/report.seal.json",SEAL_SHA)
    assert seal["report_sha256"]==REPORT_SHA
    cp0=json.loads((ART/"cp0_v2/recon.json").read_text())
    lookup={(r["category"],r["file"],r["sha256"]):r for r in cp0["inputs"]}
    jobs=[]
    for task,data in sorted(report["tasks"].items()):
        for row in data["files"]:
            if row["status"]=="compared":
                source=lookup[(task[:-len("_contract")],row["file"],row["source_sha256"])]
                jobs.append((source,row))
    assert len(jobs)==239
    store=ArtifactStore(ART/"cp2_6c_v1")
    compilers,_,trust=load_trusted_compilers()
    store.write_json("plan.json",{"profile":profile,"cwd":str(ROOT),
        "report_sha256":REPORT_SHA,"seal_sha256":SEAL_SHA,
        "key_proposal":cp0["historical_comparison"]["cp2_key_proposal"],
        "jobs":[{"source":s["path"],"replay_source":str(historical_target(r)),"source_sha256":s["sha256"],"version":r["version"]} for s,r in jobs]})
    store.write_json("trust.json",trust)
    results=[];started=time.monotonic();status="running";error=None
    with store.journal("invocations.jsonl") as inv,store.journal("comparison.jsonl") as comparisons:
        try:
            for index,(source,reference) in enumerate(jobs,1):
                path=historical_target(reference);raw=path.read_bytes();digest=sha256(path)
                assert digest==reference["source_sha256"]
                compiler=compilers[reference["version"]]
                compiled=compile_file(path,compiler)
                emit(inv,dict(kind="solc",**asdict(compiled)))
                if compiled.returncode!=0 or compiled.timed_out:
                    raise ValueError("Exact 6c solc replay failed: "+source["path"])
                verify_binary(compiler)
                call=dict(profile,kind="slither",source_path=str(path),source_sha256=digest,
                    version=compiler.version,compiler_sha256=compiler.sha256,
                    command={"api":"validate_slither._compile; slither_full_facts","target":str(path),
                             "solc":compiler.path,"solc_disable_warnings":True},
                    preceding_observed_solc_returncode=compiled.returncode,
                    equivalent_solc_argv=compiled.command,api_subprocess_returncodes_observed=False,
                    cost_usd=0.0)
                begin=time.monotonic()
                try:
                    slither=_compile(path,compiler.path)
                    _,extraction=slither_full_facts(slither,path,raw)
                    call.update(constructed=True,counts=extraction["counts"],
                                comparability=extraction["comparability"],error_first_line=None)
                except Exception as exc:
                    call.update(constructed=False,exception_type=type(exc).__name__,
                                error_first_line=str(exc).splitlines()[0] if str(exc) else type(exc).__name__)
                    raise
                finally:
                    call["elapsed_seconds"]=time.monotonic()-begin
                    emit(inv,call)
                assert sha256(path)==digest
                verify_binary(compiler)
                old=reference["slither_extraction"]
                old_paths={span["filename"] for row in old["occurrences"]
                    for field in ("function","node","declaration") for span in [row.get(field)] if span is not None}
                if len(old_paths)>1:
                    raise ValueError("Historical paths cannot be uniquely bound")
                expected=occurrence_keys(old,next(iter(old_paths),str(path)),digest)
                actual=occurrence_keys(extraction,str(path),digest)
                raw_archive=json.dumps(extraction,sort_keys=True).encode("utf8")
                archive_path=store._target("extractions/{:04d}.json.gz".format(index))
                with archive_path.open("xb") as stream:
                    with gzip.GzipFile(filename="",mode="wb",fileobj=stream,mtime=0) as zipped:
                        zipped.write(raw_archive)
                comparison={"path":source["path"],"source_sha256":digest,"version":compiler.version,
                    "profile":"regression_6c","occurrences":sum(actual.values()),
                    "reference_occurrences":sum(expected.values()),"equal":actual==expected,
                    "comparability":extraction["comparability"],
                    "only_reference":dict(expected-actual),"only_replay":dict(actual-expected),
                    "extraction_sha256":hashlib.sha256(raw_archive).hexdigest()}
                emit(comparisons,comparison);results.append(comparison)
                print("REPLAY {}/239: {} {}".format(index,source["path"],"equal" if comparison["equal"] else "DIFFERENT"),flush=True)
                if not comparison["equal"]:
                    raise ValueError("6c occurrence multiset discrepancy")
            status="complete"
        except Exception as exc:
            status="stopped";error={"type":type(exc).__name__,"message":str(exc)}
    summary={"mode":"replay","status":status,"expected":239,"compared":len(results),
             "equal":sum(r["equal"] for r in results),"error":error,
             "elapsed_seconds":time.monotonic()-started,"cost_usd":0,"passed":status=="complete"}
    store.write_json("summary.json",summary)
    implementation=json.loads((OUT/"evidence_seal.json").read_text())["implementation_sha256"]
    store.seal(dict(profile,compilers={v:asdict(c) for v,c in compilers.items()}),
               json.loads((OUT/"baseline.json").read_text())["head"],implementation)
    print(json.dumps(summary),flush=True)
    if status!="complete":raise SystemExit(2)


if __name__=="__main__":
    execute()
