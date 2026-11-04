"""Add L1 facts only for legacy fallbacks; project with each producing view.

No labels, predictions or token features enter source analysis.
Aggregate aliases and effects of callees are deliberately not summarized.
"""
import copy
import hashlib
from collections import Counter
from dataclasses import asdict, dataclass, field

from scripts.DFG.ddg_builder import DDGBuilder
from scripts.DFG.frontend import FUNCTION_TYPES, parse, text, walk
from scripts.DFG.graph_audit import assert_augmented, fingerprint
from scripts.DFG.models import Unsupported
from scripts.DFG.projection import Projector
from scripts.DFG.symbol_table import _scalar_type
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from . import DATA_DEF_USE, VERSION
from .l1_cfg import V2CFGBuilder
from .l1_rd import solve_v2


@dataclass
class _Analysis:
    facts: list = field(default_factory=list)
    origins: list = field(default_factory=list)
    routes: list = field(default_factory=list)
    views: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _limits(max_iterations):
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")


def _functions(source):
    return [n for n in walk(parse(source).root_node)
            if n.type in FUNCTION_TYPES and n.child_by_field_name("body") is not None]


def _reason(exc):
    return dict(getattr(exc, "diagnostic", {}), reason=str(exc))


def _routes(builder, old_reason, file_fallback):
    routes = []
    if builder.modifier_evidence is not None:
        routes.append("v2_modifier")
    if len(builder.scope.chain) > 1:
        routes.append("v2_inheritance")
    if file_fallback or old_reason in (
            "builtin_not_guaranteed_over_pragma_interval",
            "pragma_missing_for_builtin_availability"):
        routes.append("v2_version")
    # A permitted unnamed aggregate parameter/return has no Symbol ID but
    # still required extended type acceptance. Classify the declaration, not
    # just the registered symbols. This is audit-only and does not change IR.
    extended_declaration = False
    for declaration in walk(builder.function):
        if declaration.type in ("parameter", "variable_declaration"):
            try:
                _scalar_type(declaration)
            except Unsupported:
                extended_declaration = True
                break
    if extended_declaration:
        routes.append("v2_aggregate")
    if any(d.get("kind") == "v2_prefix_access_chain" for d in builder.access.diagnostics):
        routes.append("v2_access_shape")
    return routes or ["v2_retry"]


def _in_modifier(anchor, spans):
    return any(start <= anchor.start and anchor.end <= end for start, end in spans)


