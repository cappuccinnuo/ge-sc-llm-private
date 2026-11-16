"""EP6 forward adapters; adopt only a fresh private structural model.

Copied forward: sco_models/model_hgt.py:420-432,590-613.
SHA256 4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947
Pooling, node order, adaptation and classification are unchanged. The sole
addition is a model-level edge encoder evaluated once per relation per forward.
No frozen class/module/function is rebound.
"""
import torch
from torch import nn
import torch.nn.functional as F
from scripts.DFG.dfg_v2.model import DfgV2NodeClassifier, DfgV2GraphClassifier


class EdgeForward:
    def __init__(self, fresh):
        nn.Module.__init__(self)
        # Ownership transfer of an unexposed, newly constructed private model.
        self.__dict__.update(fresh.__dict__)

    def edge_embeddings(self):
        g=self.symmetrical_global_graph
        return {c:self.edge_encoder(g.edges[c].data["ea"][:,list(self.edge_indices)])
                for c in g.canonical_etypes}


class EdgeNodeClassifier(EdgeForward, DfgV2NodeClassifier):
    def forward(self):
        psi = self.edge_embeddings()
        h = {}
        hiddens = torch.zeros((self.symmetrical_global_graph.number_of_nodes(), self.hidden_size), device=self.device)
        for ntype in self.symmetrical_global_graph.ntypes:
            n_id = self.ntypes_dict[ntype]
            h[ntype] = F.gelu(self.adapt_ws[n_id](self.symmetrical_global_graph.nodes[ntype].data['inp']))
        for i in range(self.num_layers):
            h = self.gcs[i](self.symmetrical_global_graph, h, psi)
        for ntype, feature in h.items():
            assert len(self.node_ids_dict[ntype]) == feature.shape[0]
            hiddens[self.node_ids_dict[ntype]] = feature
        output = self.classify(hiddens)
        return output


class EdgeGraphClassifier(EdgeForward, DfgV2GraphClassifier):
    def forward(self, batched_g_name, save_featrues=None):
        psi = self.edge_embeddings()
        h = {}
        hiddens = torch.zeros((self.symmetrical_global_graph.number_of_nodes(), self.hidden_size), device=self.device)
        for ntype in self.symmetrical_global_graph.ntypes:
            n_id = self.ntypes_dict[ntype]
            h[ntype] = F.gelu(self.adapt_ws[n_id](self.symmetrical_global_graph.nodes[ntype].data['inp']))
        for i in range(self.num_layers):
            h = self.gcs[i](self.symmetrical_global_graph, h, psi)
        for ntype, feature in h.items():
            assert len(self.node_ids_dict[ntype]) == feature.shape[0]
            hiddens[self.node_ids_dict[ntype]] = feature
        batched_graph_embedded = []
        for g_name in batched_g_name:
            node_list = self.node_ids_by_filename[g_name]
            # GRADIENT FIX: keep the pooled tensor connected to the HGT layers.
            # Original: batched_graph_embedded.append(hiddens[node_list].mean(0).tolist())
            batched_graph_embedded.append(hiddens[node_list].mean(0))
        # GRADIENT FIX: stack preserves autograd; rebuilding a tensor detaches it.
        # Original: batched_graph_embedded = torch.tensor(batched_graph_embedded).to(self.device)
        batched_graph_embedded = torch.stack(batched_graph_embedded, dim=0)
        if save_featrues:
            torch.save(batched_graph_embedded, save_featrues)
        output = self.classify(batched_graph_embedded)
        return output, batched_graph_embedded


