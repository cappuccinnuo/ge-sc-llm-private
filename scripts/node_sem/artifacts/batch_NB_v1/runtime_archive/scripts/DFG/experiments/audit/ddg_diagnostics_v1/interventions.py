"""Read-only, instance-local HGT diagnostics. No replacement HGT forward.

Normal mode calls the original layer and multi_update_all unchanged. Zero mode
replaces only the DATA_DEF_USE *message* function, after native attention has
already been computed; sum and cross-relation mean stay native. Hooks never
return replacement outputs. All hooks and instance attributes restore in finally.
"""
import json
import types
from collections import Counter

import numpy as np
import torch

DDG = "DATA_DEF_USE"
_ABSENT = object()


def _restore_attr(obj, name, previous):
    if previous is _ABSENT:
        obj.__dict__.pop(name, None)
    else:
        setattr(obj, name, previous)


def _zero_message(value_key):
    def message(edges):
        actual_message = edges.src[value_key] * edges.data["t"]
        return {"m": torch.zeros_like(actual_message)}
    return message


def _summary(values, near_zero):
    values = np.asarray(values, dtype=np.float64)
    if not len(values):
        return dict(count=0, mean=None, median=None, p95=None, max=None,
                    zero_count=0, near_zero_count=0, zero_fraction=None,
                    near_zero_fraction=None)
    if not np.isfinite(values).all():
        raise ValueError("Non-finite diagnostic norm")
    zero = int(np.count_nonzero(values == 0))
    near = int(np.count_nonzero(np.abs(values) <= near_zero))
    return dict(count=int(len(values)), mean=float(values.mean()),
                median=float(np.median(values)), p95=float(np.percentile(values, 95)),
                max=float(values.max()), zero_count=zero, near_zero_count=near,
                zero_fraction=zero / len(values), near_zero_fraction=near / len(values))


