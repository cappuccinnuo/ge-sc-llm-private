"""EP7 approved adaptation of scripts/DFG/dfg_v2/benchmark_v2/checkpoint.py.
Frozen source SHA256: 6450b4cc74a8b57eb5310a68bf2fb3c43bf34903c2d169db461e4c1dcdd51f79
Numeric training is unchanged; only EdgeSem registration/audit routing differs.
"""
"""Prompt 8H adaptation of experiment/checkpoint.py.\nFrozen source SHA256: 96311a8f8bd2d064d84a396cd2923923c1b4c45cbf5932b865107aaaff4fa3bd
Old-input equivalence is required before execution.
"""
"""Nested v2 binding wrapper; generic ddg-controlled-v1 serialization unchanged."""
from pathlib import Path
import time
import torch
import copy
from .io import checked, read
from scripts.DFG.experiments import checkpoint as native
from scripts.DFG.experiments.common import digest, sha256, tensor_digest
from scripts.DFG.dfg_v2 import AUX_NODE_TYPES
from .model import validate_registration
from scripts.DFG.dfg_v2.benchmark_v2.protocol import PROTOCOL_NAME, PROTOCOL_VERSION, FORWARD_SCOPE, SCORE_ROLE, SELECTION_ROLE

StopMonitor = native.StopMonitor


