"""Zero-step initialization of NodeSem models.

Starts from the DFG fold initial state of the same profile (``dfg.train.runner.
initial_states``), so a NodeSem model shares every graph-layer and classifier
tensor with the corresponding DFG model. New input-adapter tensors are drawn from
a seed derived from (fold constructor seed, parameter name, task, fold, profile,
feature spec): Xavier-uniform Linear weights, zero biases, unit LayerNorms, N(0,1)
token embeddings with a zero padding row. S0o keeps the DFG state unchanged.

Extensions of S4 (S5, S6, S8) take every S4 tensor from S4's initial state and draw
only their new modality's tensors; S8 also shares S5's modality-dropout stream.
"""
import math

import torch
from torch import nn

from dfg.train.init import parameter_seed
from dfg.utils import tensor_digest
from nodesem.model import NodeSemAdapter

VERSION = "nodesem-semantic-initialization-v2"


def initial_state(model, spec, task_id, fold, profile, base_state, constructor_seed):
    """Detached CPU initial weights for ``model``; neither model nor global RNG changes."""
    if model.dfg_profile != profile or model.dfg_task != task_id.rsplit("_", 1)[-1]:
        raise ValueError("Receiving model identity differs")
    if any(p.grad is not None for p in model.parameters()):
        raise ValueError("Receiving model must be untrained")
    old, current = base_state, model.state_dict()
    if spec.token_mode == "raw_linear":
        if set(current) != set(old):
            raise ValueError("S0 parameter dictionary differs")
        for name in current:
            if current[name].shape != old[name].shape or current[name].dtype != old[name].dtype:
                raise ValueError("S0 parameter shape/dtype differs: " + name)
        state = {name: old[name].detach().cpu().clone() for name in current}
        return state, tensor_digest(state)
    modules = dict(model.named_modules())
    shared_keys = {k for k in current if k.startswith(("gcs.", "classify."))}
    old_shared = {k for k in old if k.startswith(("gcs.", "classify."))}
    expected_shared = old_shared if spec.layers != 0 else {k for k in old_shared if k.startswith("classify.")}
    if shared_keys != expected_shared:
        raise ValueError("Shared graph/classifier parameter dictionary differs")
    state, identity = {}, [task_id, fold, profile, spec.digest()]
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
        generator.manual_seed(parameter_seed(constructor_seed, name, identity))
        if isinstance(module, nn.EmbeddingBag) and field == "weight":
            value.normal_(0.0, 1.0, generator=generator)
            value[0].zero_()
        elif type(module) is NodeSemAdapter and field == "bias":
            value.zero_()
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


def extend_state(candidate, baseline, modality):
    """Candidate state with every baseline (S4) tensor copied; only ``modality`` tensors stay new."""
    extra = set(candidate) - set(baseline)
    if not baseline or not extra or not set(baseline) < set(candidate):
        raise ValueError("Extension must strictly extend the S4 state")
    marks = (".norm.%s." % modality, ".proj.%s." % modality)
    if any(not (k.startswith("adapt_ws.") and any(m in k for m in marks)) for k in extra):
        raise ValueError("Unexpected new parameter outside the %s modality" % modality)
    merged = {k: v.detach().cpu().clone() for k, v in candidate.items()}
    for k, value in baseline.items():
        if merged[k].shape != value.shape or merged[k].dtype != value.dtype:
            raise ValueError("Common tensor shape/dtype differs: " + k)
        merged[k] = value.detach().cpu().clone()
    return merged, tensor_digest(merged)


def pair_dropout(model, paired_spec):
    """Make every adapter draw modality dropout from ``paired_spec``'s stream (S8 <- S5)."""
    for adapter in model.adapt_ws:
        adapter.spec_digest = paired_spec.digest()
    return model