def _analyze(source, file, metadata=None, max_iterations=100000):
    _limits(max_iterations)
    old = DDGBuilder(max_iterations).analyze_source(source, file)
    result = _Analysis(
        facts=list(old.facts), origins=["legacy"] * len(old.facts),
        routes=[["legacy"] for _ in old.facts], diagnostics=list(old.diagnostics))
    if old.view is not None:
        result.views["legacy"] = old.view
    old_failures = {d["function"]: d["reason"] for d in old.diagnostics
                    if d.get("kind") == "function_fallback"}
    old_file_reason = next((d["reason"] for d in old.diagnostics
                            if d.get("kind") == "file_fallback"), None)
    functions = old.view.functions if old.view is not None else []
    try:
        if old.view is None:
            functions = _functions(source)
    except Unsupported:
        pass
    supported = {file + ":" + str(n.start_byte) for n in functions
                 if old.view is not None and file + ":" + str(n.start_byte) not in old_failures}
    if len(supported) != old.stats["functions_supported"]:
        raise AssertionError("Legacy success identity accounting differs")
    pending = [n for n in functions if file + ":" + str(n.start_byte) not in supported]
    view, view_error = None, None
    if pending:
        try:
            view = SupportedSourceView(source, file, metadata)
            result.views["v2"] = view
        except Unsupported as exc:
            view_error = str(exc)
            result.diagnostics.append(dict(kind="v2_file_fallback", file=file, reason=view_error,
                                           legacy_results_retained=True))
    modifiers = [(n.start_byte, n.end_byte) for n in walk(view.tree.root_node)
                 if n.type == "modifier_definition"] if view is not None else []
    new_by_id = {file + ":" + str(n.start_byte): n for n in view.functions} if view else {}
    old_fact_counts = Counter(f.use.function for f in old.facts)
    records, filtered = [], []
    for fn in functions:
        ident = file + ":" + str(fn.start_byte)
        name = fn.child_by_field_name("name")
        rec = dict(function=ident, file=file, start=fn.start_byte, end=fn.end_byte,
                   line=fn.start_point[0] + 1,
                   name=text(source, name) if name is not None else fn.type,
                   old_status="supported" if ident in supported else "fallback",
                   old_reason=None if ident in supported else old_failures.get(ident, old_file_reason))
        if ident in supported:
            rec.update(status="supported", routes=["legacy"], facts=old_fact_counts[ident],
                       recovered=False, legacy_reused=True)
        elif view is None:
            rec.update(status="fallback", routes=[], facts=0, recovered=False,
                       reason=view_error or old_file_reason, partial_facts_published=False)
        else:
            try:
                if ident not in new_by_id:
                    raise Unsupported("Function identity differs between source views")
                builder = V2CFGBuilder(view, new_by_id[ident])
                ir = builder.build()
                rd = solve_v2(ir, max_iterations)
                routes = _routes(builder, rec["old_reason"], old.view is None)
                accepted = []
                for fact in rd.facts:
                    if _in_modifier(fact.definition.anchor, modifiers) or _in_modifier(fact.use.anchor, modifiers):
                        filtered.append(dict(function=ident, symbol=fact.symbol,
                                             definition=asdict(fact.definition.anchor),
                                             use=asdict(fact.use.anchor)))
                    else:
                        accepted.append(fact)
                # Commit only after CFG+RD complete; a failed function has no partial facts.
                result.facts.extend(accepted)
                result.origins.extend(["v2"] * len(accepted))
                result.routes.extend([list(routes) for _ in accepted])
                for diagnostic in builder.binding_diagnostics + builder.access.diagnostics:
                    result.diagnostics.append(dict(diagnostic, function=ident, analysis_path="v2"))
                rec.update(status="supported", routes=routes, facts=len(accepted), recovered=True,
                           legacy_reused=False, weak_definitions=sum(len(e.weak_writes)
                               for block in ir.blocks.values() for e in block.events),
                           binding=dict(scope=builder.scope.evidence,
                                        modifier=builder.modifier_evidence,
                                        version=view.version_evidence))
            except Unsupported as exc:
                diagnostic = dict(_reason(exc), kind="v2_function_fallback", function=ident,
                                  file=file, partial_facts_published=False)
                result.diagnostics.append(diagnostic)
                rec.update(status="fallback", routes=[], facts=0, recovered=False,
                           reason=str(exc), partial_facts_published=False)
        records.append(rec)
    routes = Counter(route for rec in records for route in rec["routes"])
    cross = Counter((rec["old_reason"] or "legacy_supported",
                     "+".join(rec["routes"]) if rec["status"] == "supported"
                     else "fallback:" + str(rec["reason"])) for rec in records)
    result.stats = dict(functions_total=len(functions), functions_supported=sum(
        rec["status"] == "supported" for rec in records),
        legacy_supported=len(supported), recovered=sum(rec["recovered"] for rec in records),
        legacy_stats=old.stats, legacy_file_reason=old_file_reason, v2_view_error=view_error,
        facts_total=len(result.facts), legacy_facts=len(old.facts),
        modifier_facts_dropped=len(filtered), modifier_fact_examples=filtered,
        routes=dict(routes), functions=records,
        fallback_reasons=dict(Counter(rec["reason"] for rec in records if rec["status"] == "fallback")),
        recovery_cross_table=[dict(old_reason=old, new_result=new, functions=count)
                              for (old, new), count in sorted(cross.items())],
        approximate_call_effects="aggregate call arguments read only; aliases/callee mutations not summarized")
    return result


