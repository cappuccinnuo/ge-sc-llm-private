"""Stage G input-only adapter around the unchanged production HGT classifiers.

Only the frozen inside_token constructor path is reproduced here. Forward,
pooling, HGTLayer, node feature conversion and numeric initialization remain the
production implementations. Stage F supplies directional graph materialization.
No module/global monkeypatch and no new parameters at scoring time.
"""
import copy
import re
from pathlib import Path

import networkx as nx
import torch
from torch import nn
import sco_models.graph_utils as gu
from sco_models.model_hgt import HGTVulNodeClassifier, HGTVulGraphClassifier, HGTLayer
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.graph_audit import frozen
from scripts.DFG.state.stage_f.model_adapter import build_dgl, reflected_input
from scripts.DFG.state.stage_f.initialization import initialize_pair, INITIALIZATION_VERSION
from scripts.DFG.experiments.common import sha256, tensor_digest
from scripts.DFG.experiments.paper_runtime import validate_registration as native_registration
from scripts.DFG.experiments.runtime import assert_disconnected_files

ADAPTER_VERSION = "stage-g-original-classifier-forward-adapter-v1"
TRIPLE_INITIALIZATION_VERSION = INITIALIZATION_VERSION + "/triple-chain-v1"


def _construct(model, task, graph_or_path, device, hidden_size, layers, heads):
    nn.Module.__init__(model)
    if task not in ("node", "contract"):
        raise ValueError("Unknown task")
    model.compressed_global_graph_path = (str(graph_or_path) if not isinstance(graph_or_path, nx.Graph)
                                         else "<in-memory-frozen-graph>")
    source = graph_or_path if isinstance(graph_or_path, nx.Graph) else read_graph(Path(graph_or_path))
    if not isinstance(source, nx.MultiDiGraph):
        raise TypeError("Expected the frozen directed multigraph")
    assert_disconnected_files(source)
    model.original_graph_node_ids = list(source)
    model.nx_graph = gu.add_hetero_ids(nx.convert_node_labels_to_integers(copy.deepcopy(source)))
    model.hidden_size, model.num_heads, model.device = hidden_size, heads, str(device)
    model.total_nodes = len(model.nx_graph)
    model.node_ids_dict = gu.get_node_ids_dict(model.nx_graph)
    if task == "node":
        model.node_labels, model.labeled_node_ids, model.label_ids = gu.get_node_label(model.nx_graph)
    else:
        model.node_ids_by_filename = gu.get_node_ids_by_filename(model.nx_graph)
    model.number_of_nodes = gu.get_number_of_nodes(model.nx_graph)
    model.symmetrical_global_graph_data = reflected_input(gu.generate_hetero_graph_data(model.nx_graph))
    # This is the real Stage F adapter, not the legacy reflection followed by a repair.
    model.symmetrical_global_graph, actual_local_ids = build_dgl(model.nx_graph)
    for node, attrs in model.nx_graph.nodes(data=True):
        if actual_local_ids[node] != attrs["node_hetero_id"]:
            raise AssertionError("Adapter changed node type-local row")
    model.symmetrical_global_graph = model.symmetrical_global_graph.to(device)
    model.meta_paths = (gu.get_length_2_metapath(model.symmetrical_global_graph) if task == "node"
                        else gu.get_symmatrical_metapaths(model.symmetrical_global_graph))
    model.full_metapath = {}
    for path in model.meta_paths:
        model.full_metapath.setdefault(path[0][0], []).append(path)
    model.node_types = list(model.symmetrical_global_graph.ntypes)
    model.ntypes_dict = {name: idx for idx, name in enumerate(model.node_types)}
    model.etypes_dict = {c: idx for idx, c in enumerate(model.symmetrical_global_graph.canonical_etypes)}
    for c, idx in model.etypes_dict.items():
        model.symmetrical_global_graph.edges[c].data["id"] = torch.full(
            (model.symmetrical_global_graph.num_edges(c),), idx, dtype=torch.long, device=device)
    model.node_feature = "inside_token"
    features = gu.get_node_token(model.nx_graph)
    model.in_size = list(features.values())[0].shape[-1]
    for typ in model.node_types:
        if features[typ].ndim != 2 or features[typ].shape[1] != model.in_size:
            raise ValueError("Inconsistent frozen input features")
        emb = nn.Parameter(features[typ], requires_grad=False)
        model.symmetrical_global_graph.nodes[typ].data["inp"] = emb.to(device)
    # Preserve the original constructor's module creation order and RNG draws.
    model.gcs = nn.ModuleList()
    model.out_size, model.num_layers = 2, layers
    model.adapt_ws = nn.ModuleList([nn.Linear(model.in_size, hidden_size) for _ in model.ntypes_dict])
    for _ in range(layers):
        model.gcs.append(HGTLayer(hidden_size, hidden_size, model.ntypes_dict,
                                 model.etypes_dict, heads, use_norm=True))
    model.classify = nn.Linear(hidden_size, model.out_size)
    model._stage_g_fresh = True
    model._stage_g_task = task


