"""Prompt 8H final-resource cache adapter.
Copied source: scripts/DFG/dfg_v2/experiment/acceptance_cache.py
Source SHA256: a6afa11d40334cdbe49abed55e04129246a41ba6eeca8edf344f000544eae145
Only new-protocol dependency collection uses final_result.json and its approved
runtime amendment. Cache identity, inventory and tamper checks are unchanged.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime, timezone

VERSION = "prompt8h-final-resource-acceptance-cache-v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")


class AcceptanceCacheChanged(ValueError):
    """A cached dependency changed; preserve the old seal for review."""


def _sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _stat(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Acceptance dependency is not a regular file: " + str(path))
    value = path.stat()
    return dict(size=value.st_size, mtime_ns=value.st_mtime_ns)


def _identity(job):
    if isinstance(job, str):
        identity = job
    else:
        identity = "{task_id}/{fold}/{seed}/{profile}".format(**job)
    parts = identity.split("/")
    if not parts or any(not p or p in (".", "..") or "\\" in p for p in parts):
        raise ValueError("Unsafe cache job identity")
    return identity


def _resolve(path, base):
    path = Path(path)
    return (path if path.is_absolute() else base / path).resolve()


def _dependencies(plan_path, attempt, extra_refs=()):
    """Mirror the files read by the full acceptance path, not all provenance.

    All receipt artifacts remain bound. External references are followed only
    at the exact schema locations read by run._verify_attempt,
    run._verify_execution_authorization and resource_plan.validate_resource_result.
    Historical provenance (for example the old PROMPTS.md SHA in a stage A
    approval) records its source at that time; it is not a mutable runtime input.
    File extensions are never used to exclude evidence: an interim report .md
    referenced by stage B authorization is still a required checked dependency.
    """
    plan_path, attempt = Path(plan_path).resolve(), Path(attempt).resolve()
    from .protocol import PROTOCOL_NAME
    if _read(plan_path).get("protocol") != PROTOCOL_NAME:
        from ..experiment.acceptance_cache import _dependencies as old_dependencies
        return old_dependencies(plan_path, attempt, extra_refs)
    receipt_path = attempt / "receipt.json"
    receipt = _read(receipt_path)
    records = {}

    def add(path, expected=None):
        path = Path(path).resolve()
        if expected is not None and (not isinstance(expected, str) or not _SHA.fullmatch(expected)):
            raise ValueError("Invalid dependency SHA: " + str(path))
        record = dict(path=str(path), sha256=expected or _sha(path), **_stat(path))
        previous = records.get(str(path))
        if previous is not None and previous != record:
            raise ValueError("Conflicting or changing dependency: " + str(path))
        records[str(path)] = record
        return path

    def add_ref(ref, base):
        if not isinstance(ref, dict) or "path" not in ref or "sha256" not in ref:
            raise ValueError("Missing acceptance dependency reference")
        return add(_resolve(ref["path"], base), ref["sha256"])

    add(plan_path)
    seal = plan_path.with_name("plan.seal.json")
    if seal.exists():
        add(seal)
    add(receipt_path)
    for name, checksum in receipt.get("artifacts", {}).items():
        path = (attempt / name).resolve()
        if attempt not in path.parents:
            raise ValueError("Receipt artifact escapes attempt")
        add(path, checksum)

    # _prepared reads one task/fold/seed record. Its selected profile graph,
    # initial state and task labels/folds are bound; unrelated jobs are not
    # traversed through the plan or an authorization's historical provenance.
    plan = _read(plan_path)
    # Bind the same amendment for the original successful fit, whose historical
    # start record intentionally predates the amendment and stays unchanged.
    from .runtime_amendment import NAME
    amendment_path = plan_path.parent / NAME
    if amendment_path.is_file():
        add(amendment_path)
        add(amendment_path.with_name(amendment_path.stem + ".seal.json"))
        amendment = _read(amendment_path)
        for name in ("approval", "proof", "before_execution"):
            add_ref(amendment[name], amendment_path.parent)
    if "tasks" in plan:
        job = receipt["job"]
        task = plan["tasks"][job["task_id"]]
        prepared_path = add_ref(task["prepared"]["%d/%d" % (job["fold"], job["seed"])],
                                plan_path.parent)
        prepared = _read(prepared_path)
        entry = prepared["profiles"][job["profile"]]
        for name in ("graph", "initial"):
            add_ref(entry[name], prepared_path.parent)
        for name in ("labels", "folds"):
            add_ref(task["record"][name], plan_path.parent)

    # Authorization validation checks the start and authorization themselves;
    # only stage B additionally reads its bound interim receipt/report files.
    if "execution_start" in receipt:
        started_path = add_ref(receipt["execution_start"], receipt_path.parent)
        started = _read(started_path)
        authorization_path = add_ref(started["execution_authorization"], started_path.parent)
        authorization = _read(authorization_path)
        if "runtime_amendment" in started:
            amendment_path = add_ref(started["runtime_amendment"], started_path.parent)
            amendment_seal = amendment_path.with_name(amendment_path.stem + ".seal.json")
            add(amendment_seal)
            amendment = _read(amendment_path)
            proof_path = add_ref(amendment["equivalence_proof"], amendment_path.parent)
            proof = _read(proof_path)
            for proof_job in proof["jobs"]:
                for proof_ref in proof_job["refs"].values():
                    add_ref(proof_ref, proof_path.parent)
            # Historical verification validates this ticket's own bound fields,
            # not the live parent's cache anchors nested inside the ticket.
            add_ref(started["execution_ticket"], started_path.parent)
        if "benchmark_runtime_amendment" in started:
            amendment_path = add_ref(started["benchmark_runtime_amendment"], started_path.parent)
            amendment = _read(amendment_path)
            add(amendment_path.with_name(amendment_path.stem + ".seal.json"))
            for name in ("approval", "proof", "before_execution"):
                add_ref(amendment[name], amendment_path.parent)
        if authorization.get("stage") == "B":
            interim_path = add_ref(authorization["interim_receipt"], authorization_path.parent)
            interim = _read(interim_path)
            for report_ref in interim["report_files"].values():
                add_ref(report_ref, interim_path.parent)

    # result.json remains a receipt-bound interim artifact; final_result is
    # the authoritative post-watcher resource record for this protocol.
    result_path = attempt / "final_result.json"
    if "final_result.json" not in receipt.get("artifacts", {}):
        raise ValueError("Final resource result must be bound by the receipt")
    if result_path.exists():
        resources = _read(result_path).get("resources", {})
        for name in ("preflight", "context_ref"):
            if name in resources:
                add_ref(resources[name], result_path.parent)
        if "raw_samples_path" in resources:
            add(_resolve(resources["raw_samples_path"], result_path.parent),
                resources["raw_samples_sha256"])
    # Bind retained adjacent resource evidence as well. Do not recursively
    # reinterpret documentary references embedded in these sidecars.
    for suffix in (".started.json", ".resources.json", ".context.json", ".memory_samples.jsonl"):
        sibling = attempt.with_suffix(suffix)
        if sibling.exists():
            add(sibling)
    for ref in extra_refs:
        add_ref(ref, plan_path.parent)
    return receipt, [records[k] for k in sorted(records)]


def _attempt_inventory(attempt):
    """Do not let a cached receipt hide later attempts or duplicate success."""
    parent = Path(attempt).resolve().parent
    receipts = sorted(parent.glob("attempt_*/receipt.json"))
    if receipts != [Path(attempt).resolve() / "receipt.json"]:
        raise ValueError("Expected exactly one successful attempt for cached job")
    started = list(parent.glob("attempt_*.started.json"))
    successful_match = re.fullmatch(r"attempt_(\d+)", Path(attempt).name)
    if successful_match is None:
        raise ValueError("Invalid successful attempt identity")
    successful_index = int(successful_match.group(1))
    for path in started:
        match = re.fullmatch(r"attempt_(\d+)\.started\.json", path.name)
        if match is None:
            raise ValueError("Invalid started attempt identity")
        if int(match.group(1)) > successful_index:
            raise ValueError("Newer started/incomplete attempt follows successful receipt")
    paths = set(receipts)
    paths.update(started)
    paths.update(parent.glob("attempt_*.failure.json"))
    return [dict(path=str(p.resolve()), sha256=_sha(p), **_stat(p)) for p in sorted(paths)]


def create_cache(cache_root, plan_path, job, attempt, full_verify,
                 acceptance_version, extra_refs=()):
    """Fully accept once, then create an exclusive seal and return its SHA ref.

    full_verify is a zero-argument callback returning the full accepted row
    (including the independent gradient/resource audit), not merely a boolean.
    The caller supplies a fresh generation directory as cache_root.
    """
    if not acceptance_version:
        raise ValueError("Acceptance code version/digest is required")
    plan_path, attempt = Path(plan_path).resolve(), Path(attempt).resolve()
    cache_root = Path(cache_root).resolve()
    if cache_root == attempt or attempt in cache_root.parents:
        raise ValueError("Acceptance cache must not write inside historical attempt")
    identity = _identity(job)
    receipt, before = _dependencies(plan_path, attempt, extra_refs)
    inventory_before = _attempt_inventory(attempt)
    value = full_verify()
    if (not isinstance(value, dict) or value.get("audit", {}).get("passed") is not True
            or value.get("job") != job or Path(value.get("attempt", "")).resolve() != attempt):
        raise ValueError("Cannot cache incomplete, failed or misbound acceptance")
    after_receipt, after = _dependencies(plan_path, attempt, extra_refs)
    inventory_after = _attempt_inventory(attempt)
    if before != after or receipt != after_receipt or inventory_before != inventory_after:
        raise AcceptanceCacheChanged("Dependencies changed during full acceptance")
    # Check all bound SHA values once when establishing the anchor. Cache hits
    # only hash the seal/receipt and small attempt inventory.
    for record in after:
        if _sha(record["path"]) != record["sha256"] or _stat(record["path"]) != {
                key: record[key] for key in ("size", "mtime_ns")}:
            raise AcceptanceCacheChanged("Dependency changed during cache creation: " + record["path"])
    plan_sha = _sha(plan_path)
    destination = cache_root / plan_sha
    for part in identity.split("/"):
        destination /= part
    destination /= attempt.name
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "acceptance_seal.json"
    document = dict(version=VERSION, acceptance_version=acceptance_version,
        recorded_at=datetime.now(timezone.utc).isoformat(), plan_path=str(plan_path),
        plan_sha256=plan_sha, job=copy.deepcopy(job), job_identity=identity,
        attempt=str(attempt), receipt_sha256=_sha(attempt / "receipt.json"),
        dependencies=after, attempt_inventory=inventory_after, accepted=value)
    with path.open("x", encoding="utf8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return dict(path=str(path), sha256=_sha(path))


def verify_cache(cache_ref, *, expected_seal_sha, plan_path, job, attempt,
                 full_verify, acceptance_version):
    """Return a verified cached row; on metadata drift fully check then stop.

    expected_seal_sha must come from the live controller's trusted ref/ticket.
    No on-disk sidecar can substitute for it. Corrupt seals fail immediately;
    artifact metadata drift invokes full_verify for diagnostic evidence, then
    still raises even if content hashes remain equal (e.g. a harmless touch).
    Neither branch replaces or refreshes the historical seal.
    """
    if not isinstance(expected_seal_sha, str) or not _SHA.fullmatch(expected_seal_sha):
        raise ValueError("Trusted expected seal SHA is required")
    path = Path(cache_ref["path"]).resolve()
    if cache_ref.get("sha256") != expected_seal_sha or _sha(path) != expected_seal_sha:
        raise ValueError("Acceptance seal differs from trusted controller anchor")
    doc = _read(path)
    plan_path, attempt = Path(plan_path).resolve(), Path(attempt).resolve()
    if (doc.get("version") != VERSION or doc.get("acceptance_version") != acceptance_version
            or doc.get("plan_path") != str(plan_path) or doc.get("job") != job
            or doc.get("job_identity") != _identity(job) or doc.get("attempt") != str(attempt)):
        raise ValueError("Acceptance cache identity/version differs")
    changed = []
    try:
        if _attempt_inventory(attempt) != doc["attempt_inventory"]:
            changed.append("attempt inventory")
    except (OSError, ValueError) as error:
        changed.append("attempt inventory: " + str(error))
    for record in doc["dependencies"]:
        try:
            if _stat(record["path"]) != {key: record[key] for key in ("size", "mtime_ns")}:
                changed.append(record["path"])
        except (OSError, ValueError) as error:
            changed.append(record["path"] + ": " + str(error))
    try:
        if _sha(attempt / "receipt.json") != doc["receipt_sha256"]:
            changed.append("receipt SHA")
        if _sha(plan_path) != doc["plan_sha256"]:
            changed.append("plan SHA")
    except OSError as error:
        changed.append(str(error))
    if changed:
        try:
            full_verify()
        except Exception as error:
            raise AcceptanceCacheChanged(
                "Cached evidence changed; full acceptance failed; review required: " +
                "; ".join(changed)) from error
        raise AcceptanceCacheChanged(
            "Cached evidence metadata changed; full acceptance passed but review required: " +
            "; ".join(changed))
    return copy.deepcopy(doc["accepted"])
