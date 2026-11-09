"""NS-P8a initialization: exact S4 common tensors, semantic-seeded new TEACHER tensors."""
from pathlib import Path
import torch
from scripts.DFG.experiments.common import tensor_digest
from .feature_spec import FeatureSpec
from .init import checked_initial, initial_state

VERSION = "nodesem-nc1-s4-common-initial-v1"


def validate_rebuilt(state, job):
    if tensor_digest(state) != job["initial"]["state_sha256"]:
        raise ValueError("Rebuilt S4 state differs from sealed N-A digest")
    return state


def baseline_state(job, model=None):
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read
    spec = FeatureSpec.from_json(read(checked(job["spec"])))
    if spec.digest() != job["spec_sha256"] or spec.name != "S4":
        raise ValueError("Wrong baseline feature specification")
    if Path(job["initial"]["path"]).exists():
        payload = checked_initial(job["initial"], job["task_id"], job["fold"],
                                  job["profile"], spec_digest=spec.digest())
        return payload["state_dict"], "existing_NA_initial"
    if model is None:
        raise ValueError("Missing S4 initial requires deterministic reconstruction model")
    state, _ = initial_state(model, spec, job["task_id"], job["fold"],
                             job["profile"], job["h8_initial"])
    validate_rebuilt(state, job)
    return state, "reconstructed_exact_NA_digest"


def merge_common(candidate, baseline):
    if not baseline or not set(baseline) < set(candidate):
        raise ValueError("S6 must strictly extend the complete S4 state")
    extra = set(candidate) - set(baseline)
    if any(not (k.startswith("adapt_ws.") and
                (".norm.teacher." in k or ".proj.teacher." in k)) for k in extra):
        raise ValueError("Unexpected non-TEACHER parameter")
    merged = {k: v.detach().cpu().clone() for k, v in candidate.items()}
    for k, value in baseline.items():
        if candidate[k].shape != value.shape or candidate[k].dtype != value.dtype:
            raise ValueError("Common S4 tensor shape/dtype differs: " + k)
        merged[k] = value.detach().cpu().clone()
    return merged, dict(common_keys=len(baseline), teacher_keys=sorted(extra),
                        baseline_state_sha256=tensor_digest(baseline),
                        common_bitwise_equal=all(torch.equal(merged[k], baseline[k]) for k in baseline))


def paired_state(model, spec, job, baseline):
    state, _ = initial_state(model, spec, job["task_id"], job["fold"],
                             job["profile"], job["h8_initial"])
    return merge_common(state, baseline)
