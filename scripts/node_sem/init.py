"""NodeSem zero-step initialization; frozen semantic seed functions are reused.

Reference: scripts/DFG/dfg_v2/experiment/init.py
SHA256: c37916d086a24cc56a0c120ab1d1f0e71da63590cc4e6814362518e1d6adfc05
"""
import math
import torch
from torch import nn

from scripts.DFG.dfg_v2.experiment.init import parameter_seed, seeds
from scripts.DFG.experiments.common import tensor_digest
from .checkpoint_io import load_checked

VERSION = "nodesem-semantic-initialization-v1"


def checked_initial(reference, task_id, fold, profile, seed=1, spec_digest=None):
    """Read only a sealed, authorized zero-step file and verify its identity."""
    payload = load_checked(reference, map_location="cpu")
    expected = dict(task_id=task_id, fold=fold, profile=profile, seed=seed)
    if (payload.get("kind") != "untrained_initial"
            or payload.get("optimizer_steps") != 0
            or any(payload.get(k) != v for k, v in expected.items())):
        raise ValueError("Initial-state identity or zero-step provenance differs")
    granularity = task_id.rsplit("_", 1)[-1]
    random_state = seeds(granularity, fold, seed)
    if any(payload.get(k + "_seed") != value for k, value in random_state.items()):
        raise ValueError("Initial-state random seed differs")
    actual = tensor_digest(payload["state_dict"])
    if (actual != payload.get("state_sha256")
            or actual != reference.get("state_sha256")):
        raise ValueError("Initial tensor digest differs")
    if spec_digest is not None and payload.get("feature_spec_sha256") != spec_digest:
        raise ValueError("Initial feature specification differs")
    return payload


def initial_state(model, spec, task_id, fold, profile, h8_initial_ref):
    """Return detached CPU weights; never mutate the model or global RNG."""
    payload = checked_initial(h8_initial_ref, task_id, fold, profile)
    if (model.dfg_profile != profile
            or model.dfg_task != task_id.rsplit("_", 1)[-1]):
        raise ValueError("Receiving model identity differs")
    if (any(getattr(model, name, 0) != 0 for name in ("optimizer_steps", "_dfg_optimizer_steps"))
            or any(p.grad is not None for p in model.parameters())):
        raise ValueError("Receiving model must be untrained without gradients")
    old = payload["state_dict"]
    current = model.state_dict()
    if spec.name == "S0":
        if set(current) != set(old):
            raise ValueError("S0 parameter dictionary differs")
        for name in current:
            if current[name].shape != old[name].shape or current[name].dtype != old[name].dtype:
                raise ValueError("S0 parameter shape/dtype differs: " + name)
        state = {name: old[name].detach().cpu().clone() for name in current}
        if tensor_digest(state) != payload["state_sha256"]:
            raise ValueError("S0 is not the exact historical zero-step state")
        return state, tensor_digest(state)

    modules = dict(model.named_modules())
    shared_keys = {k for k in current if k.startswith(("gcs.", "classify."))}
    old_shared = {k for k in old if k.startswith(("gcs.", "classify."))}
    # The zero-layer diagnostic intentionally omits graph layers.
    expected_shared = old_shared if spec.layers != 0 else {k for k in old_shared if k.startswith("classify.")}
    if shared_keys != expected_shared:
        raise ValueError("Shared graph/classifier parameter dictionary differs")
    state = {}
    identity = [task_id, fold, profile, spec.digest()]
    for name, source in current.items():
        value = torch.empty_like(source, device="cpu")
        if name in shared_keys:
            if source.shape != old[name].shape or source.dtype != old[name].dtype:
                raise ValueError("Shared parameter shape/dtype differs: " + name)
            state[name] = old[name].detach().cpu().clone()
            continue
        if not name.startswith(("adapt_ws.", "nodesem_shared.")):
            raise ValueError("Unexpected receiving parameter: " + name)
        module_path, field = name.rsplit(".", 1)
        module = modules[module_path]
        generator = torch.Generator(device="cpu")
        generator.manual_seed(parameter_seed(payload["constructor_seed"], name, identity))
        if isinstance(module, nn.EmbeddingBag) and field == "weight":
            value.normal_(0.0, 0.02, generator=generator)
            value[0].zero_()
        elif isinstance(module, nn.Linear):
            if field == "weight":
                bound = math.sqrt(6.0 / float(module.in_features + module.out_features))
                value.uniform_(-bound, bound, generator=generator)
            elif field == "bias":
                value.zero_()
            else:
                raise ValueError("Unknown Linear parameter: " + name)
        elif isinstance(module, nn.LayerNorm):
            if field == "weight":
                value.fill_(1)
            elif field == "bias":
                value.zero_()
            else:
                raise ValueError("Unknown LayerNorm parameter: " + name)
        else:
            raise ValueError("Unsupported new parameter module: " + name)
        state[name] = value
    return state, tensor_digest(state)
