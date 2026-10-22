"""Bind every profile to the existing five-relation forward adapter."""
from pathlib import Path
from scripts.labeling_v2.safe_graph import read_graph
from ..experiments.guard_extension.model import make_model as original_make_model
from ..experiments.guard_extension.model import reflected_input, build_dgl
from ..model_validation import capture_model_input
from .pipeline import assert_profile
from . import VERSION


def make_model(task, graph, profile, device="cpu", hidden_size=128, layers=2, heads=8):
    if not hasattr(graph, "nodes"):
        graph = read_graph(Path(graph))
    assert_profile(graph, profile)
    model = original_make_model(task, graph, device, hidden_size, layers, heads)
    model.integration_profile = profile
    model.integration_version = VERSION
    capture_model_input(model, {"profile": profile, "integration_version": VERSION})
    return model
