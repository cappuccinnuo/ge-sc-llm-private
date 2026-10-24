"""DFG v2 reaching definitions with strong and weak aggregate writes.

Source: scripts/DFG/reaching_definitions.py
Source SHA256: d3b35d9696a0ad922274ea9c36595531930ab46a50106bfa9a03d3634476846f
Copied algorithm: solve and _validate_and_index; _reachable_order and RDResult
are imported unchanged. The only transfer extension is that weak writes GEN
without KILL. This analysis IR never changes the model CFG or graph labels.
"""
from collections import defaultdict, deque

from scripts.DFG.models import Definition, Fact, Unsupported
from scripts.DFG.reaching_definitions import RDResult, _reachable_order


SOURCE_SHA256 = "d3b35d9696a0ad922274ea9c36595531930ab46a50106bfa9a03d3634476846f"


def _validate_and_index_v2(ir):
    if ir.entry not in ir.blocks:
        raise Unsupported("RD entry block is absent")
    for identifier, symbol in ir.symbols.items():
        if identifier != symbol.id or symbol.function != ir.id:
            raise Unsupported("RD symbol belongs to another function or has inconsistent ID")
        if symbol.declaration.file != ir.file:
            raise Unsupported("RD symbol source file differs from its function")
    events = set()
    definitions = {}
    by_symbol = defaultdict(set)
    predecessors = {identifier: set() for identifier in ir.blocks}
    for identifier in sorted(ir.blocks):
        block = ir.blocks[identifier]
        if identifier != block.id:
            raise Unsupported("RD block dictionary key differs from its ID")
        for successor in block.successors:
            if successor not in ir.blocks:
                raise Unsupported("RD successor block is absent: " + str(successor))
            predecessors[successor].add(identifier)
        for event in block.events:
            if event.id in events:
                raise Unsupported("RD event IDs must be unique")
            events.add(event.id)
            if event.function != ir.id or event.anchor.file != ir.file:
                raise Unsupported("RD event belongs to another function or file")
            # V2: original Event is still accepted for scalar parity probes.
            weak_writes = tuple(getattr(event, "weak_writes", ()))
            if set(event.writes).intersection(weak_writes):
                raise Unsupported("RD event contains overlapping strong and weak writes")
            for symbol_id in tuple(event.reads) + tuple(event.writes) + weak_writes:
                if symbol_id not in ir.symbols:
                    raise Unsupported("RD event references an unknown symbol")
            # V2: weak definitions have the same static identity scheme.
            for symbol_id in dict.fromkeys(tuple(event.writes) + weak_writes):
                definition_id = event.id + ":" + symbol_id
                if definition_id in definitions:
                    raise Unsupported("RD static definition identity collision")
                definition = Definition(
                    definition_id, symbol_id, event.id, ir.id, event.anchor)
                definitions[definition_id] = definition
                by_symbol[symbol_id].add(definition_id)
    return definitions, by_symbol, predecessors


def solve_v2(ir, max_iterations=100000):
    """Return direct def-to-read facts after convergence, retaining weak defs.

    Strong writes replace all incoming definitions of that declaration identity.
    Weak writes add a definition while retaining the earlier possible values.
    Reads precede writes within an event. Unreachable definitions remain indexed
    for auditing but do not produce facts. Worklist ordering and accounting are
    unchanged from the scalar solver, including when weak_writes is empty.
    """
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    definitions, by_symbol, predecessors = _validate_and_index_v2(ir)
    order, reachable = _reachable_order(ir)
    generated, killed = {}, {}
    for identifier in order:
        block_generated, block_killed = set(), set()
        for event in ir.blocks[identifier].events:
            for symbol_id in dict.fromkeys(event.writes):
                # V2: a strong write also removes earlier weak writes in block.
                block_generated.difference_update(by_symbol[symbol_id])
                block_generated.add(event.id + ":" + symbol_id)
                block_killed.update(by_symbol[symbol_id])
            for symbol_id in dict.fromkeys(getattr(event, "weak_writes", ())):
                block_generated.add(event.id + ":" + symbol_id)
        generated[identifier] = frozenset(block_generated)
        killed[identifier] = block_killed
    in_sets = {identifier: frozenset() for identifier in ir.blocks}
    out_sets = {identifier: frozenset() for identifier in ir.blocks}
    # All reachable blocks start pending, including blocks reached via an empty
    # entry. Enqueuing only after nonempty changes would otherwise miss them.
    pending = deque(order)
    queued = set(order)
    iterations = 0
    while pending:
        if iterations >= max_iterations:
            raise Unsupported("RD worklist did not converge within max_iterations")
        identifier = pending.popleft()
        queued.remove(identifier)
        iterations += 1
        incoming = set()
        for predecessor in predecessors[identifier]:
            if predecessor in reachable:
                incoming.update(out_sets[predecessor])
        new_in = frozenset(incoming)
        new_out = frozenset((incoming - killed[identifier]) | generated[identifier])
        in_sets[identifier] = new_in
        if new_out != out_sets[identifier]:
            out_sets[identifier] = new_out
            for successor in sorted(ir.blocks[identifier].successors):
                if successor not in queued:
                    pending.append(successor)
                    queued.add(successor)
    # Resolve reads only after fixed point; final block GEN does not describe
    # a read before a later write inside the same block.
    facts, uses_total, uses_resolved = [], 0, 0
    for identifier in order:
        current = set(in_sets[identifier])
        for event in ir.blocks[identifier].events:
            for symbol_id in dict.fromkeys(event.reads):
                uses_total += 1
                reaching = current.intersection(by_symbol[symbol_id])
                if reaching:
                    uses_resolved += 1
                for definition_id in sorted(reaching):
                    facts.append(Fact(symbol_id, definitions[definition_id], event))
            for symbol_id in dict.fromkeys(event.writes):
                current.difference_update(by_symbol[symbol_id])
                current.add(event.id + ":" + symbol_id)
            # V2: replay must retain prior possible aggregate values as well.
            for symbol_id in dict.fromkeys(getattr(event, "weak_writes", ())):
                current.add(event.id + ":" + symbol_id)
        if current != out_sets[identifier]:
            raise AssertionError("RD block transfer and ordered event replay disagree")
    return RDResult(
        facts, in_sets, out_sets, definitions, reachable, iterations,
        uses_total, uses_resolved)