def build_binding(model, *, task_id, fold, seed, profile, reducer, graph_ref,
                  fold_ref, label_ref, initial_sha256, config, split, support,
                  initialization_record=None):
    schema = validate_registration(model)
    if config.get("layer_impl", "original") != model.dfg_layer_impl:
        raise ValueError("Config layer_impl differs from model")
    binding = dict(protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
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
    if hasattr(model,"edge_profile"):
        binding.update(edge_fields(model))
    return binding


def validate_binding(model, binding, check_files=True, deep=True):
    if binding.get("protocol") == "dfg-v2-nested":
        from scripts.DFG.dfg_v2.experiment.checkpoint import validate_binding as old_validate
        return old_validate(model,binding,check_files=check_files,deep=deep)
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
    validate_registration(model, binding["registered_schema"], deep=deep)
    if (binding.get("canonical") != sorted([list(c) for c in model.etypes_dict])
            or binding.get("auxiliary_node_types") != sorted(set(model.ntypes_dict) & set(AUX_NODE_TYPES))):
        raise ValueError("Canonical/auxiliary binding mismatch")
    if not binding.get("initial_weights_sha256"):
        raise ValueError("Missing initial state SHA")
    if check_files:
        for name in ("graph", "folds", "labels", "label_view", "feature_view", "feature_npz"):
            ref = binding[name]
            if not Path(ref["path"]).is_file() or sha256(ref["path"]) != ref["sha256"]:
                raise ValueError("Bound input changed: " + name)
    if hasattr(model,"edge_profile"):
        for key,value in edge_fields(model).items():
            if binding.get(key) != value:
                raise ValueError("EdgeSem binding differs: "+key)
        if check_files:
            for value in extra_references(binding): checked(value)
    expected = getattr(model,"edge_bound_identity",None)
    if expected is not None and expected != binding:
        raise ValueError("Sealed execution binding differs")
    return binding


def snapshot_input(model, binding):
    from .input_guard import active_guard
    guard = active_guard(model)
    if guard is not None:
        return guard.start(binding)
    validate_binding(model, binding)
    return native.snapshot_input(model, binding)


def save_checkpoint(path, model, expected_input, binding, epoch, monitor, optimizer, scheduler):
    from .input_guard import active_guard
    guard = active_guard(model)
    if guard is not None:
        started = time.monotonic()
        guard.fast_check(binding, "save_before")
        if expected_input != guard.snapshot:
            raise ValueError("Model input changed before checkpoint save")
        result = native.save_checkpoint(path, model, expected_input, binding, epoch, monitor, optimizer, scheduler)
        guard.fast_check(binding, "save_after")
        guard.record_operation("save", path, started)
        return result
    validate_binding(model, binding)
    # This comparison also covers masks/labels/features and actual DGL endpoints.
    if native.snapshot_input(model, binding) != expected_input:
        raise ValueError("Model input changed before checkpoint save")
    return native.save_checkpoint(path, model, expected_input, binding, epoch, monitor, optimizer, scheduler)


def restore_checkpoint(path, model, binding, expected_file_sha256):
    from .input_guard import active_guard
    guard = active_guard(model)
    if guard is not None:
        started = time.monotonic()
        guard.before_restore(binding)
        # Adapted from scripts/DFG/experiments/checkpoint.py::restore_checkpoint
        # Frozen source SHA256: 7ccef05371f0324271986dce7d274f3a81a45a9af0e3fe10e08c018dcdd2fb99
        # Native format/checksum/binding/weight checks are preserved; compare
        # the verified process snapshot instead of rebuilding its fingerprint.
        if sha256(path) != expected_file_sha256:
            raise ValueError("Checkpoint file changed")
        result = torch.load(str(path), map_location=model.device)
        if result.get("format") != "ddg-controlled-v1":
            raise ValueError("Unsupported checkpoint format")
        if result["binding"] != binding or result["binding_sha256"] != digest(binding):
            raise ValueError("Checkpoint experiment binding mismatch")
        if result["model_input"] != guard.snapshot:
            raise ValueError("Checkpoint input differs from the starting process snapshot")
        if tensor_digest(result["state_dict"]) != result["state_sha256"]:
            raise ValueError("Checkpoint weights changed")
        model.load_state_dict(result["state_dict"])
        guard.fast_check(binding, "restore_after")
        guard.record_operation("restore", path, started)
        return result
    validate_binding(model, binding)
    result = native.restore_checkpoint(path, model, binding, expected_file_sha256)
    validate_binding(model, binding)
    return result


def edge_fields(model):
    """Every EdgeSem identity is reproducible from the constructed model."""
    key_rows=[dict(canonical=list(c),key=list(model.edge_key_map[c]))
              for c in sorted(model.edge_key_map)]
    attributes=getattr(model,"edge_attribute_binding",None)
    placebo=getattr(model,"edge_placebo_binding",None)
    refs=copy.deepcopy(getattr(model,"edge_input_refs",{}))
    if attributes is not None:
        refs["attrs_manifest"]=copy.deepcopy(attributes["manifest"])
        refs["f4_manifest"]=read(checked(attributes["manifest"]))["f4_manifest"]
    if placebo is not None:
        refs["f4_manifest"]=copy.deepcopy(placebo["f4_manifest"])
    core=(read(checked(attributes["manifest"]))["core_indices"] if attributes else [])
    return dict(edge_profile=model.edge_profile,edge_version=model.edge_version,
        edge_key_map_sha256=digest(key_rows),edge_seeds=copy.deepcopy(model.edge_seeds),
        edge_input_refs=refs,core_indices=list(core),
        edge_indices=list(getattr(model,"edge_indices",())),
        edge_attribute_binding=copy.deepcopy(attributes),
        edge_placebo_binding=copy.deepcopy(placebo))


def extra_references(binding):
    """Data dependencies only; archive verification binds runtime separately."""
    refs={}
    def add(value):
        if value is None:return
        if "path" not in value or "sha256" not in value:raise ValueError("Invalid EdgeSem file reference")
        prior=refs.get(value["path"])
        if prior is not None and prior["sha256"]!=value["sha256"]:raise ValueError("Conflicting EdgeSem file reference")
        refs[value["path"]]=value
    for name,value in binding.get("edge_input_refs",{}).items():
        add(value)
        if name in ("attrs_manifest","f4_manifest"):
            data=read(checked(value))
            for field in ("attrs","keys","edges","f4_manifest"):
                if field in data:
                    add(data[field])
                    if field=="f4_manifest":
                        f4=read(checked(data[field]));add(f4["edges"])
    return list(refs.values())


def freeze_binding(model,binding):
    """Anchor config/initial/source fields for every subsequent checkpoint use."""
    if hasattr(model,"edge_bound_identity"):raise ValueError("Execution binding already fixed")
    validate_binding(model,binding)
    model.edge_bound_identity=copy.deepcopy(binding)
    return binding
