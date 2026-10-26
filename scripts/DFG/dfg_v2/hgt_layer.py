"""Optional execution adapters for the frozen HGT layer.

Copied forward source: sco_models/model_hgt.py::HGTLayer.forward
Source file SHA256: 4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947
Constructors and parameter allocation are inherited unchanged. NonEmptyMean
changes only the cross-relation reduction. SharedProjection classes reuse
one k/v/q result per node type while preserving their respective original
reducers, relation transforms, attention, residuals, dropout and normalization.
The frozen original HGT implementation and the default layer are unchanged.
"""

import torch
import dgl.function as fn
from dgl.nn.functional import edge_softmax

from sco_models.model_hgt import HGTLayer


FROZEN_HGT_SHA256 = "4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947"


class HGTLayerNonEmptyMean(HGTLayer):
    """Use a zero message when a node has no incoming relation support."""

    def forward(self, G, h ):
        with G.local_scope():
            node_dict, edge_dict = self.node_dict, self.edge_dict
            for srctype, etype, dsttype in G.canonical_etypes:
                sub_graph = G[srctype, etype, dsttype]
                canonical_etype = (srctype, etype, dsttype)
                k_linear = self.k_linears[node_dict[srctype]]
                v_linear = self.v_linears[node_dict[srctype]]
                q_linear = self.q_linears[node_dict[dsttype]]

                k = k_linear(h[srctype]).view(-1, self.n_heads, self.d_k)
                v = v_linear(h[srctype]).view(-1, self.n_heads, self.d_k)
                q = q_linear(h[dsttype]).view(-1, self.n_heads, self.d_k)

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
                attn_score = edge_softmax(sub_graph, attn_score, norm_by='dst')

                sub_graph.edata['t'] = attn_score.unsqueeze(-1)

            active_edge_dict = {
                etype: edge_dict[etype]
                for etype in G.canonical_etypes
                if etype in edge_dict
            }
            if active_edge_dict:
                G.multi_update_all({etype : (fn.u_mul_e('v_%d' % e_id, 't', 'm'), fn.sum('m', 't')) \
                                    for etype, e_id in active_edge_dict.items()}, cross_reducer = 'stack')

                # Diagnostic-only change: average only relations that actually
                # deliver a message to each destination node. DGL 0.6.1 stacks
                # relations on dimension 1 in ascending graph edge-type ID.
                for ntype in G.ntypes:
                    incoming = sorted(
                        (etype for etype in active_edge_dict if etype[2] == ntype),
                        key=G.get_etype_id,
                    )
                    if not incoming:
                        continue
                    stacked = G.nodes[ntype].data['t']
                    active = torch.stack(
                        [G.in_degrees(etype=etype) > 0 for etype in incoming],
                        dim=1,
                    ).to(device=stacked.device, dtype=stacked.dtype)
                    weights = active.unsqueeze(-1).unsqueeze(-1)
                    count = active.sum(dim=1).clamp(min=1).view(-1, 1, 1)
                    G.nodes[ntype].data['t'] = (stacked * weights).sum(dim=1) / count

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


class HGTLayerSharedProjection(HGTLayer):
    """Reuse k/v/q projections without changing parameters or reduction."""

    def forward(self, G, h ):
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
                attn_score = edge_softmax(sub_graph, attn_score, norm_by='dst')

                sub_graph.edata['t'] = attn_score.unsqueeze(-1)

            active_edge_dict = {
                etype: edge_dict[etype]
                for etype in G.canonical_etypes
                if etype in edge_dict
            }
            if active_edge_dict:
                G.multi_update_all({etype : (fn.u_mul_e('v_%d' % e_id, 't', 'm'), fn.sum('m', 't')) \
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


class HGTLayerSharedProjectionNonEmptyMean(HGTLayerNonEmptyMean):
    """Reuse k/v/q projections without changing parameters or reduction."""

    def forward(self, G, h ):
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
                attn_score = edge_softmax(sub_graph, attn_score, norm_by='dst')

                sub_graph.edata['t'] = attn_score.unsqueeze(-1)

            active_edge_dict = {
                etype: edge_dict[etype]
                for etype in G.canonical_etypes
                if etype in edge_dict
            }
            if active_edge_dict:
                G.multi_update_all({etype : (fn.u_mul_e('v_%d' % e_id, 't', 'm'), fn.sum('m', 't')) \
                                    for etype, e_id in active_edge_dict.items()}, cross_reducer = 'stack')

                # Diagnostic-only change: average only relations that actually
                # deliver a message to each destination node. DGL 0.6.1 stacks
                # relations on dimension 1 in ascending graph edge-type ID.
                for ntype in G.ntypes:
                    incoming = sorted(
                        (etype for etype in active_edge_dict if etype[2] == ntype),
                        key=G.get_etype_id,
                    )
                    if not incoming:
                        continue
                    stacked = G.nodes[ntype].data['t']
                    active = torch.stack(
                        [G.in_degrees(etype=etype) > 0 for etype in incoming],
                        dim=1,
                    ).to(device=stacked.device, dtype=stacked.dtype)
                    weights = active.unsqueeze(-1).unsqueeze(-1)
                    count = active.sum(dim=1).clamp(min=1).view(-1, 1, 1)
                    G.nodes[ntype].data['t'] = (stacked * weights).sum(dim=1) / count

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
