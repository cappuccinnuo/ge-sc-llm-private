"""Reuse the sealed Stage J pipeline bytecode with an explicit local frontend."""
from types import FunctionType
from ..stage_j import pipeline as original
from .profile import SupportedSourceView
from . import VERSION

# Local function context, not a module/global monkeypatch. Algorithm, labels,
# projection and graph materialization are the already-tested Stage J body.
prepare_graph = FunctionType(
    original.prepare_graph.__code__,
    dict(original.prepare_graph.__globals__, StageFSourceView=SupportedSourceView, VERSION=VERSION),
    "prepare_graph", original.prepare_graph.__defaults__, original.prepare_graph.__closure__)
assert original.prepare_graph.__globals__["StageFSourceView"] is not SupportedSourceView
