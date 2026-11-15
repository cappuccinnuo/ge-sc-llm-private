"""CP2.2 D20a and continuation; frozen extraction and keys, no production edits."""
import gzip
import hashlib
import importlib.util
import json
import os
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ART = OUT.parent
sys.path.insert(0, str(ROOT))
from compile_repair.core.store import ArtifactStore, emit, sha256
from compile_repair.evaluation.survey import checked_json, SIX_C, REPORT_SHA, SEAL_SHA
from compile_repair.toolchain.solc import load_trusted_compilers, compile_file, verify_binary
from compile_repair.toolchain.slither import check_profile
from scripts.DFG.dfg_v2.validate_slither import _compile, slither_full_facts

spec = importlib.util.spec_from_file_location("cp21_frozen_driver", ART/"cp2_1_v1/run_replay.py")
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)
occurrence_keys = frozen.occurrence_keys
historical_target = frozen.historical_target
ranges = frozen.ranges
archive_extraction = frozen.archive_extraction


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def verify_store(path):
    seal = read(path/"seal.json")
    for name, digest in seal["files"].items():
        assert sha256(path/name) == digest, name
    return seal


def seal_store(store, tools):
    baseline = read(OUT/"baseline.json")
    store.seal(tools, baseline["head"], baseline["implementation_sha256"])


def references():
    report = checked_json(SIX_C/"slither_full/report.json", REPORT_SHA)
    seal = checked_json(SIX_C/"slither_full/report.seal.json", SEAL_SHA)
    assert seal["report_sha256"] == REPORT_SHA
    rows = [r for _, task in sorted(report["tasks"].items())
            for r in task["files"] if r["status"] == "compared"]
    plan = read(ART/"cp2_6c_v2/plan.json")
    assert plan == read(ART/"cp2_6c_v1/plan.json") and len(rows) == 239
    for ref, job in zip(rows, plan["jobs"]):
        assert ref["source_sha256"] == job["source_sha256"]
        assert ref["version"] == job["version"]
        assert str(historical_target(ref)) == job["replay_source"]
    return rows, plan


def extract(store, inv, job, compiler, profile, relative, sample, role):
    """One logged extraction, with source and executable identity checks."""
    path = Path(job["replay_source"])
    assert Path.cwd() == ROOT and sha256(path) == job["source_sha256"]
    raw = path.read_bytes()
    compiled = compile_file(path, compiler)
    emit(inv, dict(kind="solc", role=role, sample=sample, **asdict(compiled)))
    if compiled.returncode != 0 or compiled.timed_out:
        raise ValueError("Frozen replay solc failed; no retry")
    verify_binary(compiler)
    call = dict(profile, kind="slither", role=role, sample=sample,
        source_path=str(path), source_sha256=job["source_sha256"], version=compiler.version,
        compiler_sha256=compiler.sha256, settings=compiled.settings, cwd=str(ROOT),
        command={"api":"validate_slither._compile; slither_full_facts", "target":str(path),
                 "solc":compiler.path, "solc_disable_warnings":True},
        preceding_observed_solc_returncode=compiled.returncode,
        equivalent_solc_argv=compiled.command, api_subprocess_returncodes_observed=False,
        cost_usd=0.0, pid=os.getpid())
    begin = time.monotonic()
    try:
        slither = _compile(path, compiler.path)
        _, extraction = slither_full_facts(slither, path, raw)
        call.update(constructed=True, counts=extraction["counts"],
                    comparability=extraction["comparability"], error_first_line=None)
    except Exception as exc:
        call.update(constructed=False, exception_type=type(exc).__name__,
                    error_first_line=str(exc).splitlines()[0] if str(exc) else type(exc).__name__)
        raise
    finally:
        call["elapsed_seconds"] = time.monotonic()-begin
        emit(inv, call)
    assert sha256(path) == job["source_sha256"]
    verify_binary(compiler)
    assert extraction["comparability"]["status"] == "comparable"
    counts = occurrence_keys(extraction, str(path), job["source_sha256"])
    digest = archive_extraction(store, relative, extraction)
    return counts, dict(sample=sample, extraction=relative, extraction_sha256=digest,
                       occurrences=sum(counts.values()), comparability=extraction["comparability"])


