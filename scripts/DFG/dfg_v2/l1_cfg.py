"""L1 analysis-only CFG: unchanged Stage J statements and modifier semantics.

Constructor copied from scripts/DFG/state/stage_j/analyzer.py::StageJCFGBuilder.
Source SHA256: f2934f3efc7d202e6fe78c2f7e26bf172b663067713fb3108e48a522b001d6af
Only the symbol table and access extractor differ; no HCG nodes are added.
"""
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_j.analyzer import StageJCFGBuilder
from scripts.DFG.state.stage_j.binding import ClosedScopeJ
from scripts.DFG.state.stage_j.modifiers import prefix_modifier
from scripts.DFG.state.stage_f.binding import StageFCallResolver
from .l1_symbols import ExtendedSymbolTable
from .l1_access import ExtendedAccessExtractor


class V2CFGBuilder(StageJCFGBuilder):
    def __init__(self, view, function, enable_modifiers=True):
        self.view, self.function = view, function
        # P2 change: keep declaration identities/scopes, permit aggregate locals.
        self.table = ExtendedSymbolTable(view.source, view.file, function, view.mode)
        self.scope = ClosedScopeJ(view, function)
        # P2 change: strong/weak V2Events; inherited build/statement code unchanged.
        self.access = ExtendedAccessExtractor(view.source, self.table)
        self.blocks = {}
        self.call_bindings, self.binding_diagnostics = StageFCallResolver(
            view, function, self.table, self.scope).preflight()
        if not enable_modifiers and any(n.type == "modifier_invocation" for n in function.named_children):
            raise Unsupported("J: modifier recovery disabled")
        self.prefix, self.modifier_evidence = prefix_modifier(view, function, self.scope)
