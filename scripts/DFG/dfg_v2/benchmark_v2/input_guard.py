"""Prompt 8H adaptation of experiment/input_guard.py.\nFrozen source SHA256: 9b0259334c41b0905605e1af83c6f270b78c5aa0a8423169026fa95ea33413fc
Old-input equivalence is required before execution.
"""
"""Prompt 8B.0 process-local validation around the unchanged numeric trainer.

Inputs are deeply validated at three boundaries. Checkpoint save/restore uses
tensor identities/versions, schema/binding checks, and DGL endpoint equality.
DGL 0.6.1 edge wrappers share storage without sharing PyTorch version counters,
so endpoints additionally need independent content snapshots.
"""
import copy
from pathlib import Path
import time

import torch


VERSION = "prompt8h-fit-input-guard-v1"
_ATTRIBUTE = "_dfg_v2_fit_input_guard"


def active_guard(model):
    guard = getattr(model, _ATTRIBUTE, None)
    if guard is not None and (not isinstance(guard, FitInputGuard) or guard.model is not model):
        raise ValueError("Invalid process-local fit input guard")
    return guard


def _tensor_identity(value):
    return (value.data_ptr(), value._version, tuple(value.shape), tuple(value.stride()),
            value.storage_offset(), str(value.dtype), str(value.device), value.requires_grad)


def _file_identity(path):
    item = Path(path).stat()
    return (item.st_size, item.st_mtime_ns, item.st_ino, item.st_dev)


class _ObservedSupervision:
    """Delegate without reading outer targets ahead of the frozen trainer."""
    def __init__(self, wrapped, role, guard):
        self._wrapped, self._role, self._guard = wrapped, role, guard

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    def targets(self, model, labels):
        value = self._wrapped.targets(model, labels)
        self._guard.observe_targets(self._role, value)
        return value

    def forward(self, model):
        return self._wrapped.forward(model)