def analyze_file(source, file, metadata=None, max_iterations=100000):
    """Return immutable facts, diagnostics and JSON-serializable statistics."""
    result = _analyze(source, file, metadata, max_iterations)
    return result.facts, result.diagnostics, result.stats


def augment_l1(graph, sources, metadata=None, max_iterations=100000):
    """Return a new frozen-node HCG with merged forward DATA_DEF_USE edges."""
    _limits(max_iterations)
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("Expected a directed MultiDiGraph")
    if any(d.get("edge_type") == DATA_DEF_USE or str(d.get("edge_type", "")).startswith("REV_")
           for _, _, d in graph.edges(data=True)):
        raise ValueError("Expected an unenhanced HCG")
    initial = fingerprint(graph)
    output = copy.deepcopy(graph)
    audit = dict(version=VERSION, layer="L1", profile="G1R", files={}, evidence=[],
                 source_hashes={}, labels_used_for_analysis=False, token_features_changed=False)
    builder = DDGBuilder(max_iterations)
    files = list(dict.fromkeys(d["source_file"] for _, d in graph.nodes(data=True)))
    for file in files:
        if file not in sources:
            audit["files"][file] = dict(diagnostics=[dict(kind="file_fallback",
                reason="Source manifest has no exact file identity")])
            continue
        result = _analyze(sources[file], file, (metadata or {}).get(file), max_iterations)
        record = dict(analysis=result.stats, diagnostics=list(result.diagnostics), views={})
        audit["files"][file] = record
        audit["source_hashes"][file] = hashlib.sha256(sources[file].encode("utf8")).hexdigest()
        mapping, projectors = {}, {}
        for origin, view in result.views.items():
            selected = [f for f, path in zip(result.facts, result.origins) if path == origin]
            try:
                projector = Projector(graph, view)
                local_mapping, diagnostics = projector.map_facts(selected)
                for anchor, identifier in local_mapping.items():
                    if anchor in mapping and mapping[anchor] != identifier:
                        raise AssertionError("Producing views disagree on an exact anchor")
                    mapping[anchor] = identifier
                projectors[origin] = projector
                record["diagnostics"].extend(diagnostics)
                record["views"][origin] = dict(projector.stats, scope_mode=view.mode)
            except Unsupported as exc:
                record["diagnostics"].append(dict(kind="projection_fallback", origin=origin,
                                                   reason=str(exc)))
        if len(projectors) == 2:
            if projectors["legacy"].by_ast != projectors["v2"].by_ast:
                raise AssertionError("SourceView and SupportedSourceView AST node projections differ")
            record["projectors_by_ast_equal"] = True
        # Do not let a failed view borrow another view's projection.
        valid = [(f, origin, routes) for f, origin, routes in
                 zip(result.facts, result.origins, result.routes) if origin in projectors]
        facts = [x[0] for x in valid]
        edges, evidence, stats = builder.projected_edges(facts, mapping)
        route_lookup = {(f.definition.id, f.use.id, f.symbol): (origin, routes)
                        for f, origin, routes in valid}
        for ev in evidence:
            origin, routes = route_lookup[(ev["definition"], ev["use"], ev["symbol"])]
            ev.update(analysis_path=origin, routes=list(routes))
        record["projection"] = stats
        record["anchors"] = [dict(asdict(anchor), node_id=identifier)
                             for anchor, identifier in sorted(mapping.items())]
        offset = len(audit["evidence"])
        audit["evidence"].extend(evidence)
        for src, dst, attrs in edges:
            indices = attrs["ddg_fact_indices"]
            attrs["routes"] = sorted({route for i in indices for route in evidence[i]["routes"]})
            attrs["dfg_v2_version"] = VERSION
            attrs["ddg_fact_indices"] = [offset + i for i in indices]
            output.add_edge(src, dst, **attrs)
    audit["invariants"] = assert_augmented(graph, output)
    if fingerprint(graph) != initial:
        raise AssertionError("Input graph mutated")
    return output, audit
