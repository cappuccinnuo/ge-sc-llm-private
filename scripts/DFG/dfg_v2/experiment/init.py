"""Prompt 7 semantic initialization; only the receiving profiles are changed.

G0-shared parameters are copied exactly by semantic identity. The approved
policy for new relation rows uses independent semantic draws scaled by each
receiving profile's full-bank Xavier bound. New rows shared by two enhanced
profiles therefore need not be bitwise equal if their bank sizes differ.
Freshness is a caller provenance contract, with defensive checks below.

Reference: scripts/DFG/state/stage_f/initialization.py
SHA256: 0c2323a568cec07c9f73c269f9e3f180a4750581dfd807a8956bd6b4602832f8
Constructor: sco_models/model_hgt.py
SHA256: 4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947
"""
import hashlib
import json
import math
import re
import torch
from scripts.DFG.experiments.protocol import _state_digest, _validate_schema
from .. import AUX_NODE_TYPES, FORWARD_RELATIONS
from ..model import validate_registration

INITIALIZATION_VERSION = "dfg-v2-semantic-family-own-bank-v1"
NEW_RELATION_POLICY = "semantic_draws_profile_full_bank_xavier"
_RELATION = re.compile(r"^gcs\.\d+\.relation_(pri|att|msg)$")
_SKIP = re.compile(r"^gcs\.\d+\.skip$")
_NODE = re.compile(r"^(adapt_ws)\.(\d+)\.(weight|bias)$")
_LAYER_NODE = re.compile(
    r"^(gcs\.\d+\.(?:k_linears|q_linears|v_linears|a_linears|norms))"
    r"\.(\d+)\.(weight|bias)$")

def seeds(task, fold, seed=1):
    """Preserve the seed-1 constructor and fit rules from RECON."""
    if task not in ("node", "contract"):
        raise ValueError("Initialization task must be node or contract")
    if type(fold) is not int or not 0 <= fold < (10 if task == "node" else 5):
        raise ValueError("Fold outside frozen K-fold range")
    if type(seed) is not int or seed < 1:
        raise ValueError("Seed must be a positive integer")
    constructor = 10000 + fold + (1000 if task == "contract" else 0)
    constructor += 100000 * (seed - 1)
    return {"constructor": constructor, "fit": constructor + 1000000}

