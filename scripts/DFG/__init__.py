"""Legacy DFG modules still used by scripts/node_sem and scripts/edge_sem.

The DFG implementation now lives in the top-level ``dfg`` package. Modules that
moved there are served under their old names by the import hook below, so
``scripts.DFG.frontend`` *is* ``dfg.analysis.frontend`` (one module object). The
remaining files in this directory are kept only because NodeSem/EdgeSem import
them; they are removed when those modules are integrated. Do not add code here.
"""
import importlib
import importlib.abc
import importlib.util
import sys

__version__ = "0.1.1"
DATA_DEF_USE = "DATA_DEF_USE"

MOVED = {
    "models": "dfg.analysis.ir",
    "frontend": "dfg.analysis.frontend",
    "state.stage_f.versioning": "dfg.analysis.frontend",
    "state.stage_f.frontend": "dfg.analysis.frontend",
    "state.stage_k.profile": "dfg.analysis.frontend",
    "symbol_table": "dfg.analysis.symbols",
    "call_binding": "dfg.analysis.symbols",
    "access_extractor": "dfg.analysis.access",
    "dfg_v2.access_shape": "dfg.analysis.access",
    "semantic_cfg": "dfg.analysis.cfg",
    "reaching_definitions": "dfg.analysis.dataflow",
    "state.stage_f.binding": "dfg.analysis.state",
    "state.stage_j.binding": "dfg.analysis.state",
    "state.stage_j.modifiers": "dfg.analysis.state",
    "dfg_v2.units": "dfg.analysis.units",
    "graph_audit": "dfg.graph.audit",
    "projection": "dfg.graph.projection",
    "dfg_v2.projection_view": "dfg.graph.projection",
    "ddg_builder": "dfg.graph.local",
    "dfg_v2.l1_models": "dfg.graph.local",
    "dfg_v2.l1_symbols": "dfg.graph.local",
    "dfg_v2.l1_access": "dfg.graph.local",
    "dfg_v2.l1_cfg": "dfg.graph.local",
    "dfg_v2.l1_rd": "dfg.graph.local",
    "dfg_v2.l1": "dfg.graph.local",
    "dfg_v2.state_binding": "dfg.graph.binding",
    "dfg_v2.state_access": "dfg.graph.binding",
    "dfg_v2.l2": "dfg.graph.state",
    "dfg_v2.env": "dfg.graph.env",
    "dfg_v2.l3": "dfg.graph.env",
    "dfg_v2.pipeline": "dfg.graph.pipeline",
    "dfg_v2.hgt_layer": "dfg.model.hgt",
    "dfg_v2.model_input": "dfg.model.model",
    "dfg_v2.model": "dfg.model.model",
}


class _Alias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        prefix = __name__ + "."
        if fullname.startswith(prefix) and fullname[len(prefix):] in MOVED:
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        module = importlib.import_module(MOVED[spec.name[len(__name__) + 1:]])
        self._spec = module.__spec__
        return module

    def exec_module(self, module):
        # The import system just set the alias spec; keep the module's own identity.
        module.__spec__ = self._spec


if not any(isinstance(f, _Alias) for f in sys.meta_path):
    sys.meta_path.insert(0, _Alias())