class StageGNodeClassifier(HGTVulNodeClassifier):
    def __init__(self, graph_or_path, device="cpu", hidden_size=128, layers=2, heads=8):
        _construct(self, "node", graph_or_path, device, hidden_size, layers, heads)


class StageGGraphClassifier(HGTVulGraphClassifier):
    def __init__(self, graph_or_path, device="cpu", hidden_size=128, layers=2, heads=8):
        _construct(self, "contract", graph_or_path, device, hidden_size, layers, heads)


def make_model(task, path, device="cpu", hidden_size=128, layers=2, heads=8):
    if task not in ("node", "contract"):
        raise ValueError("Unknown task")
    cls = StageGNodeClassifier if task == "node" else StageGGraphClassifier
    model = cls(path, device, hidden_size, layers, heads).to(device)
    validate_registration(model)
    return model


def move_to_device(model, device):
    """Move the non-buffer fixed DGL graph together with the nn.Module."""
    model.to(device)
    model.symmetrical_global_graph = model.symmetrical_global_graph.to(device)
    model.device = str(device)
    return model


def validate_registration(model, expected_schema=None, deep=True):
    schema = native_registration(model, expected_schema, deep=False)
    if not deep:
        return schema
    assert_disconnected_files(model.nx_graph)
    expected_ids = gu.get_node_ids_dict(model.nx_graph)
    if model.node_ids_dict != expected_ids:
        raise ValueError("Node row dictionary misaligned")
    if hasattr(model, "node_ids_by_filename") and model.node_ids_by_filename != gu.get_node_ids_by_filename(model.nx_graph):
        raise ValueError("File row dictionary misaligned")
    if hasattr(model, "node_labels") and model.node_labels != gu.get_node_label(model.nx_graph)[0]:
        raise ValueError("Node labels mismatch")
    expected = reflected_input(gu.generate_hetero_graph_data(model.nx_graph))
    graph = model.symmetrical_global_graph
    if set(expected) != set(model.etypes_dict) or set(expected_ids) != set(model.ntypes_dict):
        raise ValueError("Graph/schema mismatch")
    features = gu.get_node_token(model.nx_graph)
    for typ, rows in expected_ids.items():
        if len(rows) != graph.num_nodes(typ):
            raise ValueError("Graph node count mismatch")
        actual = graph.nodes[typ].data["inp"]
        if actual.requires_grad or actual.dtype != features[typ].dtype or not torch.equal(actual.cpu(), features[typ]):
            raise ValueError("Frozen inside_token features mismatch")
    for c, endpoints in expected.items():
        if not all(torch.equal(x.cpu(), y.cpu()) for x, y in zip(endpoints, graph.edges(etype=c, order="eid"))):
            raise ValueError("Graph endpoints mismatch")
    return schema


def semantic_state(model):
    """Views keyed by node names/canonical relations, never by incidental IDs."""
    out = {}
    inverse = {idx: name for name, idx in model.ntypes_dict.items()}
    for name, value in model.state_dict().items():
        if re.match(r"^gcs\.\d+\.relation_(pri|att|msg)$", name):
            for c, idx in model.etypes_dict.items():
                out[name + "|" + repr(c)] = value[idx]
        elif re.match(r"^gcs\.\d+\.skip$", name):
            for typ, idx in model.ntypes_dict.items():
                out[name + "|" + typ] = value[idx]
        else:
            match = re.match(r"^(adapt_ws|gcs\.\d+\.(?:k_linears|q_linears|v_linears|a_linears|norms))\.(\d+)\.(.+)$", name)
            identity = (match.group(1) + "|" + inverse[int(match.group(2))] + "|" + match.group(3)) if match else name
            out[identity] = value
    return out


def _independent_storage(models):
    seen = set()
    for model in models.values():
        pointers = {p.storage().data_ptr() for p in model.parameters()}
        pointers |= {model.symmetrical_global_graph.nodes[t].data["inp"].storage().data_ptr()
                     for t in model.symmetrical_global_graph.ntypes}
        if seen & pointers:
            raise AssertionError("Variant models share parameter or input storage")
        seen |= pointers


