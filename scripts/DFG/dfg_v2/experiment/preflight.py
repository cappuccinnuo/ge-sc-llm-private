"""Read-only startup VRAM gate and additional resource observations.

The baseline path uses only the standard library and never initializes CUDA.
Measurements outside the Torch allocator remain unattributed estimates:
driver reservations, this process, and other processes cannot be separated by
whole-card readings alone.
"""
import copy
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


DEFAULT_PREFLIGHT_POLICY = dict(
    version="dfg-v2-vram-preflight-v1",
    baseline_minimum_free_mib=3000.0,
    running_minimum_free_mib=100.0,
    sampling_seconds=0.5,
    process_scope="fresh_process_one_job",
)
LOCAL_DEV_POLICY = dict(DEFAULT_PREFLIGHT_POLICY, version="local_dev_v1")

CAVEATS = [
    "Whole-card memory is not a per-process measurement.",
    "CUDA/DGL/driver allocations outside the Torch allocator belong partly to this process.",
    "Context initialization differences can include concurrent changes by other processes.",
    "Later lazy library allocations are not necessarily included in the initial context observation.",
    "Peak reserved and minimum free are not necessarily observed at the same instant.",
    "Total, used, and free may not sum due to driver/system reservations; raw readings are retained.",
]
QUERY_ARGV = [
    "nvidia-smi",
    "--query-gpu=uuid,memory.total,memory.used,memory.free",
    "--format=csv,noheader,nounits",
]


class PreflightError(RuntimeError):
    def __init__(self, message, receipt=None):
        super().__init__(message)
        self.receipt = receipt


class PreflightBlocked(PreflightError):
    pass


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != set(DEFAULT_PREFLIGHT_POLICY):
        raise ValueError("Invalid preflight policy fields")
    registered = (LOCAL_DEV_POLICY if policy.get("version") == "local_dev_v1"
                  else DEFAULT_PREFLIGHT_POLICY)
    for key, expected in registered.items():
        value = policy[key]
        if key == "baseline_minimum_free_mib" and registered is DEFAULT_PREFLIGHT_POLICY:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Invalid baseline memory threshold")
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Invalid baseline memory threshold")
        elif value != expected or isinstance(value, bool):
            raise ValueError("Frozen preflight policy differs: " + key)
    return copy.deepcopy(policy)


def _cuda_initialized():
    # Inspect an already imported Torch only; importing this module does not
    # import Torch, query its runtime, or allocate device memory.
    module = sys.modules.get("torch")
    cuda = getattr(module, "cuda", None) if module is not None else None
    return bool(cuda is not None and cuda.is_initialized())


def query_baseline():
    """Read one GPU via nvidia-smi without importing Torch or creating CUDA."""
    started = time.time()
    monotonic_started = time.monotonic()
    raw = subprocess.check_output(
        QUERY_ARGV, timeout=5, stderr=subprocess.PIPE
    ).decode("utf-8").strip()
    rows = list(csv.reader(io.StringIO(raw)))
    if len(rows) != 1 or len(rows[0]) != 4:
        raise ValueError("Expected exactly one GPU with UUID, total, used, free")
    uuid, total, used, free = [value.strip() for value in rows[0]]
    if not uuid.startswith("GPU-") or len(uuid) <= 4:
        raise ValueError("GPU UUID unavailable")
    values = [float(total), float(used), float(free)]
    if (not all(math.isfinite(value) for value in values)
            or values[0] <= 0 or any(value < 0 for value in values[1:])
            or any(value > values[0] for value in values[1:])):
        raise ValueError("Invalid whole-card memory measurement")
    return dict(
        unix_seconds=started, monotonic_seconds=monotonic_started,
        elapsed_seconds=time.monotonic()-monotonic_started,
        uuid=uuid, total_mib=values[0], used_mib=values[1],
        free_mib=values[2], unaccounted_mib=values[0]-values[1]-values[2],
        raw=raw, command=list(QUERY_ARGV),
    )


def _same_device(baseline, observed):
    if (baseline["uuid"] != observed["uuid"]
            or baseline["total_mib"] != observed["total_mib"]):
        raise ValueError("Observed GPU identity or total memory changed")


