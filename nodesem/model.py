"""TODO docstring."""
import numpy as np
import torch
from nodesem.schema import STATIC, TOKEN_IDS
from nodesem.features import FeatureSpec
from nodesem.rows import vector_sha
from torch import nn

from dfg.model.model import validate_registration
from dfg.train.init import parameter_seed


# ----------------------------------------------------------------------
# node_sem/adapter
# NodeSem fusion, preserving the NS-P1 single-token parameter/forward path.
#
# The frozen model applies GELU. No HGT or graph computations are replaced.
# Dropout uses an explicit fit identity and local CPU RNG, never global RNG.
class NodeSemAdapter(nn.Module):
    def __init__(self, spec, ntype, shared=None, hidden_size=128):
        super().__init__()
        if not isinstance(spec, FeatureSpec):
            raise TypeError("NodeSemAdapter requires FeatureSpec")
        if spec.token_mode == "raw_linear":
            raise ValueError("S0 retains the original nn.Linear adapter")
        if not isinstance(ntype, str) or not ntype:
            raise ValueError("ntype must be a nonempty node type")
        if isinstance(hidden_size, bool) or not isinstance(hidden_size, int) or hidden_size <= 0:
            raise ValueError("hidden_size must be a positive integer")
        self.spec, self.spec_digest = spec, spec.digest()
        self.ntype, self.hidden_size = ntype, hidden_size
        self.names = tuple(m["name"] for m in spec.modalities)
        self.legacy_token = self.names == (TOKEN_IDS,) and spec.fusion == "concat"
        self.dropout_seed = None
        self.forward_count = 0
        self.last_gates = None
        if TOKEN_IDS in self.names:
            if not isinstance(shared, nn.ModuleDict) or set(shared) != {"token_bag", "token_norm"}:
                raise ValueError("shared must register token_bag and token_norm on the owning model")
            bag, norm = shared["token_bag"], shared["token_norm"]
            if (type(bag) is not nn.EmbeddingBag or bag.embedding_dim != 64 or bag.mode != "mean"
                    or bag.num_embeddings < 1 or bag.include_last_offset):
                raise ValueError("token_bag requires EmbeddingBag(V,64,mode='mean')")
            if (type(norm) is not nn.LayerNorm or norm.normalized_shape != (64,)
                    or not norm.elementwise_affine or norm.eps != 1e-5):
                raise ValueError("token_norm requires affine LayerNorm(64)")
        elif shared is not None and len(shared):
            raise ValueError("Non-token fusion must not register token modules")
        object.__setattr__(self, "_shared", shared)
        if self.legacy_token:
            # Preserve old S1 keys, constructor RNG and exact p=0 arithmetic.
            self.token_projection = nn.Linear(64, hidden_size)
        else:
            self.norm = nn.ModuleDict()
            self.proj = nn.ModuleDict()
            for m in spec.modalities:
                name = m["name"]
                if name == STATIC and m["normalize"]:
                    raise ValueError("STATIC must not use LayerNorm")
                if name not in (TOKEN_IDS, STATIC) and m["normalize"]:
                    self.norm[name] = nn.LayerNorm(m["dim"])
                self.proj[name] = nn.Linear(64 if name == TOKEN_IDS else m["dim"], hidden_size, bias=False)
            self.bias = nn.Parameter(torch.zeros(hidden_size))
            if spec.fusion == "gated":
                self.gate = nn.Linear(len(self.names) * hidden_size, len(self.names))

    @property
    def token_bag(self):
        return self._shared["token_bag"]

    @property
    def token_norm(self):
        return self._shared["token_norm"]

    def reset_dropout(self, fit_seed, task_id, fold, profile):
        if (isinstance(fit_seed, bool) or not isinstance(fit_seed, int)
                or not isinstance(task_id, str) or not task_id
                or isinstance(fold, bool) or not isinstance(fold, int) or fold < 0
                or profile not in ("G0", "G3R")):
            raise ValueError("Invalid dropout fit identity")
        self.dropout_seed = parameter_seed(fit_seed, "modality_dropout",
            [task_id, fold, profile, self.spec_digest, self.ntype])
        self.forward_count = 0
        return self.dropout_seed

    def _input_presence(self, inp):
        if (not isinstance(inp, torch.Tensor) or inp.ndim != 2
                or inp.shape[1] != self.spec.carrier_dim() or inp.dtype != torch.float32
                or not bool(torch.isfinite(inp).all())):
            raise ValueError("Expected finite float32 carrier with the bound width")
        presence = inp[:, :len(self.names)]
        if not bool(((presence == 0) | (presence == 1)).all()):
            raise ValueError("Modality presence must be binary")
        return presence

    def _drop_presence(self, presence):
        if not self.training or self.spec.modality_dropout == 0:
            return presence
        if self.dropout_seed is None:
            raise RuntimeError("Reset modality dropout from the bound fit identity before training")
        generator = torch.Generator(device="cpu")
        generator.manual_seed(self.dropout_seed + self.forward_count)
        self.forward_count += 1
        keep = torch.rand(presence.shape, generator=generator, device="cpu") >= self.spec.modality_dropout
        return presence * keep.to(device=presence.device, dtype=presence.dtype)

    def _normalized_tokens(self, inp):
        pooled = self.pooled_tokens(inp)
        active = inp[:, self.spec.layout()[TOKEN_IDS]["presence"]] == 1
        normalized = torch.zeros_like(pooled)
        if bool(active.any()):
            normalized[active] = self.token_norm(pooled[active])
        return normalized

    def pooled_tokens(self, inp):
        """Pool each nonzero prefix without materializing N x 512 x 64."""
        if (not isinstance(inp, torch.Tensor) or inp.ndim != 2
                or inp.shape[1] != self.spec.carrier_dim()
                or inp.dtype != torch.float32):
            raise ValueError("input must be a float32 carrier matrix of the bound width")
        if not bool(torch.isfinite(inp).all()):
            raise ValueError("carrier contains nonfinite values")
        part = self.spec.layout()[TOKEN_IDS]
        ids = inp[:, part["start"]:part["stop"]]
        if (not bool((ids >= 0).all())
                or not bool((ids == ids.floor()).all())
                or not bool((ids < self.token_bag.num_embeddings).all())):
            raise ValueError("token IDs must be exact nonnegative integers within vocabulary")
        nonzero = ids != 0
        if bool((nonzero[:, 1:] & ~nonzero[:, :-1]).any()):
            raise ValueError("token ID padding must be a continuous right suffix")
        lengths = nonzero.sum(dim=1)
        presence = inp[:, part["presence"]]
        if (not bool(((presence == 0) | (presence == 1)).all())
                or not torch.equal(presence, (lengths > 0).to(inp.dtype))):
            raise ValueError("token presence must agree with the nonempty token prefix")
        if inp.shape[0] == 0:
            return inp.new_zeros((0, 64))
        flat_ids = ids[nonzero].to(dtype=torch.long)
        offsets = torch.cat((lengths.new_zeros(1), lengths.cumsum(0)[:-1]))
        # EmbeddingBag returns zero vectors for empty bags, including an
        # entirely empty flat_ids tensor; padding ID zero never reaches it.
        return self.token_bag(flat_ids, offsets)

    def forward(self, inp):
        presence = self._drop_presence(self._input_presence(inp))
        if self.legacy_token:
            normalized = self._normalized_tokens(inp)
            if not self.training or self.spec.modality_dropout == 0:
                return self.token_projection(normalized)
            return (torch.nn.functional.linear(normalized, self.token_projection.weight)
                    * presence[:, :1] + self.token_projection.bias)
        projected = []
        for index, modality in enumerate(self.spec.modalities):
            name = modality["name"]
            part = self.spec.layout()[name]
            value = self._normalized_tokens(inp) if name == TOKEN_IDS else inp[:, part["start"]:part["stop"]]
            if name in self.norm:
                value = self.norm[name](value)
            projected.append(self.proj[name](value) * presence[:, index:index+1])
        if self.spec.fusion == "concat":
            result = projected[0]
            for value in projected[1:]:
                result = result + value
            return result + self.bias
        logits = self.gate(torch.cat(projected, dim=1))
        active = presence != 0
        any_active = active.any(dim=1, keepdim=True)
        masked = logits.masked_fill(~active, float("-inf"))
        # Never feed an all -inf row to softmax (forward AND backward).
        safe = torch.where(any_active, masked, torch.zeros_like(masked))
        gates = torch.softmax(safe, dim=1) * active.to(logits.dtype)
        self.last_gates = gates.detach().cpu().clone()
        return (torch.stack(projected, dim=1) * gates.unsqueeze(-1)).sum(dim=1) + self.bias

