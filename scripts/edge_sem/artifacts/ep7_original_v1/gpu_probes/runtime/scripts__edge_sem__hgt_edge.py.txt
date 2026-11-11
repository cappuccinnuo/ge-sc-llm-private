"""EP6 edge-aware HGT; frozen projection/reduction/residual behavior.

Forward copied from scripts/DFG/dfg_v2/hgt_layer.py:115-185.
SHA256 09eb3f7d6cce2e22214cb0cb127d47c69fab43e382032f8439896938ef46cf8b
Inherited constructor: sco_models/model_hgt.py::HGTLayer.
SHA256 4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947
Only edge attention bias and edge message addition differ.
"""
import hashlib
from pathlib import Path
import torch
from torch import nn
import torch.nn.functional as F
import dgl.function as fn
from dgl.nn.functional import edge_softmax
from . import FAMILIES, RELATION_FAMILY

FROZEN_SOURCES = {
    "scripts/DFG/dfg_v2/hgt_layer.py": "09eb3f7d6cce2e22214cb0cb127d47c69fab43e382032f8439896938ef46cf8b",
    "sco_models/model_hgt.py": "4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947",
}


def verify_frozen_sources(root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[2]
    for name,sha in FROZEN_SOURCES.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:
            raise ValueError("Frozen HGT source SHA mismatch: "+name)


verify_frozen_sources()
from scripts.DFG.dfg_v2.hgt_layer import HGTLayerSharedProjection


class EdgeAttrEncoder(nn.Module):
    """One model-level MLP; output dropout is shared by every HGT layer."""
    def __init__(self, in_dim, hidden=32, out_dim=16, dropout=0.1):
        super().__init__()
        if in_dim<=0 or hidden<=0 or out_dim!=16:raise ValueError("Invalid edge encoder dimensions")
        self.in_dim=in_dim
        self.w1=nn.Linear(in_dim,hidden)
        self.w2=nn.Linear(hidden,out_dim)
        self.drop=nn.Dropout(dropout)

    def forward(self, a_uint8):
        if a_uint8.dtype!=torch.uint8 or a_uint8.ndim!=2 or a_uint8.shape[1]!=self.in_dim:
            raise ValueError("Expected uint8 edge feature matrix")
        return self.drop(self.w2(F.gelu(self.w1(a_uint8.float()))))


class EdgeAwareHGTLayer(HGTLayerSharedProjection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.u=nn.Parameter(torch.zeros(len(self.edge_dict),16,self.n_heads))
        self.U=nn.ParameterDict({family:nn.Parameter(torch.zeros(16,self.out_dim)) for family in sorted(FAMILIES)})
        if any(c[1] not in RELATION_FAMILY for c in self.edge_dict):
            raise ValueError("Unknown edge relation family")

    def forward(self, G, h, psi=None):
        if psi is None:
            return super().forward(G, h)
        if set(psi)!=set(G.canonical_etypes):
            raise ValueError("Edge embedding relation schema differs")
        with G.local_scope():
            node_dict, edge_dict = self.node_dict, self.edge_dict
            # These type-specific projections have identical inputs for every
            # canonical relation. Keep one autograd result per type and reuse it;
            # relation-specific transforms and message order remain unchanged.
            projected_k, projected_v, projected_q = {}, {}, {}
            for ntype in G.ntypes:
                n_id = node_dict[ntype]
                projected_k[ntype] = self.k_linears[n_id](h[ntype]).view(-1, self.n_heads, self.d_k)
                projected_v[ntype] = self.v_linears[n_id](h[ntype]).view(-1, self.n_heads, self.d_k)
                projected_q[ntype] = self.q_linears[n_id](h[ntype]).view(-1, self.n_heads, self.d_k)
            for srctype, etype, dsttype in G.canonical_etypes:
                sub_graph = G[srctype, etype, dsttype]
                canonical_etype = (srctype, etype, dsttype)
                k = projected_k[srctype]
                v = projected_v[srctype]
                q = projected_q[dsttype]

                e_id = self.edge_dict[canonical_etype]

                relation_att = self.relation_att[e_id]
                relation_pri = self.relation_pri[e_id]
                relation_msg = self.relation_msg[e_id]

                k = torch.einsum("bij,ijk->bik", k, relation_att)
                v = torch.einsum("bij,ijk->bik", v, relation_msg)

                sub_graph.srcdata['k'] = k
                sub_graph.dstdata['q'] = q
                sub_graph.srcdata['v_%d' % e_id] = v

                sub_graph.apply_edges(fn.v_dot_u('q', 'k', 't'))
                attn_score = sub_graph.edata.pop('t').sum(-1) * relation_pri / self.sqrt_dk
                if psi[canonical_etype].shape != (sub_graph.num_edges(),16):
                    raise ValueError("Edge embedding rows differ")
                attn_score = attn_score + psi[canonical_etype] @ self.u[e_id]
                attn_score = edge_softmax(sub_graph, attn_score, norm_by='dst')

                sub_graph.edata['t'] = attn_score.unsqueeze(-1)
                sub_graph.edata['edge_value'] = (psi[canonical_etype] @ self.U[RELATION_FAMILY[etype]]).view(-1,self.n_heads,self.d_k)
                if sub_graph.num_edges():
                    sub_graph.apply_edges(lambda e: {'m': e.data['t'] * (e.src['v_%d' % e_id] + e.data['edge_value'])})
                else:
                    sub_graph.edata['m'] = sub_graph.edata['edge_value']

            active_edge_dict = {
                etype: edge_dict[etype]
                for etype in G.canonical_etypes
                if etype in edge_dict
            }
            if active_edge_dict:
                G.multi_update_all({etype : (fn.copy_e('m', 'm'), fn.sum('m', 't')) \
                                    for etype, e_id in active_edge_dict.items()}, cross_reducer = 'mean')

            new_h = {}
            for ntype in G.ntypes:
                '''
                    Step 3: Target-specific Aggregation
                    x = norm( W[node_type] * gelu( Agg(x) ) + x )
                '''
                n_id = node_dict[ntype]
                alpha = torch.sigmoid(self.skip[n_id])
                if 't' in G.nodes[ntype].data:
                    t = G.nodes[ntype].data['t'].view(-1, self.out_dim)
                else:
                    t = torch.zeros(
                        G.num_nodes(ntype),
                        self.out_dim,
                        device=h[ntype].device,
                        dtype=h[ntype].dtype,
                    )
                trans_out = self.drop(self.a_linears[n_id](t))
                trans_out = trans_out * alpha + h[ntype] * (1-alpha)
                if self.use_norm:
                    new_h[ntype] = self.norms[n_id](trans_out)
                else:
                    new_h[ntype] = trans_out
            return new_h
