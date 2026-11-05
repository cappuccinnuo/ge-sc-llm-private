"""Serial, authorized staged execution for frozen Prompt 8 batches.

Only process orchestration and report dispatch live here. Every fit still uses
run.execute and the existing trainer with the sealed initial state and config.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from . import run
from .precision_gpu import audit_pilot_result

VERSION = "dfg-v2-staged-batch-v1"
AUTH_VERSION = "prompt8-stage-execution-authorization-v1"
TICKET_VERSION = "prompt8b0-controller-ticket-v1"


def _process_start(pid):
    # Linux starttime prevents a stale PID from being mistaken for this parent.
    fields = Path("/proc/{}/stat".format(pid)).read_text().rsplit(")", 1)[1].split()
    return fields[19]


def _acceptance_version():
    from . import acceptance_cache, precision_gpu
    return {"version": TICKET_VERSION, "code": {
        str(Path(mod.__file__).resolve()): sha256(mod.__file__)
        for mod in (run, acceptance_cache, precision_gpu)},
        "batch_sha256": sha256(__file__)}


def validate_execution_ticket(ticket_path, ticket_sha256, plan_path, plan, job,
                              authorization_path, amendment_path):
    ticket = read_json(checked(ticket_path, ticket_sha256))
    identity = run.job_id(job)
    auth, decision = validate_authorization(plan_path, plan, "B", authorization_path)
    if decision.get("amendment") != _ref(amendment_path):
        raise ValueError("Stage B authorization does not approve this runtime amendment")
    if (ticket.get("version") != TICKET_VERSION or ticket.get("parent_pid") != os.getppid()
            or ticket.get("parent_start") != _process_start(os.getppid())
            or ticket.get("plan") != _ref(plan_path) or ticket.get("job") != identity
            or ticket.get("authorization") != auth
            or ticket.get("amendment") != _ref(amendment_path)):
        raise ValueError("Execution ticket does not belong to the live stage B controller")
    start = read_json(checked(ticket["invocation_start"]["path"],
                              ticket["invocation_start"]["sha256"]))
    if (start.get("pid") != os.getppid() or start.get("plan") != _ref(plan_path)
            or start.get("authorization") != auth or start.get("stage") != "B"):
        raise ValueError("Controller invocation binding differs")
    if not isinstance(ticket.get("completed"), dict):
        raise ValueError("Missing controller acceptance anchors")
    known = {run.job_id(j) for j in plan["jobs"]}
    if not set(ticket["completed"]) <= known:
        raise ValueError("Foreign job in controller ticket")
    return ticket


def _ticket_completed(plan_path, plan, job, ticket):
    from .acceptance_cache import verify_cache
    folder = run._job_directory(Path(plan_path).parent, job)
    matches = sorted(folder.glob("attempt_*/receipt.json")) if folder.exists() else []
    if len(matches) > 1:
        raise ValueError("Duplicate successful job results")
    reference = ticket["completed"].get(run.job_id(job))
    if not matches:
        if reference is not None:
            raise ValueError("Controller receipt disappeared")
        return None
    if reference is None:
        raise ValueError("Successful receipt has no live-controller acceptance anchor")
    row = verify_cache(reference, expected_seal_sha=reference["sha256"],
        plan_path=plan_path, job=job, attempt=matches[0].parent,
        full_verify=lambda: _accept(plan_path, plan, job),
        acceptance_version=_acceptance_version())
    return Path(row["attempt"]), row["result"]


def _ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha256(path)}


def _exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def stage_jobs(plan, stage):
    if stage not in ("A", "B"):
        raise ValueError("Unknown execution stage")
    registration = plan.get("batch_registration", {})
    stages = registration.get("stages", {})
    if set(stages) != {"A", "B"}:
        raise ValueError("Missing registered stages")
    jobs = {run.job_id(job): job for job in plan["jobs"]}
    all_ids = []
    for name in ("A", "B"):
        ids = stages[name]["jobs"]
        if (not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
                or any(i not in jobs for i in ids)):
            raise ValueError("Invalid stage identities")
        if any(jobs[i]["profile"] not in stages[name]["profiles"] for i in ids):
            raise ValueError("Stage profile differs")
        all_ids.extend(ids)
    if len(all_ids) != len(set(all_ids)) or set(all_ids) != set(jobs):
        raise ValueError("Stages must partition the entire frozen plan")
    return [jobs[i] for i in stages[stage]["jobs"]]


def _interim_receipt(plan_path):
    path = Path(plan_path).parent / "batch_records" / "interim_A.json"
    value = read_json(path)
    if (value.get("version") != VERSION or value.get("stage") != "A"
            or value.get("plan_sha256") != sha256(plan_path)
            or value.get("status") != "complete"):
        raise ValueError("Stage B requires a bound complete stage A interim report")
    for ref in value["report_files"].values():
        checked(ref["path"], ref["sha256"])
    return path, value


def validate_authorization(plan_path, plan, stage, authorization):
    if not authorization:
        raise ValueError("Explicit stage authorization is required after plan review")
    path = Path(authorization).resolve()
    record = read_json(path)
    expected = [run.job_id(j) for j in stage_jobs(plan, stage)]
    if (record.get("version") != AUTH_VERSION or record.get("approved") is not True
            or record.get("stage") != stage or record.get("plan") != _ref(plan_path)
            or record.get("authorized_jobs") != expected
            or not isinstance(record.get("user_answer"), str) or not record["user_answer"].strip()
            or not isinstance(record.get("recorded_at"), str) or not record["recorded_at"].strip()):
        raise ValueError("Stage authorization does not match the frozen plan and order")
    if stage == "B":
        receipt_path, _ = _interim_receipt(plan_path)
        if record.get("interim_receipt") != _ref(receipt_path):
            raise ValueError("Stage B authorization must bind the reviewed stage A report")
    return _ref(path), record


def authorize_job(plan_path, plan, job, execution_authorization, retry=False, execution_ticket=None):
    """Direct execution needs the same explicit retry evidence as the controller."""
    identity = run.job_id(job)
    matches = [stage for stage in ("A", "B")
               if identity in [run.job_id(j) for j in stage_jobs(plan, stage)]]
    if len(matches) != 1:
        raise ValueError("Job not uniquely registered")
    ref, decision = validate_authorization(plan_path, plan, matches[0], execution_authorization)
    accepted = {}
    # One pass owns ordering and failed-start checks. Amended children use only
    # cache anchors supplied by their live parent; standalone calls stay strict.
    for prior in plan["jobs"]:
        pid = run.job_id(prior)
        if not _attempts(plan_path, prior):
            continue
        row = (_ticket_completed(plan_path, plan, prior, execution_ticket)
               if execution_ticket is not None else
               run._completed(Path(plan_path).parent, plan, prior, Path(plan_path)))
        if row is not None:
            accepted[pid] = row
        elif not (retry and pid == identity):
            raise RuntimeError("Batch stopped by failed/incomplete job " + pid +
                               "; user-confirmed explicit --retry required")
    existing = accepted.get(identity)
    if existing is None:
        ordered = stage_jobs(plan, matches[0])
        if any(run.job_id(earlier) not in accepted
               for earlier in ordered[:[run.job_id(j) for j in ordered].index(identity)]):
            raise RuntimeError("Earlier stage jobs must be verified before a new direct fit")
    # Only the live controller that directly spawned this child may be ignored.
    # A failed invocation (including preflight-before-attempt failure) is retained.
    latches = _controller_failures(plan_path, parent=(os.getppid(), ref, identity))
    attempts = _attempts(plan_path, job)
    failed_fit = bool(attempts and existing is None)
    if latches or failed_fit or retry:
        if not retry:
            raise RuntimeError("Preserved batch failure requires user-confirmed explicit --retry")
        _retry_evidence(plan_path, decision, identity, latches,
                        _fit_failure_evidence(attempts) if failed_fit else None)
    return ref


def _accept(plan_path, plan, job):
    completed = run._completed(Path(plan_path).parent, plan, job, Path(plan_path))
    if completed is None:
        return None
    attempt, result = completed
    audit = audit_pilot_result(result, resource_policy=plan["resource_policy"])
    if not audit["passed"]:
        raise ValueError("Completed job failed gradient/checkpoint/resource audit: " +
                         repr(audit["problems"]))
    if result["resources"].get("sampling_errors"):
        raise ValueError("Completed job has resource sampling errors needing review")
    return dict(job=job, attempt=str(attempt), result=result, audit=audit)


def _attempts(plan_path, job):
    folder = run._job_directory(Path(plan_path).parent, job)
    return sorted(folder.glob("attempt_*.started.json")) if folder.exists() else []


def verify_stage(plan_path, stage, amendment_path=None):
    path = Path(plan_path).resolve()
    plan = run._load_plan(path, amendment_path=amendment_path)
    results, missing = {}, []
    for job in stage_jobs(plan, stage):
        row = _accept(path, plan, job)
        if row is None:
            missing.append(run.job_id(job))
        else:
            results[run.job_id(job)] = row
    if missing:
        raise ValueError("Incomplete stage {}: {}".format(stage, ", ".join(missing)))
    return dict(version=VERSION, stage=stage, plan_sha256=sha256(path),
                complete=True, completed_jobs=len(results), results=results)


def _next_invocation(plan_path, stage):
    parent = Path(plan_path).parent / "batch_records" / "executions" / stage
    parent.mkdir(parents=True, exist_ok=True)
    used = [int(p.name.split("_")[1]) for p in parent.glob("invocation_*") if p.is_dir()]
    path = parent / ("invocation_%03d" % (max(used, default=0) + 1))
    path.mkdir()
    return path


def _fit_failure_evidence(attempts):
    latest = attempts[-1]
    failure = latest.with_name(latest.name.replace(".started.json", ".failure.json"))
    return failure if failure.exists() else latest


def _controller_failures(plan_path, parent=None):
    """Find unreviewed failed or interrupted invocations, even without a fit."""
    root = Path(plan_path).parent / "batch_records" / "executions"
    if not root.exists():
        return []
    directories = sorted(root.glob("*/invocation_*"))
    resolved = set()
    for directory in directories:
        resolution = directory / "retry_resolution.json"
        if resolution.exists():
            doc = read_json(resolution)
            if doc.get("plan") != _ref(plan_path):
                raise ValueError("Retry resolution plan differs")
            receipt = doc["successful_receipt"]
            checked(receipt["path"], receipt["sha256"])
            for ref in doc["resolved_evidence"]:
                checked(ref["path"], ref["sha256"])
                resolved.add((ref["path"], ref["sha256"]))
    result = []
    for directory in directories:
        started, failure = directory / "started.json", directory / "failure.json"
        if not started.exists():
            raise ValueError("Invocation directory has no bound start record")
        first = read_json(started)
        if first.get("plan") != _ref(plan_path):
            raise ValueError("Invocation start plan differs")
        if not failure.exists() and (directory / "complete.json").exists():
            continue
        active_records = sorted(directory.glob("*.active_job.json"))
        active = read_json(active_records[-1])["job"] if active_records else None
        if failure.exists():
            doc = read_json(failure)
            if doc.get("plan") != _ref(plan_path):
                raise ValueError("Invocation failure plan differs")
            active = doc.get("active_job", active)
            if active is None and doc.get("execution_records"):
                active = doc["execution_records"][-1].get("job")
        elif parent and first.get("pid") == parent[0] and first.get("authorization") == parent[1] and active == parent[2]:
            continue
        evidence = _ref(failure if failure.exists() else started)
        if (evidence["path"], evidence["sha256"]) not in resolved:
            result.append(dict(job=active, evidence=evidence))
    return result


def _retry_evidence(plan_path, decision, identity, latches, fit_evidence=None):
    if decision.get("retry_job") != identity:
        raise ValueError("Retry requires a new user decision naming the failed job")
    if any(row["job"] not in (None, identity) for row in latches):
        raise RuntimeError("Other unresolved controller failures cannot be skipped")
    evidence = [row["evidence"] for row in latches]
    if fit_evidence is not None:
        evidence.append(_ref(fit_evidence))
    if not evidence:
        raise ValueError("Retry authorization has no preserved failure")
    # A second failed retry requires a second decision; the old failure's hash
    # must not become reusable authority for an unlimited sequence of attempts.
    newest = max(evidence, key=lambda ref: (Path(ref["path"]).stat().st_mtime_ns, ref["path"]))
    if decision.get("retry_evidence") != newest:
        raise ValueError("Retry authorization does not bind the latest preserved failure")
    return evidence


def _resolve_retry(invocation, plan_path, identity, accepted, evidence):
    if not evidence:
        return
    # A recovery is resolved only after its named job is independently accepted.
    receipt_path = Path(accepted["attempt"]) / "receipt.json"
    _exclusive_json(invocation / "retry_resolution.json", dict(
        version=VERSION, plan=_ref(plan_path), job=identity, resolved_evidence=evidence,
        successful_receipt=_ref(receipt_path), resume_epoch=False))


def execute(plan_path, stage, authorization_record, retry_job=None, amendment_path=None):
    path = Path(plan_path).resolve()
    if amendment_path is not None and stage != "B":
        raise ValueError("Runtime amendment permits stage B only, not stage A retraining")
    plan = run._load_plan(path, amendment_path=amendment_path)
    authorization, decision = validate_authorization(path, plan, stage, authorization_record)
    if amendment_path is not None and decision.get("amendment") != _ref(amendment_path):
        raise ValueError("Stage B authorization does not approve this runtime amendment")
    jobs = stage_jobs(plan, stage)
    ids = [run.job_id(j) for j in jobs]
    if retry_job is not None and retry_job not in ids:
        raise ValueError("Retry identity is outside the selected stage")
    if retry_job is not None and decision.get("retry_job") != retry_job:
        raise ValueError("Retry requires a new user decision naming the failed job")
    with run._Lock(path.parent / ".batch.lock"):
        # Check earlier invocations before creating another one. A rejected
        # resume request must not create an endless chain of new failure latches.
        latches = _controller_failures(path)
        completed, failures, cache_refs = {}, [], {}
        cache_root = None
        if amendment_path is not None:
            from .acceptance_cache import create_cache, verify_cache
            cache_root = Path(amendment_path).resolve().parent / "acceptance_generations" / uuid.uuid4().hex
            cache_root.mkdir(parents=True)
        for job in plan["jobs"]:
            identity = run.job_id(job)
            attempts = _attempts(path, job)
            if attempts and amendment_path is not None:
                matches = sorted(run._job_directory(path.parent, job).glob("attempt_*/receipt.json"))
                if len(matches) > 1:
                    raise ValueError("Duplicate successful job results")
                if matches:
                    reference = create_cache(cache_root, path, job, matches[0].parent,
                        lambda job=job: _accept(path, plan, job), _acceptance_version())
                    cache_refs[identity] = reference
                    row = verify_cache(reference, expected_seal_sha=reference["sha256"],
                        plan_path=path, job=job, attempt=matches[0].parent,
                        full_verify=lambda job=job: _accept(path, plan, job),
                        acceptance_version=_acceptance_version())
                else:
                    row = None
            else:
                row = _accept(path, plan, job) if attempts else None
            if row is not None:
                completed[identity] = row
            elif attempts:
                failures.append(identity)
        retry_evidence = []
        if failures or latches:
            if retry_job is None:
                raise RuntimeError("Batch stopped by preserved failed/incomplete execution")
            if failures and failures != [retry_job]:
                raise RuntimeError("Other failed/incomplete jobs cannot be skipped: " + repr(failures))
            target = next(j for j in jobs if run.job_id(j) == retry_job)
            fit_evidence = _fit_failure_evidence(_attempts(path, target)) if failures else None
            retry_evidence = _retry_evidence(path, decision, retry_job, latches, fit_evidence)
            if any(identity not in completed for identity in ids[:ids.index(retry_job)]):
                raise RuntimeError("Retry cannot execute new earlier jobs before the failed target")
        elif retry_job is not None:
            raise ValueError("No failed execution exists for the requested retry")
        invocation = _next_invocation(path, stage)
        _exclusive_json(invocation / "started.json", dict(
            version=VERSION, stage=stage, plan=_ref(path), authorization=authorization,
            retry_job=retry_job, pid=os.getpid(), started_unix=time.time()))
        records, active_job = [], None
        try:
            for job in jobs:
                checked(authorization["path"], authorization["sha256"])
                identity = run.job_id(job)
                if identity in completed:
                    record = dict(job=identity, status="reused", attempt=completed[identity]["attempt"])
                    records.append(record)
                    _exclusive_json(invocation / ("%03d.reused.json" % len(records)), record)
                    if identity == retry_job:
                        _resolve_retry(invocation, path, identity, completed[identity], retry_evidence)
                    continue
                active_job = identity
                _exclusive_json(invocation / ("%03d.active_job.json" % (len(records) + 1)),
                                dict(job=identity, plan=_ref(path), started_unix=time.time()))
                argv = [sys.executable, "-B", "-m", "scripts.DFG.dfg_v2.experiment.run",
                        "execute", "--plan", str(path), "--only", identity,
                        "--execution-authorization", authorization["path"]]
                if identity == retry_job:
                    argv.append("--retry")
                if amendment_path is not None:
                    ticket_path = invocation / ("%03d.execution_ticket.json" % (len(records) + 1))
                    ticket = dict(version=TICKET_VERSION, parent_pid=os.getpid(),
                        parent_start=_process_start(os.getpid()), plan=_ref(path),
                        authorization=authorization, amendment=_ref(amendment_path),
                        invocation_start=_ref(invocation / "started.json"),
                        job=identity, completed=cache_refs)
                    _exclusive_json(ticket_path, ticket)
                    argv.extend(["--amendment", str(Path(amendment_path).resolve()),
                        "--execution-ticket", str(ticket_path),
                        "--ticket-sha256", sha256(ticket_path)])
                log = invocation / ("%03d_%s.log" % (len(records) + 1, identity.replace("/", "_")))
                start = time.time()
                print("START " + identity, flush=True)
                with log.open("x", encoding="utf8") as stream:
                    exit_code = subprocess.run(argv, cwd=str(run.ROOT),
                        stdout=stream, stderr=subprocess.STDOUT, env=os.environ.copy()).returncode
                record = dict(job=identity, argv=argv, status="executed",
                    started_unix=start, seconds=time.time()-start, returncode=exit_code, log=_ref(log))
                records.append(record)
                _exclusive_json(invocation / ("%03d.process.json" % len(records)), record)
                if exit_code:
                    raise RuntimeError("Job failed with exit {}: {}".format(exit_code, identity))
                if amendment_path is not None:
                    matches = sorted(run._job_directory(path.parent, job).glob("attempt_*/receipt.json"))
                    if len(matches) != 1:
                        raise ValueError("Expected one completed child receipt")
                    reference = create_cache(cache_root, path, job, matches[0].parent,
                        lambda: _accept(path, plan, job), _acceptance_version())
                    cache_refs[identity] = reference
                    accepted = verify_cache(reference, expected_seal_sha=reference["sha256"],
                        plan_path=path, job=job, attempt=matches[0].parent,
                        full_verify=lambda: _accept(path, plan, job),
                        acceptance_version=_acceptance_version())
                    completed[identity] = accepted
                else:
                    accepted = _accept(path, plan, job)
                if accepted is None:
                    raise ValueError("Child returned success without a verified result")
                _exclusive_json(invocation / ("%03d.acceptance.json" % len(records)), dict(
                    job=identity, attempt=accepted["attempt"], audit=accepted["audit"],
                    formal_receipt_verified=True))
                if identity == retry_job:
                    _resolve_retry(invocation, path, identity, accepted, retry_evidence)
                active_job = None
                print("ACCEPTED " + identity, flush=True)
            verified = verify_stage(path, stage, amendment_path=amendment_path)
            _exclusive_json(invocation / "complete.json", dict(
                version=VERSION, stage=stage, status="complete", plan=_ref(path),
                jobs=verified["completed_jobs"], execution_records=records))
            return dict(stage=stage, complete=True, jobs=verified["completed_jobs"],
                        invocation=str(invocation))
        except BaseException as exc:
            _exclusive_json(invocation / "failure.json", dict(
                version=VERSION, stage=stage, status="failed", exception=repr(exc),
                automatic_retry=False, resume_epoch=False, plan=_ref(path),
                active_job=active_job, execution_records=records))
            raise


def interim(plan_path, stage="A"):
    if stage != "A":
        raise ValueError("Only stage A has an interim report")
    path = Path(plan_path).resolve()
    plan = run._load_plan(path)
    if (path.parent / "selection.json").exists():
        raise ValueError("Interim must not use or calculate a selected profile")
    receipt_path = path.parent / "batch_records" / "interim_A.json"
    if receipt_path.exists():
        raise FileExistsError("Refusing to overwrite the registered interim report")
    verified = verify_stage(path, "A")
    from .reporting import build_report
    report = build_report(path, stage="A",
        verified_results={identity: row["result"] for identity, row in verified["results"].items()})
    # Bind every generated report file, including human-readable tables.
    directory = Path(report["output"])
    files = {str(p.relative_to(directory)): _ref(p)
             for p in sorted(directory.rglob("*")) if p.is_file()}
    if not files or "REPORT_INTERIM_A.md" not in files:
        raise ValueError("Missing explicitly named stage A interim report")
    receipt = dict(version=VERSION, stage="A", status="complete", plan_sha256=sha256(path),
        completed_jobs=verified["completed_jobs"], report_files=files,
        selected_profile=None, next_stage_execution_authorized=False)
    _exclusive_json(receipt_path, receipt)
    return dict(stage="A", report=str(directory), receipt=str(receipt_path),
                stop_for_user_review=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("execute", "interim", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--plan", required=True)
        command.add_argument("--stage", choices=("A", "B"), required=True)
        command.add_argument("--amendment", help="Explicit validated Prompt8B.0 runtime amendment")
        if name == "execute":
            command.add_argument("--authorization-record", required=True)
            command.add_argument("--retry", metavar="JOB_ID")
    args = parser.parse_args(argv)
    if args.command == "execute":
        answer = execute(args.plan, args.stage, args.authorization_record, args.retry,
                         amendment_path=args.amendment)
    elif args.command == "interim":
        if args.amendment is not None:
            raise ValueError("Historical stage A interim must not be regenerated")
        answer = interim(args.plan, args.stage)
    else:
        answer = verify_stage(args.plan, args.stage, amendment_path=args.amendment)
        answer = {k:v for k,v in answer.items() if k != "results"}
    print(json.dumps(answer, ensure_ascii=False, sort_keys=True), flush=True)
    return answer


if __name__ == "__main__":
    main()
