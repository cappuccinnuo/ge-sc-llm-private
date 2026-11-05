"""Retry only frozen Stage F fallbacks; supported Stage F results are untouched."""
from ...models import Unsupported, FunctionIR
from ...frontend import text
from ...symbol_table import SymbolTable
from ...access_extractor import AccessExtractor
from ...semantic_cfg import CFGBuilder
from ..models import StateAnalysisResult
from ..reaching_definitions import solve
from ..stage_f.frontend import StageFSourceView
from ..stage_f.analyzer import StageFExtractor, analyze_view as stage_f_analyze
from ..stage_f.binding import StageFCallResolver
from .binding import ClosedScopeJ
from .modifiers import prefix_modifier

def runtime_function(view, fn):
    if fn.type in ("constructor_definition", "modifier_definition"):
        return False
    name = fn.child_by_field_name("name")
    owner = fn.parent
    while owner is not None and owner.type not in ("contract_declaration", "interface_declaration", "library_declaration"):
        owner = owner.parent
    old_constructor = (view.mode == "legacy" and name is not None and owner is not None
        and text(view.source, name) == text(view.source, owner.child_by_field_name("name")))
    return not old_constructor


class StageJCFGBuilder(CFGBuilder):
    def __init__(self, view, function, enable_modifiers=True):
        self.view, self.function = view, function
        self.table = SymbolTable(view.source, view.file, function, view.mode)
        self.scope = ClosedScopeJ(view, function)
        self.access = AccessExtractor(view.source, self.table)
        self.blocks = {}
        self.call_bindings, self.binding_diagnostics = StageFCallResolver(
            view, function, self.table, self.scope).preflight()
        if not enable_modifiers and any(n.type == "modifier_invocation" for n in function.named_children):
            raise Unsupported("J: modifier recovery disabled")
        self.prefix, self.modifier_evidence = prefix_modifier(view, function, self.scope)

    def build(self):
        entry = self.new([self.access.entry(self.function)])
        tails = self.sequence(self.prefix, {entry})
        self.statement(self.function.child_by_field_name("body"), tails)
        return FunctionIR(self.table.function_id, self.view.file, entry, self.blocks, self.table.symbols)

def analyze_view(view, enable_modifiers=True, max_iterations=100000):
    original = stage_f_analyze(view, max_iterations=max_iterations)
    functions = {view.file + ":" + str(n.start_byte): n for n in view.functions}
    results, records = [], []
    for before in original:
        fn = functions[before.function]
        rec = {"function": before.function, "start": fn.start_byte, "end": fn.end_byte,
               "line": fn.start_point[0]+1, "name": text(view.source, fn.child_by_field_name("name"))
                    if fn.child_by_field_name("name") is not None else fn.type,
               "before": before.status, "before_diagnostics": before.diagnostics,
               "source_sha256": view.sha256}
        if before.ir is not None:
            results.append(before)
            rec.update(after=before.status, route="frozen_stage_f_reused", recovered=False)
        else:
            try:
                builder = StageJCFGBuilder(view, fn, enable_modifiers)
                base = builder.build()
                ir = StageFExtractor(view, fn, builder, base).build()
                after = solve(ir, max_iterations)
                after.binding_evidence = {"scope": builder.scope.evidence,
                    "calls": builder.binding_diagnostics, "version": view.version_evidence,
                    "modifier": builder.modifier_evidence}
                results.append(after)
                rec.update(after=after.status, recovered=True, route="stage_j",
                           binding=after.binding_evidence)
            except Unsupported as exc:
                after = StateAnalysisResult(before.function, "function_fallback",
                    diagnostics=[{"file": view.file, "start": fn.start_byte, "end": fn.end_byte,
                        "line": fn.start_point[0]+1, "reason": str(exc),
                        "partial_state_facts_published": False}])
                results.append(after)
                rec.update(after=after.status, recovered=False, route="stage_j_fallback",
                           after_diagnostics=after.diagnostics)
        result = results[-1]
        rec.update(facts=len(result.facts), runtime_function=runtime_function(view, fn),
                   partial_facts_published=False if result.ir is None else None)
        records.append(rec)
    return results, records

def analyze_source(source, file="example.sol", metadata=None, enable_modifiers=True):
    view = StageFSourceView(source, file, metadata)
    results, records = analyze_view(view, enable_modifiers)
    return view, results, records
