"""Per-file semantic CFG (DFG analyzers) and exact declaration lookup for facts."""
import networkx as nx

from dfg.analysis.cfg import CFGBuilder
from dfg.analysis.frontend import SourceView, SupportedSourceView
from dfg.analysis.ir import Unsupported
from dfg.analysis.symbols import SymbolTable
from dfg.graph.local import ExtendedSymbolTable, V2CFGBuilder


# ----------------------------------------------------------------------
# node_sem/facts_cfg
# Frozen legacy-then-v2 semantic CFG and exact declaration lookup.
#
# Control-flow IR is analysis-only. No HCG edge or node is constructed here.
# Only declared Symbol fields are exposed; opaque IDs are lookup keys, never
# split into names and never emitted as feature strings.
def key(node):
    return node.start_byte, node.end_byte, node.type

class FileCFG:
    def __init__(self, source, file, metadata=None):
        self.source, self.file = source, file
        self.views, self.view_errors, self.results, self.tables = {}, {}, {}, {}
        for name, cls in (("legacy", SourceView), ("v2", SupportedSourceView)):
            try:
                self.views[name] = cls(source, file) if name == "legacy" else cls(source, file, metadata)
            except Unsupported as exc:
                self.view_errors[name] = str(exc)

    def build(self, function):
        identity = key(function)
        if identity in self.results:
            return self.results[identity]
        errors = {}
        for route, cls in (("legacy", CFGBuilder), ("v2", V2CFGBuilder)):
            if route not in self.views:
                errors[route] = self.view_errors[route]
                continue
            view = self.views[route]
            fn = view.raw_nodes.get(identity)
            if fn is None:
                raise ValueError("Semantic frontend changed exact AST identity")
            try:
                builder = cls(view, fn)
                ir = builder.build()
                result = dict(status="supported", route=route, ir=ir, errors=errors)
                self.results[identity] = result
                return result
            except Unsupported as exc:
                errors[route] = str(exc)
        result = dict(status="unknown", errors=errors)
        self.results[identity] = result
        return result

    def symbol(self, function, route, ident):
        lookup = (key(function), route)
        if lookup not in self.tables:
            view = self.views.get(route)
            if view is None:
                raise ValueError("Sealed supported symbol route unavailable")
            cls = SymbolTable if route == "legacy" else ExtendedSymbolTable
            fn = view.raw_nodes.get(key(function))
            if fn is None:
                raise ValueError("Declaration identity absent in original source")
            self.tables[lookup] = cls(self.source, self.file, fn, view.mode)
        symbol = self.tables[lookup].symbols.get(ident)
        if symbol is None:
            raise ValueError("Sealed symbol identity absent in frozen declaration table")
        return symbol

def apply_order(records, mapped_nodes, cfg, function, projection, projector, offsets):
    """Per-function reachability/dominance with all intermediate blocks retained.

    mapped_nodes maps original HCG IDs to raw AST nodes in this function.
    Eventless and unprojected blocks remain in the graph, hence cannot create
    false shortcuts or make conditional calls dominate an unconditional join.
    """
    result = cfg.build(function)
    eligible = [n for n in mapped_nodes if records[n].get("order")]
    if result["status"] != "supported":
        for n in eligible:
            records[n]["unresolved"]["semantic_cfg_unsupported"] = 1
        return dict(status="unknown", errors=result["errors"], missing_anchors=0)
    ir = result["ir"]
    graph = nx.DiGraph()
    graph.add_nodes_from(ir.blocks)
    for block in ir.blocks.values():
        graph.add_edges_from((block.id, other) for other in block.successors)
    if ir.entry not in graph:
        raise ValueError("Missing CFG entry")
    reached = {ir.entry} | nx.descendants(graph, ir.entry)
    active = graph.subgraph(reached)
    dominators = nx.immediate_dominators(active, ir.entry)
    dominators.setdefault(ir.entry, ir.entry)
    node_blocks, missing = {}, 0
    for block in ir.blocks.values():
        for event in block.events:
            anchor = event.anchor
            try:
                compat = projection.compat_key(anchor)
                nid = projector.by_ast.get(projection.compat_ids[compat])
                if nid is None:
                    missing += 1
                    continue
            except Unsupported:
                missing += 1
                continue
            if nid in mapped_nodes:
                node_blocks.setdefault(nid, set()).add(block.id)
    external = {n for n in eligible if records[n]["external"].get("kinds")}
    writers = {n for n in eligible if records[n]["state"].get("writes")}
    descendants = {b: nx.descendants(active, b) for b in active}
    def reaches(a, b):
        if a == b:
            return False
        return any(y in descendants.get(x, ()) for x in node_blocks.get(a, ())
                   for y in node_blocks.get(b, ()))
    def dominates(a, b):
        targets = node_blocks.get(b, set()) & reached
        sources = node_blocks.get(a, set()) & reached
        if a == b or not targets or not sources:
            return False
        for dst in targets:
            chain, cursor = set(), dst
            while cursor not in chain:
                chain.add(cursor)
                cursor = dominators[cursor]
            if not sources.intersection(chain):
                return False
        return True
    for nid in eligible:
        order = records[nid]["order"]
        if nid not in node_blocks:
            records[nid]["unresolved"]["cfg_event_not_projected"] = 1
            continue
        order.update(status="supported", reachable_from_ext_call=any(reaches(x,nid) for x in external),
                     dominated_by_ext_call=any(dominates(x,nid) for x in external),
                     write_then_call=nid in writers and any(reaches(nid,x) for x in external),
                     call_then_write=nid in external and any(reaches(nid,x) for x in writers))
        # Nearest in reverse CFG BFS; deterministic tie-break is AST preorder.
        candidates = []
        for source in external - {nid}:
            distances = [nx.shortest_path_length(active, a, b)
                         for a in node_blocks.get(source, ()) for b in node_blocks.get(nid, ())
                         if a in active and b in descendants.get(a, ())]
            if distances:
                candidates.append((min(distances), offsets.get(source, 0), str(source), source))
        if candidates:
            other = min(candidates)[3]
            order["pre_ext_call"] = dict(node=other, offset=offsets[other]-offsets[nid])
    return dict(status="supported", route=result["route"], missing_anchors=missing,
                blocks=len(graph), reachable_blocks=len(reached))