def triple_initialize(models, seed=1):
    if set(models) != {"E2", "E3a", "E3b"}:
        raise ValueError("Expected exactly E2/E3a/E3b")
    baseline = models["E2"]
    node_data = frozen(list(baseline.nx_graph.nodes(data=True)))
    for model in models.values():
        validate_registration(model)
        if not getattr(model, "_stage_g_fresh", False):
            raise ValueError("Triple initialization requires fresh constructors")
        if any(p.device.type != "cpu" or p.grad is not None for p in model.parameters()):
            raise ValueError("Triple initialization must precede GPU placement and backward")
        if model._stage_g_task != baseline._stage_g_task or model.original_graph_node_ids != baseline.original_graph_node_ids:
            raise ValueError("Variant task/node IDs differ")
        if frozen(list(model.nx_graph.nodes(data=True))) != node_data:
            raise ValueError("Variant node attributes/features/labels differ")
    pair_a = initialize_pair(models["E2"], models["E3a"], seed=seed)
    pair_b = initialize_pair(models["E3a"], models["E3b"], seed=seed)
    semantic = {v: semantic_state(m) for v, m in models.items()}
    checks = {}
    for a, b in (("E2", "E3a"), ("E2", "E3b"), ("E3a", "E3b")):
        shared = set(semantic[a]) & set(semantic[b])
        if set(semantic[a]) != shared or any(not torch.equal(semantic[a][k], semantic[b][k]) for k in shared):
            raise AssertionError("Common initial parameter mismatch: " + a + "/" + b)
        checks[a + "_" + b] = {"shared_tensor_count": len(shared), "equal": True,
                                 "shared_sha256": tensor_digest({k: semantic[a][k] for k in shared})}
    _independent_storage(models)
    for model in models.values():
        model._stage_g_fresh = False
    state_keys = [k for k in semantic["E3a"] if "STATE_DEF_USE" in k]
    return {"initialization_version": TRIPLE_INITIALIZATION_VERSION,
            "numeric_pair_algorithm": INITIALIZATION_VERSION,
            "seed": int(seed), "chain": {"E2_to_E3a": pair_a, "E3a_to_E3b": pair_b},
            "common_parameters": checks, "state_def_use_shared_slices": len(state_keys),
            "state_def_use_E3a_E3b_equal": all(torch.equal(semantic["E3a"][k], semantic["E3b"][k]) for k in state_keys),
            "independent_parameter_and_input_storage": True, "all_initialization_on_cpu": True,
            "source": "fresh original HGT constructor; no trained checkpoint",
            "state_sha256": {v: tensor_digest(m.state_dict()) for v, m in models.items()}}


def assert_e2_alignment(path, task, seed=1):
    """CPU check against the real unchanged original classifier and feature loader."""
    from scripts.DFG.experiments.runtime import make_model as original_make_model
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        original = original_make_model(task, path, "cpu")
        torch.manual_seed(seed)
        adapted = make_model(task, path, "cpu")
    if any(c[1] in {"STATE_DEF_USE", "STATE_ACCESS_ORDER", "EXTERNAL_CALL_BEFORE_STATE_WRITE"}
           for c in adapted.etypes_dict):
        raise ValueError("Baseline alignment requires E2, without the new state relations")
    if tensor_digest(original.state_dict()) != tensor_digest(adapted.state_dict()):
        raise AssertionError("Original constructor numeric initialization differs")
    if original.node_ids_dict != adapted.node_ids_dict or original.etypes_dict != adapted.etypes_dict:
        raise AssertionError("Baseline rows/schema differ")
    for c in original.etypes_dict:
        if not all(torch.equal(a,b) for a,b in zip(original.symmetrical_global_graph.edges(etype=c),
                                                  adapted.symmetrical_global_graph.edges(etype=c))):
            raise AssertionError("Baseline endpoints differ")
    for typ in original.ntypes_dict:
        if not torch.equal(original.symmetrical_global_graph.nodes[typ].data["inp"],
                           adapted.symmetrical_global_graph.nodes[typ].data["inp"]):
            raise AssertionError("Baseline features differ")
    original.eval(); adapted.eval()
    with torch.no_grad():
        files = sorted(gu.get_node_ids_by_filename(adapted.nx_graph))
        first = original() if task == "node" else original(files)[0]
        second = adapted() if task == "node" else adapted(files)[0]
    if not torch.equal(first, second):
        raise AssertionError("Baseline full-graph forward differs")
    return {"task": task, "device": "cpu", "seed": seed, "state_equal": True,
            "features_equal": True, "endpoints_equal": True, "node_rows_equal": True,
            "eval_forward_bitwise_equal": True, "logits_shape": list(first.shape),
            "initial_state_sha256": tensor_digest(adapted.state_dict()),
            "logits_sha256": tensor_digest({"logits": second}), "adapter_version": ADAPTER_VERSION}


def provenance():
    root = Path(__file__).resolve().parents[4]
    paths = ["sco_models/model_hgt.py", "sco_models/graph_utils.py",
             "scripts/DFG/experiments/paper_runtime.py", "scripts/DFG/state/stage_f/model_adapter.py",
             "scripts/DFG/state/stage_f/initialization.py", "scripts/DFG/experiments/e23_pilot/model.py"]
    return {"adapter_version": ADAPTER_VERSION,
            "constructor_path": "inside_token original allocation order; Stage F input reflection",
            "forward_reused_without_override": True,
            "source_sha256": {name: sha256(root / name) for name in paths}}
