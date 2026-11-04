"""Approved local advisory resource policy; no model or training math changes.

Epoch durations come from the frozen trainer's existing history.jsonl. Timing
alerts are observations, not evidence that WDDM moved allocations to host RAM.
"""
import json
import math
from pathlib import Path
import statistics


TIMING_VERSION = "local-dev-first-three-epoch-median-v1"
TIMING_CAVEAT = (
    "A duration above twice the first-three-epoch median is only a possible "
    "memory-spill warning. Checkpoint I/O, initialization, CPU/system load, "
    "and other GPU activity can also explain a slowdown. Whole-card samples "
    "and allocator/context arithmetic do not prove memory paging."
)


def _nonnegative_number(value, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise ValueError("Invalid local resource measurement: " + name)
    return value


def timing_summary(rows):
    """Use a fixed first-three median, testing only subsequent epochs."""
    durations = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or type(row.get("epoch")) is not int or row["epoch"] != index:
            raise ValueError("Epoch timing identities must be contiguous from zero")
        durations.append(_nonnegative_number(row.get("seconds"), "epoch seconds"))
    baseline = statistics.median(durations[:3]) if len(durations) >= 3 else None
    warnings = [index for index in range(3, len(durations))
                if durations[index] > 2 * baseline]
    status = ("insufficient_first_three_epochs" if len(durations) < 3
              else "baseline_ready_no_later_epochs" if len(durations) == 3 else "evaluated")
    return dict(version=TIMING_VERSION, status=status, epoch_seconds=durations,
                completed_epochs=len(durations),
                baseline_first_three_median_seconds=baseline,
                comparison_rule="epoch >= 3 and seconds > 2 * fixed first-three median",
                possible_memory_spill_epochs=warnings,
                possible_memory_spill=bool(warnings), caveat=TIMING_CAVEAT)


def read_epoch_timing(history_path):
    path = Path(history_path)
    rows = ([json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
            if path.exists() else [])
    return timing_summary(rows)


def local_resource_class(observed_base, history_path):
    """Preserve sampling/context accounting; low free VRAM becomes advisory."""
    from .resources import MemoryGateError

    class LocalResources(observed_base):
        def __init__(self):
            super().__init__()
            self.warned_tight = False
            self.warned_epochs = set()

        def check(self):
            measured = self.sample()
            if self.cuda and not measured:
                raise MemoryGateError("Current whole-card memory measurement failed; refusing stale sample")
            if self.cuda and not self.samples:
                raise MemoryGateError("Whole-card free memory measurement unavailable")
            if self.cuda and min(self.samples) < 100 and not self.warned_tight:
                print("local_dev_v1 advisory: memory_tight=true; observed minimum free VRAM "
                      "{:.1f} MiB; low free memory alone does not stop this job.".format(
                          min(self.samples)), flush=True)
                self.warned_tight = True
            timing = read_epoch_timing(history_path)
            for epoch in timing["possible_memory_spill_epochs"]:
                if epoch not in self.warned_epochs:
                    print("local_dev_v1 advisory: possible_memory_spill at epoch {} "
                          "({:.3f}s > 2 x {:.3f}s); this timing change does not prove paging.".format(
                              epoch + 1, timing["epoch_seconds"][epoch],
                              timing["baseline_first_three_median_seconds"]), flush=True)
                    self.warned_epochs.add(epoch)

        def summary(self):
            result = super().summary()
            minimum = result.get("minimum_free_mib")
            timing = read_epoch_timing(history_path)
            result.update(memory_tight=minimum is not None and minimum < 100,
                          possible_memory_spill=timing["possible_memory_spill"],
                          epoch_timing=timing)
            return result

    return LocalResources


def validate_local_resource_summary(resources, policy, history_path, samples):
    """Recompute all advisory fields from frozen raw samples and epoch history."""
    from .preflight import LOCAL_DEV_POLICY, validate_policy
    if validate_policy(policy) != LOCAL_DEV_POLICY:
        raise ValueError("Local summary requires the exact local_dev_v1 policy")
    if resources.get("resource_policy") != policy:
        raise ValueError("Local resource policy differs from the sealed plan")
    if not samples:
        raise ValueError("Local resource samples are missing")
    minimum = min(_nonnegative_number(row.get("free_mib"), "free_mib") for row in samples)
    if resources.get("minimum_free_mib") != minimum:
        raise ValueError("Local resource minimum differs from raw observations")
    timing = read_epoch_timing(history_path)
    if resources.get("epoch_timing") != timing:
        raise ValueError("Local epoch timing summary differs from recorded history")
    if (resources.get("memory_tight") is not (minimum < 100)
            or resources.get("possible_memory_spill") is not timing["possible_memory_spill"]):
        raise ValueError("Local advisory flags differ from raw observations")


def audit_local_resources(resources, policy):
    """Pilot resource acceptance; formal receipt validation remains required."""
    from .preflight import LOCAL_DEV_POLICY, validate_policy
    if validate_policy(policy) != LOCAL_DEV_POLICY or resources.get("resource_policy") != policy:
        raise ValueError("Local pilot resources require an explicitly matching sealed policy")
    if resources.get("device") != "cuda":
        raise ValueError("GPU resources must describe CUDA execution")
    for key in ("minimum_free_mib", "peak_allocated_mib", "peak_reserved_mib", "seconds"):
        _nonnegative_number(resources.get(key), key)
    count = resources.get("memory_samples")
    if type(count) is not int or count < 1:
        raise ValueError("GPU memory samples are missing")
    timing = resources.get("epoch_timing", {})
    durations = timing.get("epoch_seconds")
    if not isinstance(durations, list):
        raise ValueError("Local epoch durations are missing")
    recomputed = timing_summary([dict(epoch=i, seconds=value) for i, value in enumerate(durations)])
    if timing != recomputed:
        raise ValueError("Local timing fields are inconsistent")
    tight = resources["minimum_free_mib"] < 100
    if (resources.get("memory_tight") is not tight
            or resources.get("possible_memory_spill") is not recomputed["possible_memory_spill"]):
        raise ValueError("Local resource flags are inconsistent")
    return dict(minimum_free_mib=resources["minimum_free_mib"],
                below_300_mib_warning=resources["minimum_free_mib"] < 300,
                resource_policy=policy["version"], memory_tight=tight,
                possible_memory_spill=recomputed["possible_memory_spill"],
                epoch_timing=recomputed)
