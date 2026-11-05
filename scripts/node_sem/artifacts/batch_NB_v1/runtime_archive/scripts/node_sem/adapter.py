"""NodeSem fusion, preserving the NS-P1 single-token parameter/forward path.

The frozen model applies GELU. No HGT or graph computations are replaced.
Dropout uses an explicit fit identity and local CPU RNG, never global RNG.
"""
import torch
from torch import nn
from scripts.DFG.dfg_v2.experiment.init import parameter_seed
from . import TOKEN_IDS, STATIC
from .feature_spec import FeatureSpec


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
