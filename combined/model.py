"""Build, initialize and validate the combined model of one fold.

Construction (inputs in memory, nothing on disk changes):

1. the task's DFG F3 graph is *carried* with NodeSem's S6 inputs: every node's
   ``token`` becomes the S6 carrier vector (``nodesem.features.carry``);
2. EdgeSem builds its G4R-AC model on that graph (``edgesem.model.build``): the fold's
   G3R anchor re-materialized with typed directions and the E1 relations, edge-aware
   HGT layers and the shared edge-attribute encoder;
3. the anchor's input Linears are replaced by NodeSem adapters, one per node type
   (``nodesem.model.NodeSemAdapter``, the S6 specification).

Initialization joins the two stages' own rules, so each part starts exactly where it
starts in its single-stage run: every graph, relation, edge-encoder and classifier
tensor is EdgeSem's G4R-AC fold initialization; every adapter tensor is NodeSem's
S6@G3R fold initialization (S4 tensors from S4's seeds, the teacher projection new),
computed on the same carried graph. A cascade track (node model on the contract
graph) uses the node task's adapter seeds.
"""
from types import SimpleNamespace

from torch import nn

from combined import EDGE_PROFILE, GRAPH_PROFILE, NODE_CONFIG
from dfg.train.runner import initial_states
from dfg.utils import tensor_digest
from edgesem.model.build import _to_device, make_edge_model
from edgesem.model.build import validate_registration as edge_registration
from nodesem.features import CTX_VIEW, carry, spec_for
from nodesem.model import NodeSemAdapter
from nodesem.train import initial as nodesem_initial

SPEC = spec_for(NODE_CONFIG)


def carried_graph(graph, store):
    """The F3 graph with S6 carrier vectors as node tokens, and the carrier record."""
    return carry(graph, SPEC, store.modalities(CTX_VIEW[NODE_CONFIG]))


def adapter_state(task, task_id, graph_of, store, fold, config, seed):
    """NodeSem's S6@G3R initial adapter tensors of the fold ({adapt_ws.*: tensor}).

    ``graph_of(profile)`` gives the track's G0 (HCG) and G3R (DFG F3) graphs.
    """
    view = SimpleNamespace(task=task, task_id=task_id, graph=graph_of)
    fold_seeds, base = initial_states(task, graph_of, fold, ["G0", GRAPH_PROFILE], config, seed)
    state, _ = nodesem_initial(view, store, NODE_CONFIG, GRAPH_PROFILE, fold, config, fold_seeds, base, {})
    return {k: v for k, v in state.items() if k.startswith("adapt_ws.")}


def make_full_model(task, task_id, graph_of, store, edges, attrs, fold, config, seed=1, device="cpu"):
    """Untrained combined model of one fold on the track's F3 graph ``graph_of("G3R")``
    (no graph is mutated).

    ``task_id`` is the dfg form ``<category>_<node|contract>`` the NodeSem seeds use.
    """
    carried, record = carried_graph(graph_of(GRAPH_PROFILE), store)
    model = make_edge_model(task, carried, EDGE_PROFILE, fold, edges=edges, attrs=attrs, device="cpu",
                            seed=seed, hidden_size=config["hidden_size"], layers=config["layers"],
                            heads=config["heads"])
    if model.in_size != SPEC.carrier_dim():
        raise ValueError("EdgeSem input width differs from the S6 carrier")
    adapters = [NodeSemAdapter(SPEC, ntype, hidden_size=config["hidden_size"])
                for ntype, _ in sorted(model.ntypes_dict.items(), key=lambda item: item[1])]
    model.adapt_ws = nn.ModuleList(adapters)
    state = adapter_state(task, task_id, graph_of, store, fold, config, seed)
    current = {k for k in model.state_dict() if k.startswith("adapt_ws.")}
    if set(state) != current:
        raise ValueError("NodeSem adapter tensors differ from the combined model's adapters")
    model.load_state_dict(dict(model.state_dict(), **state), strict=True)
    model.combined_spec_sha256, model.combined_carrier_record = SPEC.digest(), record
    model.combined_adapter_sha256 = tensor_digest(state)
    _to_device(model, device)
    validate(model)
    return model


def validate(model, deep=True):
    """EdgeSem's registration checks plus the NodeSem adapter and carrier binding."""
    edge_registration(model, deep=deep)
    if model.combined_spec_sha256 != SPEC.digest() or model.in_size != SPEC.carrier_dim():
        raise ValueError("Combined model/spec binding differs")
    if len(model.adapt_ws) != len(model.ntypes_dict):
        raise ValueError("Combined adapter count differs")
    for ntype, index in model.ntypes_dict.items():
        adapter = model.adapt_ws[index]
        if type(adapter) is not NodeSemAdapter or adapter.ntype != ntype or adapter.spec_digest != SPEC.digest():
            raise ValueError("Combined adapter registration differs for " + ntype)
    if deep:
        record = model.combined_carrier_record
        if record["spec_sha256"] != SPEC.digest() or len(record["rows"]) != model.nx_graph.number_of_nodes():
            raise ValueError("Combined carrier record differs")
    return model


def reset_dropout(model, fit_seed, task_id, fold):
    """Seed every adapter's modality dropout from the fit identity (NodeSem's rule)."""
    return {a.ntype: a.reset_dropout(fit_seed, task_id, fold, GRAPH_PROFILE) for a in model.adapt_ws}


def parameters(model):
    return sum(p.numel() for p in model.parameters())