def parameter_seed(anchor_seed, name, identity):
    data = json.dumps([int(anchor_seed), name, identity], sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return int(hashlib.sha256(data).hexdigest()[:15], 16)

def full_bank_bound(tensor):
    fan_in, fan_out = torch.nn.init._calculate_fan_in_and_fan_out(tensor)
    return math.sqrt(6.0 / float(fan_in + fan_out))

def _uniform(value, bound, anchor_seed, name, identity):
    generator = torch.Generator(device="cpu")
    generator.manual_seed(parameter_seed(anchor_seed, name, identity))
    value.uniform_(-bound, bound, generator=generator)

def _check_fresh(model):
    # This is not forensic detection of arbitrary external trained weights.
    # The runner must bind constructor identity/seed and zero optimizer steps.
    for attr in ("optimizer_steps", "_dfg_optimizer_steps"):
        if getattr(model, attr, 0) != 0:
            raise ValueError("Family models must have zero optimizer steps")
    if any(p.grad is not None for p in model.parameters()):
        raise ValueError("Family models must be fresh without gradients")

def _semantic(state, nodes, edges):
    _validate_schema(nodes)
    _validate_schema(edges, canonical=True)
    inverse = {index: node for node, index in nodes.items()}
    result = {}
    for name, value in state.items():
        value = value.detach().cpu()
        if _RELATION.match(name):
            if value.shape[0] != len(edges):
                raise ValueError("Relation bank/schema mismatch")
            for canonical, index in edges.items():
                key = name + "|" + json.dumps(canonical, separators=(",", ":"))
                result[key] = value[index].clone()
        elif _SKIP.match(name):
            if value.shape != (len(nodes),):
                raise ValueError("Skip vector/schema mismatch")
            for node, index in nodes.items():
                result[name + "|" + node] = value[index].clone()
        else:
            match = _NODE.match(name) or _LAYER_NODE.match(name)
            if match:
                prefix, index, suffix = match.groups()
                key = prefix + "|" + inverse[int(index)] + "|" + suffix
            elif name in ("classify.weight", "classify.bias"):
                key = name
            else:
                raise ValueError("Unknown parameter needs an explicit rule: " + name)
            if key in result:
                raise ValueError("Duplicate semantic parameter identity")
            result[key] = value.clone()
    return result

def semantic_state(model):
    """Independent CPU parameter slices keyed by semantic identity."""
    return _semantic(model.state_dict(), model.ntypes_dict, model.etypes_dict)

def initialize_family(models, anchor_seed):
    """Initialize fresh models from a caller-constructed G0 anchor.

    G0 must have been constructed with anchor_seed. No global RNG is consumed.
    No checkpoint is accepted here. Receivers are fully validated before any
    weights are loaded; repeated calls are deterministic and G0 is untouched.
    """
    if type(anchor_seed) is not int or anchor_seed < 0:
        raise ValueError("anchor_seed must be a nonnegative integer")
    if "G0" not in models or len({id(m) for m in models.values()}) != len(models):
        raise ValueError("Provide distinct profile models with a G0 anchor")
    anchor = models["G0"]
    for profile, model in models.items():
        _check_fresh(model)
        if model.dfg_profile != profile:
            raise ValueError("Profile key differs from model profile")
        validate_registration(model)
        if model.dfg_task != anchor.dfg_task:
            raise ValueError("Cannot mix classifier tasks")
        if model.node_feature != anchor.node_feature:
            raise ValueError("Cannot mix feature modes")
        if not set(anchor.ntypes_dict).issubset(model.ntypes_dict):
            raise ValueError("A profile removed G0 node types")
        if set(model.ntypes_dict) - set(anchor.ntypes_dict) - set(AUX_NODE_TYPES):
            raise ValueError("Only registered auxiliary node types may be added")
        if not set(anchor.etypes_dict).issubset(model.etypes_dict):
            raise ValueError("A profile removed G0 canonical relations")
    source = {k: v.detach().cpu().clone() for k, v in anchor.state_dict().items()}
    anchor_sha = _state_digest(source)
    common_source = semantic_state(anchor)
    prepared, records = {}, {}
    for profile, model in models.items():
        target = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        inverse = {i: n for n, i in model.ntypes_dict.items()}
        bounds = {}
        if profile != "G0":
            for name, value in target.items():
                if _RELATION.match(name):
                    if name not in source or value.shape[1:] != source[name].shape[1:]:
                        raise ValueError("Family relation layer shapes differ: " + name)
                    if value.shape[0] != len(model.etypes_dict):
                        raise ValueError("Relation bank/schema mismatch")
                    bound = None if name.endswith("relation_pri") else full_bank_bound(value)
                    bounds[name] = bound
                    for canonical, index in model.etypes_dict.items():
                        if canonical in anchor.etypes_dict:
                            value[index].copy_(source[name][anchor.etypes_dict[canonical]])
                        else:
                            relation = canonical[1]
                            if relation not in FORWARD_RELATIONS and not (
                                    relation.startswith("REV_") and relation[4:] in FORWARD_RELATIONS):
                                raise ValueError("Unknown new canonical relation")
                            if bound is None:
                                value[index].fill_(1)
                            else:
                                _uniform(value[index], bound, anchor_seed, name, canonical)
                elif _SKIP.match(name):
                    if name not in source or value.shape != (len(model.ntypes_dict),):
                        raise ValueError("Family skip layer/schema mismatch")
                    for node, index in model.ntypes_dict.items():
                        if node in anchor.ntypes_dict:
                            value[index].copy_(source[name][anchor.ntypes_dict[node]])
                        else:
                            value[index].fill_(1)
                else:
                    match = _NODE.match(name) or _LAYER_NODE.match(name)
                    if match:
                        prefix, index, suffix = match.groups()
                        node = inverse[int(index)]
                        if node in anchor.ntypes_dict:
                            source_name = prefix + "." + str(anchor.ntypes_dict[node]) + "." + suffix
                        else:
                            source_name = None
                            if prefix.endswith(".norms"):
                                value.fill_(1 if suffix == "weight" else 0)
                            else:
                                weight = target[prefix + "." + index + ".weight"]
                                if weight.ndim != 2 or weight.shape[1] <= 0:
                                    raise ValueError("Expected a Linear parameter")
                                _uniform(value, 1.0 / math.sqrt(weight.shape[1]),
                                         anchor_seed, prefix + "." + suffix, node)
                    elif name in ("classify.weight", "classify.bias"):
                        source_name = name
                    else:
                        raise ValueError("Unknown parameter needs an explicit rule: " + name)
                    if source_name is not None:
                        if source_name not in source or value.shape != source[source_name].shape:
                            raise ValueError("Common parameter shape mismatch: " + name)
                        value.copy_(source[source_name])
        semantic = _semantic(target, model.ntypes_dict, model.etypes_dict)
        if not set(common_source).issubset(semantic):
            raise ValueError("Family removed semantic G0 parameters")
        common = {key: semantic[key] for key in common_source}
        if any(not torch.equal(common[key], value) for key, value in common_source.items()):
            raise AssertionError("G0-shared initial parameters differ")
        extras = {key: value for key, value in semantic.items() if key not in common_source}
        records[profile] = {
            "state_sha256": _state_digest(target),
            "shared_semantic_sha256": _state_digest(common),
            "new_semantic_sha256": _state_digest(extras),
            "shared_tensor_count": len(common), "new_tensor_count": len(extras),
            "full_bank_xavier_bounds": bounds,
            "canonical_order": [list(c) for c, _ in sorted(model.etypes_dict.items(), key=lambda x: x[1])],
            "node_type_alignment": {n: [anchor.ntypes_dict.get(n), model.ntypes_dict[n]]
                                    for n in sorted(model.ntypes_dict)},
            "optimizer_steps": 0,
        }
        prepared[profile] = target
    for profile, model in models.items():
        if profile != "G0":
            model.load_state_dict(prepared[profile], strict=True)
    if _state_digest(anchor.state_dict()) != anchor_sha:
        raise AssertionError("Family initialization mutated G0")
    return {"initialization_version": INITIALIZATION_VERSION,
            "anchor_seed": anchor_seed, "anchor_state_sha256": anchor_sha,
            "new_relation_policy": NEW_RELATION_POLICY,
            "freshness_contract": "caller supplies fresh constructor models; no checkpoints",
            "profiles": records}
