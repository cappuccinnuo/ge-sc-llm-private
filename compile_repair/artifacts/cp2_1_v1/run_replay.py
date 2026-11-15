"""CP2.1 D20 replay; fixed main order and exactly ten new-process samples."""
import gzip
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import sys
import time
import subprocess

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



def ranges(expected, samples):
    """D20 only: all eleven multiplicities, including absent keys as zero."""
    if len(samples) != 11:
        raise ValueError("D20 requires main plus exactly ten additional samples")
    keys = set(expected)
    for sample in samples:
        keys.update(sample)
    unstable, failures = [], []
    stable_count = 0
    for key in sorted(keys):
        counts = [sample.get(key, 0) for sample in samples]
        lo, hi = min(counts), max(counts)
        ref = expected.get(key, 0)
        row = dict(key=key, counts=counts, minimum=lo, maximum=hi, reference=ref)
        if lo == hi:
            stable_count += 1
            if ref != lo:
                row["reason"] = "reference_only" if hi == 0 else "stable_mismatch"
                failures.append(row)
        else:
            _, fields = json.loads(key)
            row.update(layer=fields[0], function_name=fields[1], inherited_context=fields[6],
                       kind=fields[10][2], context_contract=fields[4], context_declarer=fields[5])
            unstable.append(row)
            if not lo <= ref <= hi:
                failures.append(dict(row, reason="outside_observed_range"))
    return dict(passed=not failures, samples=11, stable_keys=stable_count,
                unstable_keys=unstable, failing_keys=failures)


def archive_extraction(store, relative, extraction):
    raw = json.dumps(extraction, sort_keys=True).encode("utf8")
    with store._target(relative).open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as zipped:
            zipped.write(raw)
    return hashlib.sha256(raw).hexdigest()


def sample(request_path, destination):
    """One child process owns all ten extractions; never rerun or resample."""
    assert Path.cwd() == ROOT
    request = json.loads(Path(request_path).read_text())
    assert request["sample_count"] == 10
    profile = check_profile("regression_6c")
    compilers, _, trust = load_trusted_compilers()
    compiler = compilers[request["version"]]
    assert compiler.sha256 == request["compiler_sha256"]
    path = Path(request["path"])
    raw = path.read_bytes()
    assert sha256(path) == request["source_sha256"]
    store = ArtifactStore(destination)
    store.write_json("request.json", request)
    store.write_json("trust.json", trust)
    results = []
    error = None
    with store.journal("invocations.jsonl") as inv:
        try:
            for index in range(1, 11):
                compiled = compile_file(path, compiler)
                emit(inv, dict(kind="solc", sample=index, **asdict(compiled)))
                if compiled.returncode != 0 or compiled.timed_out:
                    raise ValueError("Additional sample solc failure")
                verify_binary(compiler)
                call = dict(profile, kind="slither", sample=index, source_path=str(path),
                    source_sha256=request["source_sha256"], version=compiler.version,
                    compiler_sha256=compiler.sha256, settings=compiled.settings, cwd=str(ROOT),
                    command={"api":"validate_slither._compile; slither_full_facts", "target":str(path),
                             "solc":compiler.path, "solc_disable_warnings":True},
                    preceding_observed_solc_returncode=compiled.returncode,
                    equivalent_solc_argv=compiled.command, api_subprocess_returncodes_observed=False,
                    cost_usd=0.0)
                begin = time.monotonic()
                try:
                    slither = _compile(path, compiler.path)
                    _, extraction = slither_full_facts(slither, path, raw)
                    call.update(constructed=True, counts=extraction["counts"],
                                comparability=extraction["comparability"])
                except Exception as exc:
                    call.update(constructed=False, exception_type=type(exc).__name__,
                                error_first_line=str(exc).splitlines()[0] if str(exc) else type(exc).__name__)
                    raise
                finally:
                    call["elapsed_seconds"] = time.monotonic() - begin
                    emit(inv, call)
                assert sha256(path) == request["source_sha256"]
                verify_binary(compiler)
                assert extraction["comparability"]["status"] == "comparable"
                actual = occurrence_keys(extraction, str(path), request["source_sha256"])
                name = "extractions/{:02d}.json.gz".format(index)
                digest = archive_extraction(store, name, extraction)
                results.append(dict(sample=index, extraction=name, extraction_sha256=digest,
                                    occurrences=sum(actual.values())))
                print("SAMPLE {}/10 occurrences={}".format(index, sum(actual.values())), flush=True)
        except Exception as exc:
            error = {"type":type(exc).__name__, "message":str(exc)}
    summary = dict(status="complete" if len(results) == 10 and error is None else "stopped",
                   samples=results, error=error, cwd=str(ROOT), profile=profile, cost_usd=0)
    store.write_json("summary.json", summary)
    implementation = json.loads((OUT/"evidence_seal.json").read_text())["implementation_sha256"]
    store.seal(dict(profile, compiler=asdict(compiler)),
               json.loads((OUT/"baseline.json").read_text())["head"], implementation)
    if summary["status"] != "complete":
        raise SystemExit(2)