class FitInputGuard:
    """Call finish after trainer.fit and before the success receipt.

    The object owns no resource watcher and never changes the tensors returned
    by supervision. Retained target tensors are small immutable references.
    """
    def __init__(self, model, binding, parts, labels):
        self.model, self.binding, self.parts, self.labels = model, binding, parts, labels
        self.snapshot = None
        self._binding = None
        self._python = None
        self._files = {}
        self._tensors = {}
        self._endpoint_contents = {}
        self._targets = []
        self._after_training = False
        self._finished = False
        self._entered = False
        self._evaluation_started_at = None
        self._evaluation_finished_at = None
        self.events = []
        self.operations = []

    def __enter__(self):
        if self._entered or active_guard(self.model) is not None:
            raise ValueError("A fit input guard cannot be reused or nested")
        self._entered = True
        setattr(self.model, _ATTRIBUTE, self)
        return self

    def __exit__(self, error_type, error, traceback):
        if getattr(self.model, _ATTRIBUTE, None) is self:
            delattr(self.model, _ATTRIBUTE)
        if error_type is None and not self._finished:
            raise ValueError("Fit input guard finished without final deep acceptance")
        return False

    def wrap_parts(self):
        return {role: _ObservedSupervision(part, role, self)
                for role, part in self.parts.items()}

    def _python_inputs(self):
        model, graph = self.model, self.model.symmetrical_global_graph
        fields = ("dfg_profile", "dfg_task", "dfg_reducer", "dfg_layer_impl",
            "node_feature", "in_size", "hidden_size", "out_size", "num_heads", "num_layers",
            "node_ids_dict", "node_ids_by_filename", "node_labels", "original_graph_node_ids",
            "ntypes_dict", "etypes_dict", "total_nodes")
        return dict(model={name: getattr(model, name) for name in fields if hasattr(model, name)},
            graph_identity=id(graph), graph_index_identity=id(graph._graph),
            nx_identity=id(model.nx_graph), nx_nodes=model.nx_graph.number_of_nodes(),
            nx_edges=model.nx_graph.number_of_edges(),
            graph_nodes={name: graph.num_nodes(name) for name in graph.ntypes},
            graph_edges={c: graph.num_edges(c) for c in graph.canonical_etypes},
            layers=[dict(node_dict=layer.node_dict, edge_dict=layer.edge_dict,
                         use_norm=layer.use_norm, dropout=layer.drop.p) for layer in model.gcs],
            labels=self.labels,
            parts={role: dict(task=part.task, files=part.files, full_ids=part.full_ids,
                              manifest=part.manifest) for role, part in self.parts.items()})

    def _input_tensors(self):
        model, graph = self.model, self.model.symmetrical_global_graph
        values = {("supervised_mask",): model.supervised_node_mask}
        for name in graph.ntypes:
            values[("inp", name)] = graph.nodes[name].data["inp"]
        for canonical in graph.canonical_etypes:
            values[("relation_id", canonical)] = graph.edges[canonical].data["id"]
            source, target = graph.edges(etype=canonical, order="eid")
            values[("edge_source", canonical)] = source
            values[("edge_target", canonical)] = target
        for role, part in self.parts.items():
            values[("supervision_mask", role)] = part.mask
            for name in ("audit_targets","audit_include"):
                if hasattr(part,name): values[(name,role)] = getattr(part,name)
        return values

    def observe_targets(self, role, value):
        if self.snapshot is None:
            raise ValueError("Target materialization preceded the starting input snapshot")
        if role not in self.parts or not isinstance(value, torch.Tensor):
            raise ValueError("Invalid observed target tensor")
        self._targets.append((role, value, _tensor_identity(value)))

    def start(self, expected_binding):
        if self.snapshot is not None:
            self.fast_check(expected_binding, "repeated_snapshot")
            return copy.deepcopy(self.snapshot)
        from . import checkpoint
        if expected_binding != self.binding:
            raise ValueError("Guard binding differs before fitting")
        started = time.monotonic()
        checkpoint.validate_binding(self.model, self.binding)
        self.snapshot = checkpoint.native.snapshot_input(self.model, self.binding)
        self._binding = copy.deepcopy(self.binding)
        self._python = copy.deepcopy(self._python_inputs())
        self._files = {name: _file_identity(self.binding[name]["path"])
                       for name in ("graph", "folds", "labels", "label_view", "feature_view", "feature_npz") if name in self.binding}
        self._tensors = {name: (value, _tensor_identity(value))
                         for name, value in self._input_tensors().items()}
        self._endpoint_contents = {name: value.detach().clone()
            for name, (value, unused) in self._tensors.items()
            if name[0] in ("edge_source", "edge_target")}
        self.events.append(dict(kind="deep", boundary="start", seconds=time.monotonic() - started,
                                input_files_rehashed=True))
        return copy.deepcopy(self.snapshot)

    def _reject(self, reason):
        """Perform the full diagnostic, then reject even a no-op tensor write."""
        from . import checkpoint
        started, diagnostic = time.monotonic(), None
        try:
            checkpoint.validate_binding(self.model, self.binding)
            current = checkpoint.native.snapshot_input(self.model, self.binding)
            if current != self.snapshot:
                diagnostic = "deep model input fingerprint changed"
        except Exception as error:
            diagnostic = repr(error)
        self.events.append(dict(kind="rejection_deep", boundary=reason,
            seconds=time.monotonic() - started, diagnostic=diagnostic,
            input_files_rehashed=True))
        raise ValueError("Frozen fit input changed: {} (deep diagnostic: {})".format(reason, diagnostic))

    def fast_check(self, binding, boundary):
        if self.snapshot is None:
            raise ValueError("Fast input check requires a starting deep snapshot")
        started = time.monotonic()
        try:
            if binding != self._binding or self.binding != self._binding:
                raise ValueError("binding fields")
            if self._python_inputs() != self._python:
                raise ValueError("schema or Python supervision fields")
            for name, before in self._files.items():
                if _file_identity(self.binding[name]["path"]) != before:
                    raise ValueError("bound file metadata: " + name)
            current = self._input_tensors()
            if set(current) != set(self._tensors):
                raise ValueError("input tensor keys")
            for name, (held, before) in self._tensors.items():
                if _tensor_identity(held) != before or _tensor_identity(current[name]) != before:
                    raise ValueError("input tensor identity/version: " + repr(name))
            for name, content in self._endpoint_contents.items():
                if not torch.equal(current[name], content):
                    raise ValueError("DGL endpoint contents: " + repr(name))
            for role, value, before in self._targets:
                if _tensor_identity(value) != before:
                    raise ValueError("target tensor identity/version: " + role)
            from . import checkpoint
            checkpoint.validate_binding(self.model, self.binding, check_files=False, deep=False)
        except Exception as error:
            self._reject(boundary + ": " + str(error))
        self.events.append(dict(kind="fast", boundary=boundary, seconds=time.monotonic() - started))

    def _deep_boundary(self, boundary):
        from . import checkpoint
        started = time.monotonic()
        self.fast_check(self.binding, boundary + "_precheck")
        # File hashes were checked at start; metadata is checked on every use.
        # Final archive verification rehashes all bound files independently.
        checkpoint.validate_binding(self.model, self.binding, check_files=False)
        current = checkpoint.native.snapshot_input(self.model, self.binding)
        if current != self.snapshot:
            raise ValueError("Frozen input changed at deep boundary: " + boundary)
        self.events.append(dict(kind="deep", boundary=boundary, seconds=time.monotonic() - started,
                                input_files_rehashed=False))

    def before_restore(self, binding):
        self.fast_check(binding, "restore_before")
        if not self._after_training:
            self._deep_boundary("after_training")
            self._after_training = True
            self._evaluation_started_at = time.monotonic()

    def finish(self):
        if self._finished or not self._after_training:
            raise ValueError("Final acceptance requires completed training and checkpoint evaluation")
        self._evaluation_finished_at = time.monotonic()
        self._deep_boundary("after_evaluation")
        self._finished = True

    def record_operation(self, operation, path, started):
        self.operations.append(dict(operation=operation, checkpoint=Path(path).name,
                                    seconds=time.monotonic() - started))

    def summary(self):
        deep = [row for row in self.events if row["kind"] == "deep"]
        saves = [row["seconds"] for row in self.operations if row["operation"] == "save"]
        restores = [row["seconds"] for row in self.operations if row["operation"] == "restore"]
        return dict(version=VERSION, complete=self._finished,
            deep_boundaries=[row["boundary"] for row in deep], deep_checks=len(deep),
            fast_checks=sum(row["kind"] == "fast" for row in self.events),
            file_hash_rounds=sum(row.get("input_files_rehashed", False) for row in self.events),
            observed_target_tensors=len(self._targets), events=self.events, operations=self.operations,
            save_calls=len(saves), save_seconds=sum(saves),
            average_save_seconds=sum(saves) / len(saves) if saves else None,
            restore_calls=len(restores), restore_seconds=sum(restores),
            evaluation_seconds=(self._evaluation_finished_at - self._evaluation_started_at
                if self._evaluation_finished_at is not None else None))
