"""EP7 G4R-P: sealed real E1 provenance with independent topology-only rows."""
import copy
from pathlib import Path
import networkx as nx
from sco_models import graph_utils as gu
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.experiment.init import seeds
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.experiments.common import digest
from . import NEW_RELATIONS
from .io import ref, read, checked
from .build_f4 import load_edges, add_edges
from .placebo import randomize_edges, add_placebo_edges


def make_relation_placebo(task, source, manifest_path, device, fold,
                          node_feature, hidden_size, layers, heads):
    from .model import make_edge_model, validate_registration
    path = Path(manifest_path).resolve()
    manifest = read(path)
    if manifest["task_id"].rsplit("_", 1)[-1] != task:
        raise ValueError("Placebo task granularity differs")
    source = source if isinstance(source, nx.Graph) else read_graph(Path(source))
    if not isinstance(source, nx.MultiDiGraph):
        raise TypeError("Expected directed multigraph")
    before = graph_fingerprint(source)
    base = copy.deepcopy(source)
    existing = [(s, t, k) for s, t, k, d in base.edges(keys=True, data=True)
                if d.get("edge_type") in NEW_RELATIONS]
    base.remove_edges_from(existing)
    real_rows = load_edges(path)
    # Semantic evidence continues through the original strict validator.
    real_graph = add_edges(base, real_rows)
    if existing and graph_fingerprint(real_graph) != before:
        raise ValueError("Supplied E1 graph differs from the sealed real rows")
    seed_info = seeds(task, fold)
    rows, audit = randomize_edges(base, real_rows, seed=seed_info["constructor"])
    randomized = add_placebo_edges(base, rows, real_rows)
    model = make_edge_model(task, randomized, "G4R", device=device, fold=fold,
                            node_feature=node_feature, hidden_size=hidden_size, layers=layers, heads=heads)
    model.edge_profile = "G4R-P"
    model.edge_placebo_source = base
    model.edge_placebo_fold = fold
    model.edge_placebo_binding = dict(
        f4_manifest=ref(path), source_fingerprint=graph_fingerprint(base),
        real_rows_sha256=digest(real_rows), rows_sha256=digest(rows), audit=audit)
    if graph_fingerprint(source) != before:
        raise AssertionError("Original F3 graph mutated")
    validate_registration(model)
    return model


def validate_relation_placebo(model, deep=True):
    binding = model.edge_placebo_binding
    expected_seed = seeds(model.dfg_task, model.edge_placebo_fold)
    if model.edge_seeds != expected_seed or binding["audit"]["seed"] != expected_seed["constructor"]:
        raise ValueError("Placebo seed/fold differs")
    path = checked(binding["f4_manifest"])
    if read(path)["task_id"].rsplit("_", 1)[-1] != model.dfg_task:
        raise ValueError("Placebo task differs")
    if not deep:
        return
    source = model.edge_placebo_source
    if any(d.get("edge_type") in NEW_RELATIONS for _, _, d in source.edges(data=True)):
        raise ValueError("Placebo base contains E1")
    if graph_fingerprint(source) != binding["source_fingerprint"]:
        raise ValueError("Placebo original source fingerprint differs")
    real = load_edges(path)
    if digest(real) != binding["real_rows_sha256"]:
        raise ValueError("Placebo real row identity differs")
    rows, audit = randomize_edges(source, real, seed=expected_seed["constructor"])
    if audit != binding["audit"] or digest(rows) != binding["rows_sha256"]:
        raise ValueError("Placebo recomputation/audit differs")
    expected = gu.add_hetero_ids(nx.convert_node_labels_to_integers(add_placebo_edges(source, rows, real)))
    if graph_fingerprint(expected) != graph_fingerprint(model.nx_graph):
        raise ValueError("Placebo model graph differs from recomputed edges")
