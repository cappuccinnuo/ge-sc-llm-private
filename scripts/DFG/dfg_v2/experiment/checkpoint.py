"""Nested v2 binding wrapper; generic ddg-controlled-v1 serialization unchanged."""
from pathlib import Path
from scripts.DFG.experiments import checkpoint as native
from scripts.DFG.experiments.common import digest, sha256
from scripts.DFG.dfg_v2 import AUX_NODE_TYPES
from scripts.DFG.dfg_v2.model import validate_registration
from .protocol import PROTOCOL_NAME, PROTOCOL_VERSION, FORWARD_SCOPE, SCORE_ROLE, SELECTION_ROLE

StopMonitor = native.StopMonitor


def build_binding(model, *, task_id, fold, seed, profile, reducer, graph_ref,
                  fold_ref, label_ref, initial_sha256, config, split, support,
                  initialization_record=None):
    schema = validate_registration(model)
    if config.get("layer_impl", "original") != model.dfg_layer_impl:
        raise ValueError("Config layer_impl differs from model")
    return dict(protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
        score_role=SCORE_ROLE, selection_role=SELECTION_ROLE, forward_scope=FORWARD_SCOPE,
        task_id=task_id, task=model.dfg_task, fold=fold, seed=seed, profile=profile,
        reducer=reducer, layer_impl=model.dfg_layer_impl, registered_schema=schema,
        canonical=sorted([list(c) for c in model.etypes_dict]),
        auxiliary_node_types=sorted(set(model.ntypes_dict) & set(AUX_NODE_TYPES)),
        auxiliary_policy="excluded from supervision, scoring and contract pooling",
        graph=graph_ref, folds=fold_ref, labels=label_ref,
        initial_weights_sha256=initial_sha256, effective_config_sha256=digest(config),
        split=split, support_sha256=digest(support),
        initialization=initialization_record)


def validate_binding(model, binding, check_files=True):
    if (binding.get("protocol") != PROTOCOL_NAME
            or binding.get("protocol_version") != PROTOCOL_VERSION
            or binding.get("score_role") != SCORE_ROLE
            or binding.get("selection_role") != SELECTION_ROLE
            or binding.get("forward_scope") != FORWARD_SCOPE):
        raise ValueError("Nested experiment protocol/role binding mismatch")
    if (binding.get("task") != model.dfg_task
            or binding.get("profile") != model.dfg_profile
            or binding.get("reducer") != model.dfg_reducer
            or binding.get("layer_impl", "original") != model.dfg_layer_impl):
        raise ValueError("Model/profile/reducer/layer_impl binding mismatch")
    validate_registration(model, binding["registered_schema"])
    if (binding.get("canonical") != sorted([list(c) for c in model.etypes_dict])
            or binding.get("auxiliary_node_types") != sorted(set(model.ntypes_dict) & set(AUX_NODE_TYPES))):
        raise ValueError("Canonical/auxiliary binding mismatch")
    if not binding.get("initial_weights_sha256"):
        raise ValueError("Missing initial state SHA")
    if check_files:
        for name in ("graph", "folds", "labels"):
            ref = binding[name]
            if not Path(ref["path"]).is_file() or sha256(ref["path"]) != ref["sha256"]:
                raise ValueError("Bound input changed: " + name)
    return binding


def snapshot_input(model, binding):
    validate_binding(model, binding)
    return native.snapshot_input(model, binding)


def save_checkpoint(path, model, expected_input, binding, epoch, monitor, optimizer, scheduler):
    validate_binding(model, binding)
    # This comparison also covers masks/labels/features and actual DGL endpoints.
    if native.snapshot_input(model, binding) != expected_input:
        raise ValueError("Model input changed before checkpoint save")
    return native.save_checkpoint(path, model, expected_input, binding, epoch, monitor, optimizer, scheduler)


def restore_checkpoint(path, model, binding, expected_file_sha256):
    validate_binding(model, binding)
    result = native.restore_checkpoint(path, model, binding, expected_file_sha256)
    validate_binding(model, binding)
    return result