class DiagnosticContext:
    """Temporarily observe/intervene on native HGTLayer instances.

    node_files_by_type maps each type to files in exact DGL type-row order.
    rows hold scalar summaries only. Optional representations are CPU pre/post
    LayerNorm tensors, for immediate paired-difference calculation by the caller.
    This opt-in capture is deliberately disabled by default.
    """
    def __init__(self, model, mode="normal", record=False,
                 node_files_by_type=None, near_zero=1e-12,
                 capture_representations=False):
        if mode not in ("normal", "zero"):
            raise ValueError("mode must be normal or zero")
        self.model = model
        self.mode = mode
        self.record = bool(record)
        self.node_files_by_type = node_files_by_type or {}
        self.near_zero = float(near_zero)
        self.capture_representations = bool(capture_representations)
        self.rows = []
        self.representations = {}
        self._previous = []
        self._entered = False
        self._groups = {}

    def __enter__(self):
        if self._entered or any(getattr(g, "_ddg_diagnostic_owner", None) is not None
                                for g in self.model.gcs):
            raise RuntimeError("Nested diagnostic context is not supported")
        if self.model.training or any(layer.training for layer in self.model.gcs):
            raise ValueError("Diagnostics require eval()")
        self._entered = True
        try:
            for index, layer in enumerate(self.model.gcs):
                original = layer.forward
                old = layer.__dict__.get("forward", _ABSENT)
                owner = layer.__dict__.get("_ddg_diagnostic_owner", _ABSENT)
                self._previous.append((layer, old, owner))
                layer._ddg_diagnostic_owner = self

                def wrapped(this, graph, hidden, _index=index, _original=original):
                    return self._forward(_index, this, _original, graph, hidden)
                layer.forward = types.MethodType(wrapped, layer)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc, tb):
        for layer, previous, owner in reversed(self._previous):
            _restore_attr(layer, "forward", previous)
            _restore_attr(layer, "_ddg_diagnostic_owner", owner)
        self._previous = []
        self._entered = False
        return False

    def _file_groups(self, ntype, size):
        key = (ntype, size)
        if key not in self._groups:
            groups = [("__all__", np.arange(size))]
            files = self.node_files_by_type.get(ntype)
            if files is not None:
                if len(files) != size:
                    raise ValueError("node_files_by_type row count mismatch: " + ntype)
                indices = {}
                for row, file in enumerate(files):
                    indices.setdefault(str(file), []).append(row)
                groups.extend((file, np.asarray(rows)) for file, rows in sorted(indices.items()))
            self._groups[key] = groups
        return self._groups[key]

    def _scalar_rows(self, index, ntype, branch, values, canonical=None,
                     valid=None, **extra):
        array = values.detach().to("cpu", dtype=torch.float64).numpy()
        valid_array = None if valid is None else valid.detach().cpu().numpy()
        for filename, indices in self._file_groups(ntype, len(array)):
            chosen = array[indices]
            excluded = 0
            if valid_array is not None:
                mask = valid_array[indices]
                excluded = int(len(mask) - np.count_nonzero(mask))
                chosen = chosen[mask]
            row = dict(layer=index, node_type=ntype, file=filename, branch=branch,
                       canonical="" if canonical is None else json.dumps(list(canonical)),
                       population_count=len(indices),
                       denominator_near_zero_count=excluded, near_zero_threshold=self.near_zero)
            row.update(extra)
            row.update(_summary(chosen, self.near_zero))
            self.rows.append(row)

    def _norm(self, index, ntype, branch, tensor, canonical=None, **extra):
        norm = torch.norm(tensor.detach().reshape(tensor.shape[0], -1), p=2, dim=1)
        self._scalar_rows(index, ntype, branch, norm, canonical=canonical, **extra)
        return norm

    def _representation(self, index, ntype, stage, value):
        if self.capture_representations:
            self.representations[(index, ntype, stage)] = value.detach().cpu().clone()

    def _forward(self, index, layer, original_forward, graph, hidden):
        # Native local_scope handles all k/q/v/t data. This wrapper adds no data.
        previous_multi = graph.__dict__.get("multi_update_all", _ABSENT)
        # DGL 0.6.1 local_scope restores frames after yield without a finally.
        # Protect the original frame references even if the native forward or
        # a diagnostic hook raises. No input tensor is modified in place.
        previous_node_frames = graph._node_frames
        previous_edge_frames = graph._edge_frames
        native_multi = graph.multi_update_all
        hooks = []
        current = {"ntype": None}
        sums = {}
        relation_counts = Counter()

        def observe_node_branches(ntype, dropped):
            n_id = layer.node_dict[ntype]
            alpha = torch.sigmoid(layer.skip[n_id])
            message = dropped * alpha
            residual = hidden[ntype] * (1 - alpha)
            pre = message + residual
            a = float(alpha.detach().cpu())
            if self.record:
                self._norm(index, ntype, "dropout_output", dropped, alpha=a)
                m = self._norm(index, ntype, "message_branch", message, alpha=a)
                r = self._norm(index, ntype, "residual_branch", residual, alpha=a)
                valid = r > self.near_zero
                ratio = torch.zeros_like(r)
                ratio[valid] = m[valid] / r[valid]
                self._scalar_rows(index, ntype, "message_to_residual_ratio", ratio,
                                  valid=valid, alpha=a)
                self._norm(index, ntype, "pre_layernorm", pre, alpha=a)
            self._representation(index, ntype, "pre_layernorm", pre)
            if not layer.use_norm:
                if self.record:
                    self._norm(index, ntype, "post_layernorm", pre, alpha=a,
                               layernorm_enabled=False)
                self._representation(index, ntype, "post_layernorm", pre)

        def drop_hook(module, inputs, output):
            if current["ntype"] is None:
                raise RuntimeError("Unexpected native HGT dropout order")
            observe_node_branches(current["ntype"], output)

        if self.record or self.capture_representations:
            for ntype in graph.ntypes:
                n_id = layer.node_dict[ntype]
                def linear_hook(module, inputs, output, _ntype=ntype):
                    current["ntype"] = _ntype
                    if self.record:
                        self._norm(index, _ntype, "a_linear_output", output)
                hooks.append(layer.a_linears[n_id].register_forward_hook(linear_hook))
                if layer.use_norm:
                    def norm_hook(module, inputs, output, _ntype=ntype):
                        if self.record:
                            self._norm(index, _ntype, "post_layernorm", output,
                                       layernorm_enabled=True)
                        self._representation(index, _ntype, "post_layernorm", output)
                    hooks.append(layer.norms[n_id].register_forward_hook(norm_hook))
            hooks.append(layer.drop.register_forward_hook(drop_hook))

        def intercepted(this, etype_dict, cross_reducer, apply_node_func=None):
            if cross_reducer != "mean" or apply_node_func is not None:
                raise RuntimeError("Unexpected native HGT aggregation signature")
            effective = dict(etype_dict)
            if self.mode == "zero":
                for canonical, funcs in effective.items():
                    if canonical[1] == DDG:
                        e_id = layer.edge_dict[canonical]
                        effective[canonical] = (_zero_message("v_%d" % e_id),) + tuple(funcs[1:])
            if self.record:
                # These standalone native relation reductions do NOT touch the
                # parent node frames; local_scope always restores even on error.
                for canonical, funcs in effective.items():
                    sub = graph[canonical]
                    with sub.local_scope():
                        sub.update_all(*funcs)
                        agg = sub.dstdata["t"].detach().clone()
                    ntype = canonical[2]
                    self._norm(index, ntype, "canonical_relation_aggregate", agg, canonical)
                    if ntype not in sums:
                        sums[ntype] = [torch.zeros_like(agg), torch.zeros_like(agg)]
                    which = 1 if canonical[1] == DDG else 0
                    sums[ntype][which].add_(agg)
                    relation_counts[ntype] += 1
            result = native_multi(effective, cross_reducer, apply_node_func)
            if self.record:
                for ntype in graph.ntypes:
                    if ntype not in sums:
                        continue
                    base, ddg = sums[ntype]
                    divisor = relation_counts[ntype]
                    extra = dict(cross_mean_relation_count=divisor)
                    b = self._norm(index, ntype, "base_sum", base, **extra)
                    d = self._norm(index, ntype, "ddg_sum", ddg, **extra)
                    self._norm(index, ntype, "base_mean_contribution", base / divisor, **extra)
                    self._norm(index, ntype, "ddg_mean_contribution", ddg / divisor, **extra)
                    self._norm(index, ntype, "total_cross_mean",
                               graph.nodes[ntype].data["t"], **extra)
                    valid = b > self.near_zero
                    ratio = torch.zeros_like(b)
                    ratio[valid] = d[valid] / b[valid]
                    self._scalar_rows(index, ntype, "ddg_to_base_ratio", ratio,
                                      valid=valid, **extra)
            return result

        graph.multi_update_all = types.MethodType(intercepted, graph)
        try:
            return original_forward(graph, hidden)
        finally:
            graph._node_frames = previous_node_frames
            graph._edge_frames = previous_edge_frames
            _restore_attr(graph, "multi_update_all", previous_multi)
            for hook in reversed(hooks):
                hook.remove()