def load_samples(folder, rows, job):
    result = []
    for row in rows:
        raw = gzip.decompress((folder/row["extraction"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == row["extraction_sha256"]
        extraction = json.loads(raw)
        assert extraction["comparability"]["status"] == "comparable"
        result.append(occurrence_keys(extraction, job["replay_source"], job["source_sha256"]))
    return result


def d20a_decision(expected, original, additions):
    """Require exact reference counts, not only a widened min/max interval."""
    before = ranges(expected, original)
    assert not before["passed"] and 1 <= len(additions) <= 100
    failed = before["failing_keys"]
    targets = []
    for entry in failed:
        key = entry["key"]
        values = [s.get(key, 0) for s in additions]
        matches = [i for i, v in enumerate(values, 1) if v == expected.get(key, 0)]
        targets.append(dict(key=key, reference=expected.get(key, 0), original_counts=entry["counts"],
                            added_counts=values, first_match=matches[0] if matches else None))
    keys = set(expected).union(*(set(s) for s in original+additions))
    variations, stable_failures = [], []
    for key in sorted(keys):
        initial = [s.get(key,0) for s in original]
        later = [s.get(key,0) for s in additions]
        combined = initial+later
        if min(initial) == max(initial) and min(combined) < max(combined):
            variations.append(dict(key=key, reference=expected.get(key,0),
                                   original_counts=initial, added_counts=later))
        if min(combined) == max(combined) and combined[0] != expected.get(key,0):
            stable_failures.append(dict(key=key, reference=expected.get(key,0), counts=combined))
    return dict(passed=all(r["first_match"] is not None for r in targets) and not stable_failures,
                additional_samples=len(additions), failing_keys=targets,
                formerly_stable_now_varying=variations, stable_failures=stable_failures,
                original_d20_unchanged=before)


def worker(request_path, destination):
    """A new process owns exactly ten D20, or bounded early-stopping D20a, samples."""
    request = read(request_path)
    role, job = request["role"], request["job"]
    assert role in ("D20","D20a") and request["cwd"] == str(ROOT) and Path.cwd() == ROOT
    limit = 10 if role == "D20" else 100
    assert request["maximum_samples"] == limit
    targets = request.get("failing_reference_counts", {})
    assert (role == "D20") or targets
    profile = check_profile("regression_6c")
    compilers, _, trust = load_trusted_compilers()
    compiler = compilers[job["version"]]
    assert compiler.sha256 == request["compiler_sha256"]
    store = ArtifactStore(destination)
    store.write_json("request.json",request)
    store.write_json("trust.json",trust)
    results, observed = [], set()
    error = None
    with store.journal("invocations.jsonl") as inv, store.journal("counts.jsonl") as journal:
        try:
            for index in range(1, limit+1):
                actual, row = extract(store, inv, job, compiler, profile,
                    "extractions/{:03d}.json.gz".format(index), index, role)
                target_counts = {k:actual.get(k,0) for k in targets}
                observed.update(k for k,v in targets.items() if actual.get(k,0) == v)
                row["failing_key_counts"] = target_counts
                row["all_targets_observed"] = set(targets) == observed
                results.append(row)
                emit(journal, row)
                print("{} sample={} occurrences={} targets={}/{}".format(
                    role,index,row["occurrences"],len(observed),len(targets)),flush=True)
                if role == "D20a" and observed == set(targets):
                    break
        except Exception as exc:
            error = dict(type=type(exc).__name__,message=str(exc))
    success = error is None and (len(results) == 10 if role == "D20" else observed == set(targets))
    summary = dict(status="complete" if success else "stopped", role=role, samples=results,
        sample_count=len(results), unresolved=sorted(set(targets)-observed), error=error,
        pid=os.getpid(), cwd=str(ROOT), profile=profile, maximum_samples=limit, cost_usd=0)
    store.write_json("summary.json",summary)
    seal_store(store,dict(profile,compiler=asdict(compiler)))
    if not success:
        raise SystemExit(2)


def child(store, role, index, job, compiler, failures=None):
    relative = role.lower()+"/{:04d}".format(index)
    request = dict(role=role, job=job, cwd=str(ROOT), compiler_sha256=compiler.sha256,
        maximum_samples=10 if role == "D20" else 100, profile="regression_6c",
        failing_reference_counts={r["key"]:r["reference"] for r in (failures or [])})
    request_path = store.write_json(relative+"_request.json",request)
    command = [sys.executable,"-B",str(Path(__file__).resolve()),"--worker",
               str(request_path),str(store.path/relative)]
    begin = time.monotonic()
    process = subprocess.run(command,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    store.write_bytes(relative+"_stdout.log",process.stdout)
    store.write_bytes(relative+"_stderr.log",process.stderr)
    store.write_json(relative+"_invocation.json",dict(command=command,cwd=str(ROOT),
        returncode=process.returncode, elapsed_seconds=time.monotonic()-begin,
        stdout_sha256=hashlib.sha256(process.stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(process.stderr).hexdigest()))
    verify_store(store.path/relative)
    summary = read(store.path/relative/"summary.json")
    if summary["error"] is not None:
        raise ValueError("Sampling process failed: "+str(summary["error"]))
    if role == "D20" and (process.returncode or summary["sample_count"] != 10):
        raise ValueError("D20 requires exactly 10 new-process samples")
    assert summary["pid"] != os.getpid()
    counts = load_samples(store.path/relative,summary["samples"],job)
    return counts, dict(directory=relative,summary=summary,returncode=process.returncode)


def make_comparison(index, job, expected, actual, observation):
    return dict(index=index, path=job["source"], source_sha256=job["source_sha256"],
        version=job["version"], profile="regression_6c", occurrences=sum(actual.values()),
        reference_occurrences=sum(expected.values()), equal=actual == expected,
        only_reference=dict(expected-actual), only_replay=dict(actual-expected),
        extraction_sha256=observation["extraction_sha256"],
        comparability=observation["comparability"])


def continuation(destination):
    """New main process, exactly files 228-239 in their historical order."""
    assert Path.cwd() == ROOT
    refs, plan = references()
    profile = check_profile("regression_6c")
    compilers, _, trust = load_trusted_compilers()
    store = ArtifactStore(destination)
    store.write_json("plan.json",dict(indices=list(range(228,240)),original_plan=plan))
    store.write_json("trust.json",trust)
    results, error = [], None
    with store.journal("comparison.jsonl") as journal, store.journal("invocations.jsonl") as inv:
        try:
            for index in range(228,240):
                job, ref = plan["jobs"][index-1], refs[index-1]
                expected = occurrence_keys(ref["slither_extraction"],job["replay_source"],job["source_sha256"])
                compiler = compilers[job["version"]]
                actual, observation = extract(store,inv,job,compiler,profile,
                    "extractions/{:04d}.json.gz".format(index),index,"main_continuation")
                row = make_comparison(index,job,expected,actual,observation)
                if row["equal"]:
                    row.update(passed=True,criterion="main_exact",samples=1)
                else:
                    extras, evidence = child(store,"D20",index,job,compiler)
                    initial = [actual]+extras
                    decision = ranges(expected,initial)
                    row.update(passed=decision["passed"],criterion="D20",samples=11,
                               d20=decision,d20_evidence=evidence)
                    if not decision["passed"]:
                        additions, evidence = child(store,"D20a",index,job,compiler,decision["failing_keys"])
                        extension = d20a_decision(expected,initial,additions)
                        row.update(passed=extension["passed"],criterion="D20a",
                                   d20a=extension,d20a_evidence=evidence)
                emit(journal,row)
                results.append(row)
                print("REPLAY {}/239 {} {}".format(index,row["criterion"],row["passed"]),flush=True)
                if not row["passed"]:
                    raise ValueError("D20a failed; no further files or samples")
        except Exception as exc:
            error = dict(type=type(exc).__name__,message=str(exc))
    passed = error is None and len(results) == 12 and all(r["passed"] for r in results)
    store.write_json("summary.json",dict(passed=passed,status="complete" if passed else "stopped",
        compared=len(results),expected=12,error=error,pid=os.getpid(),profile=profile,cost_usd=0))
    seal_store(store,dict(profile,compilers={v:asdict(c) for v,c in compilers.items()}))
    if not passed:
        raise SystemExit(2)


def execute():
    assert Path.cwd() == ROOT
    assert read(OUT/"authorization.json")["status"] == "approved"
    profile = check_profile("regression_6c")
    refs, plan = references()
    old = ART/"cp2_6c_v2"
    verify_store(old)
    previous = [json.loads(line) for line in (old/"comparison.jsonl").read_text().splitlines()]
    assert len(previous) == 227 and all(r["passed"] for r in previous[:226])
    assert not previous[-1]["passed"] and len(previous[-1]["d20"]["failing_keys"]) == 1
    compilers, _, trust = load_trusted_compilers()
    store = ArtifactStore(ART/"cp2_6c_v3")
    store.write_json("plan.json",dict(original_plan=plan,reused_indices=list(range(1,227)),
        d20a_existing_index=227,continuation_indices=list(range(228,240)),
        old_seal_sha256=sha256(old/"seal.json"),authorization_sha256=sha256(OUT/"authorization.json"),
        driver_sha256=sha256(Path(__file__)),frozen_key_driver_sha256=sha256(ART/"cp2_1_v1/run_replay.py")))
    store.write_json("trust.json",trust)
    results, error = [], None
    begin = time.monotonic()
    with store.journal("comparison.jsonl") as journal:
        for index,row in enumerate(previous[:226],1):
            item = dict(row,index=index,evidence_batch="cp2_6c_v2",reused=True)
            emit(journal,item)
            results.append(item)
        try:
            index = 227
            row = dict(previous[-1],index=index,evidence_batch="cp2_6c_v2",reused=True)
            job = plan["jobs"][index-1]
            expected = occurrence_keys(refs[index-1]["slither_extraction"],job["replay_source"],job["source_sha256"])
            initial = load_samples(old,[dict(extraction="extractions/0227.json.gz",
                extraction_sha256=row["extraction_sha256"])],job)
            folder = old/row["additional_directory"]
            verify_store(folder)
            initial += load_samples(folder,read(folder/"summary.json")["samples"],job)
            assert ranges(expected,initial) == row["d20"]
            additions, evidence = child(store,"D20a",index,job,compilers[job["version"]],row["d20"]["failing_keys"])
            extension = d20a_decision(expected,initial,additions)
            row.update(passed=extension["passed"],criterion="D20a",d20a=extension,d20a_evidence=evidence)
            emit(journal,row)
            results.append(row)
            print("REPLAY 227/239 D20a samples={} passed={}".format(len(additions),row["passed"]),flush=True)
            if not row["passed"]:
                raise ValueError("File 227 D20a exhausted; continuation and descending forbidden")
            command = [sys.executable,"-B",str(Path(__file__).resolve()),"--continue",str(store.path/"continuation")]
            started = time.monotonic()
            process = subprocess.run(command,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            store.write_bytes("continuation_stdout.log",process.stdout)
            store.write_bytes("continuation_stderr.log",process.stderr)
            store.write_json("continuation_invocation.json",dict(command=command,cwd=str(ROOT),
                returncode=process.returncode,elapsed_seconds=time.monotonic()-started))
            verify_store(store.path/"continuation")
            receipt = read(store.path/"continuation/summary.json")
            assert receipt["pid"] != os.getpid()
            for line in (store.path/"continuation/comparison.jsonl").read_text().splitlines():
                item = dict(json.loads(line),evidence_batch="cp2_6c_v3/continuation",reused=False)
                emit(journal,item)
                results.append(item)
            print(process.stdout.decode("utf8"),flush=True)
            if process.returncode or not receipt["passed"]:
                raise ValueError("Continuation stopped: "+str(receipt["error"]))
        except Exception as exc:
            error = dict(type=type(exc).__name__,message=str(exc))
    passed = error is None and len(results) == 239 and all(r["passed"] for r in results)
    summary = dict(mode="replay",status="complete" if passed else "stopped",passed=passed,
        expected=239,compared=len(results),remaining=239-len(results),reused_main_extractions=227,
        newly_extracted_main_files=sum(not r["reused"] for r in results),error=error,
        main_exact_files=sum(r["equal"] for r in results),
        d20_passed_files=sum(r["passed"] and r["criterion"]=="D20" for r in results),
        d20a_passed_files=sum(r["passed"] and r["criterion"]=="D20a" for r in results),
        file_227_additional_samples=next((r.get("d20a",{}).get("additional_samples") for r in results if r["index"]==227), None),
        elapsed_seconds=time.monotonic()-begin,cost_usd=0)
    store.write_json("summary.json",summary)
    seal_store(store,dict(profile,compilers={v:asdict(c) for v,c in compilers.items()}))
    print(json.dumps(summary),flush=True)
    if not passed:
        raise SystemExit(2)


def self_check():
    """Synthetic limits and exact-multiplicity checks; no compiler calls."""
    def key(name):
        return json.dumps(["sha",["L1","f()",1,False,"C","C",False,2,3,name,[4,name,"DEF"],[]]],sort_keys=True)
    a,b,c = key("a"),key("b"),key("c")
    zero = Counter()
    cases = []
    for name, ref, initial, extra, passed in [
        ("reference_only_match",Counter({a:1}),[zero]*11,[Counter({a:1})],True),
        ("range_contains_but_never_equals",Counter({a:1}),[zero]*11,[Counter({a:2})],False),
        ("100_absent",Counter({a:1}),[zero]*11,[zero]*100,False),
        ("100th_observed",Counter({a:1}),[zero]*11,[zero]*99+[Counter({a:1})],True),
        ("multiple_targets_independent",Counter({a:1,b:1}),[zero]*11,[Counter({a:1}),Counter({b:1})],True),
        ("one_target_absent",Counter({a:1,b:1}),[zero]*11,[Counter({a:1})],False),
        ("reference_zero",zero,[Counter({a:1})]*11,[zero],True),
        ("outside_initial_range",Counter({a:3}),[Counter({a:1})]*10+[Counter({a:2})],[Counter({a:3})],True),
        ("newly_varying_key_recorded",Counter({a:1,c:2}),[Counter({c:2})]*11,[Counter({a:1,c:1})],True)]:
        result = d20a_decision(ref,initial,extra)
        assert result["passed"] == passed, name
        assert result["original_d20_unchanged"] == ranges(ref,initial)
        if name == "newly_varying_key_recorded":
            assert c in {r["key"] for r in result["formerly_stable_now_varying"]}
        cases.append(dict(name=name,passed=True,expected_acceptance=passed))
    for n in (0,101):
        try:
            d20a_decision(Counter({a:1}),[zero]*11,[zero]*n)
        except AssertionError:
            cases.append(dict(name="reject_sample_count_"+str(n),passed=True))
        else:
            raise AssertionError("Invalid count accepted")
    with (OUT/"d20a_rule_checks.json").open("x",encoding="utf8") as stream:
        json.dump(dict(passed=True,cases=cases,extraction_calls=0),stream,indent=2,sort_keys=True)
    print("D20a boundary checks: {} passed".format(len(cases)),flush=True)


if __name__ == "__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--worker":
        worker(sys.argv[2],sys.argv[3])
    elif len(sys.argv)>1 and sys.argv[1]=="--continue":
        continuation(sys.argv[2])
    elif len(sys.argv)>1 and sys.argv[1]=="--self-check":
        self_check()
    else:
        execute()