def reset_modality_dropout(model, fit_seed, task_id, fold, profile):
    """Call immediately before a fresh fit; evaluation never advances the counter."""
    return {a.ntype: a.reset_dropout(fit_seed, task_id, fold, profile)
            for a in model.adapt_ws if isinstance(a, NodeSemAdapter)}


# ----------------------------------------------------------------------
# node_sem/model (picked: _validate_token_rows, validate)
def _validate_token_rows(graph, vocabulary, spec):
    for _, attrs in graph.nodes(data=True):
        part = spec.layout()[TOKEN_IDS]
        tokens = attrs["token"][part["start"]:part["stop"]]
        if (not np.isfinite(tokens).all() or np.any(tokens < 0)
                or np.any(tokens != np.floor(tokens)) or np.any(tokens >= vocabulary)):
            raise ValueError("Token IDs are not exact vocabulary indices")
        nonzero = tokens != 0
        if np.any(nonzero[1:] & ~nonzero[:-1]):
            raise ValueError("Token padding must be a continuous right suffix")

def validate(model, spec):
    if not isinstance(spec, FeatureSpec):
        spec = FeatureSpec.from_json(spec)
    if model.nodesem_spec_sha256 != spec.digest() or model.nodesem_spec != spec.to_json():
        raise ValueError("NodeSem model/spec binding differs")
    if len(model.gcs) != model.num_layers or (spec.layers is not None and model.num_layers != spec.layers):
        raise ValueError("NodeSem HGT layer count differs")
    if model.in_size != spec.carrier_dim():
        raise ValueError("NodeSem carrier width differs")
    if len(model.adapt_ws) != len(model.ntypes_dict):
        raise ValueError("NodeSem adapter count differs")
    record = model.nodesem_carrier_record
    if (record["spec_sha256"] != spec.digest()
            or record["feature_shape"] != [model.total_nodes, spec.carrier_dim()]
            or len(record["rows"]) != model.total_nodes):
        raise ValueError("NodeSem carrier record differs")
    for (node, attrs), row in zip(model.nx_graph.nodes(data=True), record["rows"]):
        if vector_sha(attrs["token"]) != row["vector_sha256"]:
            raise ValueError("NodeSem carrier vector digest differs")
    if spec.token_mode == "raw_linear":
        if hasattr(model, "nodesem_shared"):
            raise ValueError("S0 must not register new shared parameters")
        for adapter in model.adapt_ws:
            if (type(adapter) is not nn.Linear or adapter.in_features != 512
                    or adapter.out_features != model.hidden_size):
                raise ValueError("S0 must preserve the original Linear adapters")
    else:
        shared = getattr(model, "nodesem_shared", None)
        if spec.token_mode == "embed_pool":
            if not isinstance(shared, nn.ModuleDict) or set(shared) != {"token_bag", "token_norm"}:
                raise ValueError("Missing unique model-level token embedding")
            bag, token_norm = shared["token_bag"], shared["token_norm"]
            if (type(bag) is not nn.EmbeddingBag or bag.embedding_dim != 64
                    or bag.num_embeddings != model.nodesem_vocabulary or bag.mode != "mean"
                    or bag.include_last_offset or bag.max_norm is not None
                    or bag.scale_grad_by_freq or bag.sparse):
                raise ValueError("Shared token embedding configuration differs")
            if (type(token_norm) is not nn.LayerNorm or token_norm.normalized_shape != (64,)
                    or not token_norm.elementwise_affine or token_norm.eps != 1e-5):
                raise ValueError("Shared token normalization configuration differs")
            expected = {"nodesem_shared.token_bag.weight", "nodesem_shared.token_norm.weight",
                        "nodesem_shared.token_norm.bias"}
            for values in (model.state_dict(), dict(model.named_parameters())):
                keys = [key for key in values if "token_bag" in key or "token_norm" in key]
                if len(keys) != 3 or set(keys) != expected:
                    raise ValueError("Shared embedding/normalization registered more than once")
        elif shared is not None:
            raise ValueError("Non-token model must not register token shared modules")
        for ntype, index in model.ntypes_dict.items():
            adapter = model.adapt_ws[index]
            if (type(adapter) is not NodeSemAdapter or adapter.spec_digest != spec.digest()
                    or adapter.spec.digest() != spec.digest() or adapter.ntype != ntype
                    or adapter.hidden_size != model.hidden_size
                    or adapter.names != tuple(m["name"] for m in spec.modalities)):
                raise ValueError("NodeSem adapter semantic registration differs")
            if spec.token_mode == "embed_pool" and (adapter.token_bag is not bag or adapter.token_norm is not token_norm):
                raise ValueError("NodeSem shared token reference differs")
            legacy = adapter.names == (TOKEN_IDS,) and spec.fusion == "concat"
            if adapter.legacy_token != legacy:
                raise ValueError("NodeSem token compatibility path differs")
            if legacy:
                projection = adapter.token_projection
                if (type(projection) is not nn.Linear or projection.in_features != 64
                        or projection.out_features != model.hidden_size or projection.bias is None):
                    raise ValueError("NodeSem token projection differs")
                continue
            expected_norm = {m["name"] for m in spec.modalities
                             if m["name"] not in (TOKEN_IDS, STATIC) and m["normalize"]}
            if set(adapter.norm) != expected_norm or set(adapter.proj) != set(adapter.names):
                raise ValueError("NodeSem projection/normalization layout differs")
            if adapter.bias.shape != (model.hidden_size,):
                raise ValueError("NodeSem fusion bias differs")
            for m in spec.modalities:
                projection = adapter.proj[m["name"]]
                if (type(projection) is not nn.Linear or projection.bias is not None
                        or projection.in_features != (64 if m["name"] == TOKEN_IDS else m["dim"])
                        or projection.out_features != model.hidden_size):
                    raise ValueError("NodeSem modality projection differs")
                if m["name"] in expected_norm:
                    norm = adapter.norm[m["name"]]
                    if (type(norm) is not nn.LayerNorm or norm.normalized_shape != (m["dim"],)
                            or not norm.elementwise_affine or norm.eps != 1e-5):
                        raise ValueError("NodeSem modality normalization differs")
            if spec.fusion == "gated":
                gate = adapter.gate
                if (type(gate) is not nn.Linear or gate.in_features != len(adapter.names)*model.hidden_size
                        or gate.out_features != len(adapter.names) or gate.bias is None):
                    raise ValueError("NodeSem gate differs")
            elif hasattr(adapter, "gate"):
                raise ValueError("Concat must not register a gate")
    if model.num_layers == 0 and model.dfg_profile != "G0":
        raise ValueError("Zero HGT layers require G0")
    return validate_registration(model)