def extra_samples(store, index, path, compiler, digest):
    relative = "additional/{:04d}".format(index)
    request = dict(path=str(path), source_sha256=digest, version=compiler.version,
                   compiler_sha256=compiler.sha256, sample_count=10, cwd=str(ROOT),
                   profile="regression_6c")
    request_path = store.write_json(relative+"_request.json", request)
    destination = store.path / relative
    command = [sys.executable, "-B", str(Path(__file__).resolve()),
               "--sample", str(request_path), str(destination)]
    begin = time.monotonic()
    process = subprocess.run(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    store.write_bytes(relative+"_stdout.log", process.stdout)
    store.write_bytes(relative+"_stderr.log", process.stderr)
    store.write_json(relative+"_invocation.json", dict(command=command, cwd=str(ROOT),
        returncode=process.returncode, elapsed_seconds=time.monotonic()-begin,
        stdout_sha256=hashlib.sha256(process.stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(process.stderr).hexdigest()))
    if process.returncode:
        raise ValueError("Additional sample process failed, no retries")
    summary = json.loads((destination/"summary.json").read_text())
    seal = json.loads((destination/"seal.json").read_text())
    assert all(sha256(destination/p) == h for p,h in seal["files"].items())
    assert summary["status"] == "complete" and len(summary["samples"]) == 10
    counts = []
    for row in summary["samples"]:
        raw = gzip.decompress((destination/row["extraction"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == row["extraction_sha256"]
        counts.append(occurrence_keys(json.loads(raw), str(path), digest))
    return counts, relative, summary["samples"]


def self_check():
    """Guard the acceptance rule without invoking solc or Slither."""
    key = json.dumps(["sha", ["L1", "f()", 1, False, "C", "C", True, 2, 3, "v", [4,"v","DEF"], []]])
    stable = Counter({key:2})
    cases = [
        ("equal_stable", stable, [stable]*11, True),
        ("stable_wrong", Counter({key:1}), [stable]*11, False),
        ("reference_only", Counter({key:1}), [Counter()]*11, False),
        ("unexpected_stable", Counter(), [stable]*11, False),
        ("inside", Counter({key:1}), [Counter(),stable]+[Counter({key:1})]*9, True),
        ("low_endpoint", Counter(), [Counter(),stable]+[Counter({key:1})]*9, True),
        ("high_endpoint", stable, [Counter(),stable]+[Counter({key:1})]*9, True),
        ("outside", Counter({key:3}), [Counter(),stable]+[Counter({key:1})]*9, False)]
    rows = []
    for name, expected, samples, passed in cases:
        result = ranges(expected, samples)
        assert result["passed"] == passed, name
        rows.append(dict(name=name, expected=passed, result=result))
    for size in [0,1,10,12]:
        try:
            ranges(stable, [stable]*size)
        except ValueError:
            rows.append(dict(name="sample_count_"+str(size), rejected=True))
        else:
            raise AssertionError("Invalid sample count accepted")
    with (OUT/"d20_rule_checks.json").open("x") as stream:
        json.dump(dict(passed=True, cases=rows), stream, sort_keys=True, indent=2)
    print("D20 boundary checks: 12 passed", flush=True)


def execute():
    assert Path.cwd()==ROOT
    assert json.loads((OUT/"authorization.json").read_text())["status"] == "approved"
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
    store=ArtifactStore(ART/"cp2_6c_v2")
    compilers,_,trust=load_trusted_compilers()
    store.write_json("plan.json",{"profile":profile,"cwd":str(ROOT),
        "report_sha256":REPORT_SHA,"seal_sha256":SEAL_SHA,
        "key_proposal":cp0["historical_comparison"]["cp2_key_proposal"],
        "jobs":[{"source":s["path"],"replay_source":str(historical_target(r)),"source_sha256":s["sha256"],"version":r["version"]} for s,r in jobs]})
    old_plan = json.loads((ART/"cp2_6c_v1/plan.json").read_text())
    new_plan = json.loads((store.path/"plan.json").read_text())
    assert new_plan == old_plan, "Main order, versions, key or targets changed"
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
                    settings=compiled.settings,cwd=str(ROOT),cost_usd=0.0)
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
                assert extraction["comparability"]["status"] == "comparable"
                if comparison["equal"]:
                    comparison.update(passed=True, criterion="main_exact", samples=1)
                else:
                    extras, sample_path, sample_rows = extra_samples(store,index,path,compiler,digest)
                    decision = ranges(expected, [actual] + extras)
                    comparison.update(passed=decision["passed"], criterion="D20",
                                      samples=11, additional_directory=sample_path,
                                      additional_extractions=sample_rows, d20=decision)
                emit(comparisons,comparison);results.append(comparison)
                print("REPLAY {}/239: {} {}".format(index,source["path"],
                      "exact" if comparison["equal"] else ("D20 PASS" if comparison["passed"] else "D20 FAIL")),flush=True)
                if not comparison["passed"]:
                    raise ValueError("D20 stable facts or multiplicity range failed; no further samples")
            status="complete"
        except Exception as exc:
            status="stopped";error={"type":type(exc).__name__,"message":str(exc)}
    summary={"mode":"replay","status":status,"expected":239,"compared":len(results),
             "equal":sum(r["equal"] for r in results),"error":error,
             "elapsed_seconds":time.monotonic()-started,"cost_usd":0,"passed":status=="complete"}
    unstable = [k for r in results for k in r.get("d20",{}).get("unstable_keys",[])]
    failing = [dict(path=r["path"], **k) for r in results
               for k in r.get("d20",{}).get("failing_keys",[])]
    summary.update(main_exact_files=sum(r["equal"] for r in results),
        unstable_only_files=sum(not r["equal"] and r["passed"] for r in results),
        additional_processes=sum(not r["equal"] for r in results),
        unstable_keys=len(unstable),
        unstable_by_layer={layer:sum(k["layer"]==layer for k in unstable) for layer in ("L1","L2")},
        unstable_by_kind={kind:sum(k["kind"]==kind for k in unstable) for kind in ("DEF","USE","READ","WRITE")},
        unstable_by_layer_kind={layer:{kind:sum(k["layer"]==layer and k["kind"]==kind for k in unstable)
            for kind in ("DEF","USE","READ","WRITE")} for layer in ("L1","L2")},
        all_unstable_inherited_context=all(k["inherited_context"] is True for k in unstable) if unstable else None,
        failing_keys=failing)
    store.write_json("summary.json",summary)
    implementation=json.loads((OUT/"evidence_seal.json").read_text())["implementation_sha256"]
    store.seal(dict(profile,compilers={v:asdict(c) for v,c in compilers.items()}),
               json.loads((OUT/"baseline.json").read_text())["head"],implementation)
    print(json.dumps(summary),flush=True)
    if status!="complete":raise SystemExit(2)


if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--sample":
        sample(sys.argv[2],sys.argv[3])
    elif len(sys.argv)>1 and sys.argv[1]=="--self-check":
        self_check()
    else:
        execute()
