"""S1 shared token EmbeddingBag adapter; the frozen forward applies GELU.

Only the single TOKEN_IDS modality is implemented in NS-P1. Multimodal
concat/gated fusion and modality dropout are reserved for NS-P4. The shared
EmbeddingBag is registered once on the owning model, never on an adapter.
"""
import torch
from torch import nn

from . import TOKEN_IDS
from .feature_spec import FeatureSpec


class NodeSemAdapter(nn.Module):
    def __init__(self, spec, ntype, shared, hidden_size=128):
        super().__init__()
        if not isinstance(spec, FeatureSpec):
            raise TypeError("NodeSemAdapter requires FeatureSpec")
        if spec.token_mode == "raw_linear":
            raise ValueError("S0 retains the original nn.Linear adapter")
        if (spec.token_mode != "embed_pool"
                or [item["name"] for item in spec.modalities] != [TOKEN_IDS]
                or spec.fusion != "concat" or spec.modality_dropout != 0):
            raise NotImplementedError(
                "NS-P1 implements only single-token embed_pool; "
                "multimodal fusion/gated/dropout are reserved for NS-P4")
        if not isinstance(ntype, str) or not ntype:
            raise ValueError("ntype must be a nonempty node type")
        if (isinstance(hidden_size, bool) or not isinstance(hidden_size, int)
                or hidden_size <= 0):
            raise ValueError("hidden_size must be a positive integer")
        if not isinstance(shared, nn.ModuleDict) or "token_bag" not in shared:
            raise ValueError("shared must register token_bag on the owning model")
        bag = shared["token_bag"]
        if (type(bag) is not nn.EmbeddingBag or bag.embedding_dim != 64
                or bag.mode != "mean" or bag.num_embeddings < 1
                or bag.include_last_offset):
            raise ValueError("token_bag requires EmbeddingBag(V,64,mode='mean')")
        # Bypass nn.Module.__setattr__: the owning model alone registers it.
        object.__setattr__(self, "_shared", shared)
        self.spec = spec
        self.spec_digest = spec.digest()
        self.ntype = ntype
        self.hidden_size = hidden_size
        self.token_projection = nn.Linear(64, hidden_size)

    @property
    def token_bag(self):
        return self._shared["token_bag"]

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
        # A missing token modality has a zero pooled vector. Its output is the
        # type-specific bias; GELU is deliberately left to the frozen HGT.
        return self.token_projection(self.pooled_tokens(inp))