def token_vocabulary():
    """Vocabulary size of the HCG token IDs (added tokens included); pad id must be 0."""
    from hcg.features.tokens import load_tokenizer
    tokenizer = load_tokenizer()
    if tokenizer.pad_token_id != 0:
        raise ValueError("HCG tokenizer padding must be zero")
    return len(tokenizer)


def make_nodesem_model(task, carried, record, profile, spec, config, device="cpu", vocabulary=None):
    """HGT over a carried graph (``features.carry``) with NodeSem input adapters."""
    from dfg.model.model import make_model
    if not isinstance(spec, FeatureSpec):
        spec = FeatureSpec.from_json(spec)
    layers = config["layers"] if spec.layers is None else spec.layers
    if layers == 0 and profile != "G0":
        raise ValueError("Zero-layer ablation is supported only on G0")
    model = make_model(task, carried, profile, device, node_feature="inside_token",
                       hidden_size=config["hidden_size"], layers=layers, heads=config["heads"],
                       reducer=config.get("reducer", "mean"), layer_impl=config["layer_impl"])
    if spec.token_mode != "raw_linear":
        shared = None
        if spec.token_mode == "embed_pool":
            vocabulary = token_vocabulary() if vocabulary is None else vocabulary
            _validate_token_rows(carried, vocabulary, spec)
            bag = nn.EmbeddingBag(vocabulary, 64, mode="mean")
            with torch.no_grad():
                bag.weight[0].zero_()
            model.nodesem_shared = nn.ModuleDict({"token_bag": bag, "token_norm": nn.LayerNorm(64)})
            shared = model.nodesem_shared
            model.nodesem_vocabulary = vocabulary
        model.adapt_ws = nn.ModuleList([
            NodeSemAdapter(spec, node_type, shared=shared, hidden_size=config["hidden_size"])
            for node_type, index in sorted(model.ntypes_dict.items(), key=lambda item: item[1])])
        model.to(device)
    model.nodesem_spec = spec.to_json()
    model.nodesem_spec_sha256 = spec.digest()
    model.nodesem_carrier_record = record
    validate(model, spec)
    return model