def _write_receipt(output_dir, receipt):
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        path = directory / ("preflight_{:03d}.json".format(index))
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(receipt, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            break
        except FileExistsError:
            index += 1
    returned = copy.deepcopy(receipt)
    returned["receipt_ref"] = dict(path=str(path),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return returned


def run_preflight(job, plan_sha256, output_dir, policy, argv=None):
    """Write a startup receipt; stop before an attempt when the gate fails."""
    receipt = dict(
        version=policy.get("version") if isinstance(policy, dict) else None, job=copy.deepcopy(job),
        plan_sha256=plan_sha256, unix_seconds=time.time(), pid=os.getpid(),
        argv=list(sys.argv if argv is None else argv), baseline=None,
        status="preflight_error", cuda_initialized_before=None,
        cuda_initialized_after=None, policy=copy.deepcopy(policy),
        process_scope="fresh_process_one_job",
    )
    blocked = False
    try:
        validate_policy(policy)
        if (not isinstance(plan_sha256, str) or len(plan_sha256) != 64
                or any(c not in "0123456789abcdef" for c in plan_sha256)):
            raise ValueError("Invalid plan SHA256")
        receipt["cuda_initialized_before"] = _cuda_initialized()
        if receipt["cuda_initialized_before"]:
            raise ValueError("Fresh process required; CUDA already initialized")
        receipt["baseline"] = query_baseline()
        receipt["cuda_initialized_after"] = _cuda_initialized()
        if receipt["cuda_initialized_after"]:
            raise ValueError("CUDA initialized during preflight")
        blocked = receipt["baseline"]["free_mib"] < policy["baseline_minimum_free_mib"]
        receipt["status"] = "preflight_blocked" if blocked else "passed"
        if blocked:
            receipt["reason"] = "Baseline free memory below registered threshold"
    except Exception as error:
        receipt["reason"] = str(error)
        receipt["error_type"] = type(error).__name__
        returned = _write_receipt(output_dir, receipt)
        raise PreflightError("Preflight failed: " + str(error), returned) from error
    returned = _write_receipt(output_dir, receipt)
    if blocked:
        raise PreflightBlocked(receipt["reason"], returned)
    return returned


def initialize_context(baseline, device="cuda:0"):
    """Initialize a minimal CUDA/DGL context without random draws or a model.

    This observation is an incremental whole-card difference, not an exact
    attribution of all memory owned by the process.
    """
    if str(device) not in ("cuda", "cuda:0"):
        raise ValueError("Preflight context requires the single CUDA device")
    if _cuda_initialized():
        raise ValueError("CUDA initialized before the recorded context boundary")
    import torch
    import dgl
    torch.cuda.set_device(device)
    torch.cuda.init()
    # A one-element tensor and a one-edge graph touch both CUDA backends.
    # They do not consume random numbers or execute neural-network arithmetic.
    tensor = torch.empty(1, dtype=torch.float32, device=device)
    graph = dgl.graph(([0], [0]), num_nodes=1).to(device)
    torch.cuda.synchronize(device)
    del tensor, graph
    torch.cuda.empty_cache()
    observed = query_baseline()
    _same_device(baseline, observed)
    return dict(
        baseline=copy.deepcopy(baseline), after_initialization=observed,
        free_decrease_mib=baseline["free_mib"]-observed["free_mib"],
        used_increase_mib=observed["used_mib"]-baseline["used_mib"],
        torch_allocated_mib=float(torch.cuda.memory_allocated(device))/1024**2,
        torch_reserved_mib=float(torch.cuda.memory_reserved(device))/1024**2,
        warmup="one-element Torch CUDA tensor and one-node one-edge DGL CUDA graph; no RNG draws",
        caveats=list(CAVEATS),
    )


def make_observed_resources(device, baseline, context, samples_path,
                            minimum_free_mib=100, policy=None, history_path=None):
    """Wrap the frozen Resources gate with raw and near-time-paired telemetry."""
    from .resources import Resources
    import torch

    registered = validate_policy(DEFAULT_PREFLIGHT_POLICY if policy is None else policy)
    local_mode = registered["version"] == "local_dev_v1"
    if local_mode and history_path is None:
        raise ValueError("Local resource policy requires an epoch history path")
    if minimum_free_mib != 100:
        raise ValueError("Running free-memory threshold must remain 100 MiB")
    if str(device) not in ("cuda", "cuda:0"):
        raise ValueError("Observed resources require CUDA")
    _same_device(baseline, context["after_initialization"])
    if context["baseline"] != baseline:
        raise ValueError("Context observation belongs to another baseline")
    path = Path(samples_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reserve a new file, never overwrite prior telemetry.
    with path.open("x", encoding="utf-8"):
        pass

    class ObservedResources(Resources):
        def __init__(self):
            super().__init__(device, minimum_free_mib=minimum_free_mib)
            self.observations = []
            self.observation_lock = threading.Lock()

        def sample(self):
            if not self.cuda:
                return
            with self.observation_lock:
                try:
                    reading = query_baseline()
                    _same_device(baseline, reading)
                    reading["torch_allocated_mib"] = float(
                        torch.cuda.memory_allocated(device))/1024**2
                    reading["torch_reserved_mib"] = float(
                        torch.cuda.memory_reserved(device))/1024**2
                    reading["pairing_completed_unix_seconds"] = time.time()
                    reading["pairing_window_seconds"] = (
                        time.monotonic()-reading["monotonic_seconds"])
                    reading["non_torch_residual_estimate_mib"] = (
                        reading["total_mib"]-reading["free_mib"]
                        -reading["torch_reserved_mib"])
                    reading["context_adjusted_residual_estimate_mib"] = (
                        reading["non_torch_residual_estimate_mib"]
                        -context["free_decrease_mib"])
                    reading["index"] = len(self.observations)
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(reading, sort_keys=True)+"\n")
                    self.observations.append(reading)
                    self.samples.append(reading["free_mib"])
                    return True
                except Exception as error:
                    self.errors.append(str(error))
                    return False

        def summary(self):
            with self.observation_lock:
                result = super().summary()
                peak = result["peak_reserved_mib"]
                free = result["minimum_free_mib"]
                residual = None if free is None else baseline["total_mib"]-free-peak
                result.update(
                    baseline=copy.deepcopy(baseline),
                    context_observation=copy.deepcopy(context),
                    total_mib=baseline["total_mib"],
                    non_torch_residual_estimate_mib=residual,
                    context_adjusted_residual_estimate_mib=(
                        None if residual is None else residual-context["free_decrease_mib"]),
                    residual_formula="total - minimum_free - peak_reserved",
                    context_adjusted_formula="non_torch_residual_estimate - observed_context_free_decrease",
                    residual_attribution="unattributed; not an identified external process",
                    raw_samples_path=str(path),
                    raw_samples_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    paired_sample_count=len(self.observations),
                    caveats=list(CAVEATS),
                )
                return result

    if local_mode:
        from .local_dev import local_resource_class
        return local_resource_class(ObservedResources, history_path)()
    return ObservedResources()
