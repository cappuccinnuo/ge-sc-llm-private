"""Graph-only, per-file attention readout over the unchanged frozen HGT path.

No graph construction, feature extraction, labels or HGT layer is changed.
The guard input adapter also represents an unenhanced HCG without registering
empty added relations. Shared parameter names and constructor RNG draws remain
identical to the corresponding mean-readout model. Only ``readout_vector`` is
new; its zero initialization uses no random numbers and is not a trained state.
"""
import torch
from torch import nn
from torch.nn import functional as F
from scripts.DFG.experiments.guard_extension import model as prior

ADAPTER_VERSION = "graph-file-softmax-readout-v1"
READOUT_PARAMETER = "readout_vector"
READOUT_INITIALIZATION_VERSION = "exact-shared-untrained-plus-zero-vector-v1"
INITIALIZATION_VERSION = READOUT_INITIALIZATION_VERSION
adapt = prior.adapt
FORWARD_RELATIONS = prior.FORWARD_RELATIONS
GRAPH_KINDS = frozenset(("HCG", "HCG_DDG_GUARD"))
move_to_device = prior.move_to_device
semantic_state = prior.semantic_state


def register_attention_parameter(model):
    """Attach only a zero vector; intentionally no RNG draws or score bias."""
    if hasattr(model, READOUT_PARAMETER):
        raise ValueError("Attention parameter already registered")
    weight = model.classify.weight
    if weight.ndim != 2 or weight.shape[1] != model.hidden_size:
        raise ValueError("Classifier/readout hidden dimension mismatch")
    model.register_parameter(READOUT_PARAMETER, nn.Parameter(
        torch.zeros(model.hidden_size, dtype=weight.dtype, device=weight.device)))


def attention_pool(hidden, vector):
    """Normalize within one file, preserving gradients even at vector == 0.

    Returned weights are a diagnostic aid, never targets or node predictions.
    No labels, filename rules, node types or source positions enter this step.
    """
    if hidden.ndim != 2 or vector.ndim != 1 or hidden.shape[1] != vector.shape[0]:
        raise ValueError("Attention input shape mismatch")
    if hidden.shape[0] == 0:
        raise ValueError("Cannot pool an empty file")
    weights = torch.softmax(torch.mv(hidden, vector), dim=0)
    pooled = torch.sum(hidden * weights.unsqueeze(1), dim=0)
    return pooled, weights


class AttentionGraphClassifier(prior.GuardGraphClassifier):
    def __init__(self, path, device="cpu", hidden_size=128, layers=2, heads=8,
                 graph_kind=None):
        super().__init__(path, device, hidden_size, layers, heads)
        relations = {canonical[1] for canonical in self.etypes_dict}
        inferred = "HCG_DDG_GUARD" if prior.RELATION in relations else "HCG"
        self.readout_graph_kind = inferred if graph_kind is None else graph_kind
        if self.readout_graph_kind not in GRAPH_KINDS:
            raise ValueError("Unknown readout graph kind")
        if self.readout_graph_kind == "HCG" and relations & prior.FORWARD_RELATIONS:
            raise ValueError("HCG baseline unexpectedly contains added relations")
        if self.readout_graph_kind == "HCG_DDG_GUARD" and prior.RELATION not in relations:
            raise ValueError("Enhanced readout graph lacks CONTROL_DEPENDENCE")
        register_attention_parameter(self)

    def forward(self, batched_g_name, save_featrues=None):
        # Same complete-graph HGT operations and global row assembly as the
        # original HGTVulGraphClassifier.forward. Only the file reduction below
        # differs; no hooks, module monkeypatch, or extra scoring parameters.
        h = {}
        hiddens = torch.zeros((self.symmetrical_global_graph.number_of_nodes(),
                               self.hidden_size), device=self.device)
        for ntype in self.symmetrical_global_graph.ntypes:
            n_id = self.ntypes_dict[ntype]
            h[ntype] = F.gelu(self.adapt_ws[n_id](
                self.symmetrical_global_graph.nodes[ntype].data["inp"]))
        for i in range(self.num_layers):
            h = self.gcs[i](self.symmetrical_global_graph, h)
        for ntype, feature in h.items():
            assert len(self.node_ids_dict[ntype]) == feature.shape[0]
            hiddens[self.node_ids_dict[ntype]] = feature
        batched_graph_embedded = []
        for g_name in batched_g_name:
            node_list = self.node_ids_by_filename[g_name]
            pooled, _ = attention_pool(hiddens[node_list], self.readout_vector)
            batched_graph_embedded.append(pooled)
        batched_graph_embedded = torch.stack(batched_graph_embedded, dim=0)
        if save_featrues:
            torch.save(batched_graph_embedded, save_featrues)
        output = self.classify(batched_graph_embedded)
        return output, batched_graph_embedded


def make_model(task, path, device="cpu", hidden_size=128, layers=2, heads=8,
               graph_kind=None):
    if task != "contract":
        raise ValueError("Attention readout is contract-only")
    model = AttentionGraphClassifier(path, device, hidden_size, layers, heads,
                                    graph_kind=graph_kind).to(device)
    validate_registration(model)
    return model


def validate_registration(model, expected_schema=None, deep=True):
    schema = prior.validate_registration(model, expected_schema, deep=deep)
    if not isinstance(model, AttentionGraphClassifier):
        raise ValueError("Expected the attention graph adapter")
    vector = dict(model.named_parameters()).get(READOUT_PARAMETER)
    if vector is None or tuple(vector.shape) != (model.hidden_size,) or not vector.requires_grad:
        raise ValueError("Readout vector not registered with the frozen shape")
    if vector.dtype != model.classify.weight.dtype or vector.device != model.classify.weight.device:
        raise ValueError("Readout/classifier dtype or device mismatch")
    return schema


def load_mean_state(model, state):
    """Strictly transfer common tensors and zero the new parameter.

    This helper checks tensor structure, not provenance. The controller MUST
    independently verify source SHA, task/fold/schema, optimizer_steps == 0 and
    saved fit_seed before passing an accepted historical initial state here.
    No missing shared tensor, unexpected relation slice, dtype conversion or
    trained-weight claim is silently accepted.
    """
    if any(p.grad is not None for p in model.parameters()):
        raise ValueError("Untrained state transfer requires no gradient history")
    expected = model.state_dict()
    shared = set(expected) - {READOUT_PARAMETER}
    if set(state) != shared:
        raise ValueError("Mean state keys differ from exact shared parameter keys")
    for key in shared:
        value = state[key]
        if not isinstance(value, torch.Tensor) or value.shape != expected[key].shape:
            raise ValueError("Shared state shape mismatch: " + key)
        if value.dtype != expected[key].dtype:
            raise ValueError("Shared state dtype mismatch: " + key)
        if not bool(torch.isfinite(value).all()):
            raise ValueError("Shared state is non-finite: " + key)
    merged = {key: state[key].detach().clone() for key in shared}
    merged[READOUT_PARAMETER] = torch.zeros_like(expected[READOUT_PARAMETER])
    model.load_state_dict(merged, strict=True)
    return model
