"""Read-only complete L1 IR event inventory for external validation.

This is NOT token-occurrence counting and NOT projected DDG-edge recall.
Locations are raw UTF-8 statement starts (entry writes use declaration starts).
Existing analyzer routes and original source metadata are reused unchanged.
"""
from collections import Counter
from dataclasses import asdict
import hashlib

from scripts.DFG.frontend import walk
from scripts.DFG.semantic_cfg import CFGBuilder
from scripts.DFG.reaching_definitions import _reachable_order
from .l1 import _analyze
from .l1_cfg import V2CFGBuilder

VERSION = "dfg-v2-l1-ir-occurrences-v1"
SCOPE = "complete_unprojected_IR_event_symbol_sets; raw_statement_start_lines"


def _line(raw, offset):
    if type(offset) is not int or not 0 <= offset <= len(raw):
        raise ValueError("Invalid raw UTF-8 byte offset")
    raw[:offset].decode("utf8")  # Reject offsets inside a multibyte character.
    return raw[:offset].count(b"\n") + 1


def extract(source, file, metadata=None, max_iterations=100000):
    """Rebuild IR only for functions accepted by the existing routing policy.

    No graph is constructed or loaded. No metadata is synthesized from the
    chosen external compiler. A rebuild failure is an integration error, not
    silently downgraded to a new fallback.
    """
    raw = source.encode("utf8")
    analysis = _analyze(source, file, metadata, max_iterations)
    rows, functions = [], []
    for record in analysis.stats["functions"]:
        function = dict(record)
        function["event_count"] = 0
        function["occurrence_count"] = 0
        if record["status"] != "supported":
            functions.append(function)
            continue
        origin = "legacy" if record["legacy_reused"] else "v2"
        view = analysis.views[origin]
        if view.source != source or view.file != file:
            raise ValueError("L1 inventory source/view identity mismatch")
        matches = [fn for fn in view.functions
                   if fn.start_byte == record["start"] and fn.end_byte == record["end"]]
        if len(matches) != 1:
            raise ValueError("L1 inventory function AST identity mismatch")
        builder = (CFGBuilder if origin == "legacy" else V2CFGBuilder)(view, matches[0])
        ir = builder.build()
        if ir.id != record["function"] or ir.file != file:
            raise ValueError("L1 inventory IR identity mismatch")
        _, reachable = _reachable_order(ir)
        modifiers = [(n.start_byte, n.end_byte) for n in walk(view.tree.root_node)
                     if n.type == "modifier_definition"]
        aggregate = getattr(builder.table, "aggregate_info", {})
        current = []
        for block_id, block in sorted(ir.blocks.items()):
            for event in block.events:
                if event.function != ir.id or event.anchor.file != file:
                    raise ValueError("L1 inventory event/function identity mismatch")
                if not 0 <= event.anchor.start <= event.anchor.end <= len(raw):
                    raise ValueError("L1 inventory invalid event span")
                function["event_count"] += 1
                kinds = [("USE", event.reads, False),
                         ("DEF", event.writes, False),
                         ("DEF", getattr(event, "weak_writes", ()), True)]
                for kind, symbols, weak in kinds:
                    for symbol_id in symbols:
                        if symbol_id not in ir.symbols:
                            raise ValueError("L1 inventory unknown symbol")
                        symbol = ir.symbols[symbol_id]
                        if symbol.function != ir.id or symbol.declaration.file != file:
                            raise ValueError("L1 inventory symbol identity mismatch")
                        if not 0 <= symbol.declaration.start <= symbol.declaration.end <= len(raw):
                            raise ValueError("L1 inventory invalid declaration span")
                        start = (symbol.declaration.start if event.kind == "entry"
                                 else event.anchor.start)
                        tags = []
                        if event.kind == "entry":
                            tags.append("entry_initialization")
                        if block_id not in reachable:
                            tags.append("unreachable_ir")
                        if any(a <= event.anchor.start and event.anchor.end <= b
                               for a, b in modifiers):
                            tags.append("modifier_inlining")
                        if aggregate.get(symbol_id, {}).get("location") == "storage":
                            tags.append("alias")
                        current.append(dict(
                            file=file, function=ir.id, function_start=record["start"],
                            function_end=record["end"], symbol=symbol_id,
                            declaration=asdict(symbol.declaration), name=symbol.name,
                            symbol_kind=symbol.kind, type=symbol.type_name,
                            line=_line(raw, start), kind=kind, event_id=event.id,
                            event_kind=event.kind, event_anchor=asdict(event.anchor),
                            weak_write=weak, reachable=block_id in reachable,
                            origin=origin, routes=list(record["routes"]), tags=tags))
        # Commit after a complete successful rebuild, never publish partial IR.
        function["occurrence_count"] = len(current)
        rows.extend(current)
        functions.append(function)
    facts = {}
    identities = {}
    for row in rows:
        fact = (row["line"], row["name"], row["kind"])
        facts.setdefault(fact, set()).update(row["tags"])
        identities.setdefault(fact, set()).add(
            (row["function_start"], row["declaration"]["start"], row["symbol"]))
    ambiguous = [dict(fact=list(fact), identities=[list(i) for i in sorted(ids)])
                 for fact, ids in sorted(identities.items()) if len(ids) > 1]
    return facts, dict(
        version=VERSION, scope=SCOPE, source_sha256=hashlib.sha256(raw).hexdigest(),
        functions=functions, occurrences=rows, ambiguous_triples=ambiguous,
        functions_supported=sum(f["status"] == "supported" for f in functions),
        functions_fallback=sum(f["status"] != "supported" for f in functions),
        event_symbol_occurrences=len(rows), distinct_line_name_kind_facts=len(facts),
        tag_counts=dict(Counter(tag for row in rows for tag in row["tags"])),
        analyzer_diagnostics=analysis.diagnostics, analysis_stats=analysis.stats,
        no_projection=True, token_occurrence_count=False, ddg_edge_recall=False)
