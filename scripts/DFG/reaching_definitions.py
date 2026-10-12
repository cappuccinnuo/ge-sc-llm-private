"""Intraprocedural, flow-sensitive reaching definitions for statement events.

Definition identities are static. The worklist must converge before facts are
published; unsupported resource limits never return a partial dependence graph.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Set

from .models import Definition, Fact, Unsupported


@dataclass
class RDResult:
    facts: List[Fact]
    in_sets: Dict[str, FrozenSet[str]]
    out_sets: Dict[str, FrozenSet[str]]
    definitions: Dict[str, Definition]
    reachable: Set[str]
    iterations: int
    uses_total: int
    uses_resolved: int


def _validate_and_index(ir):
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
            for symbol_id in tuple(event.reads) + tuple(event.writes):
                if symbol_id not in ir.symbols:
                    raise Unsupported("RD event references an unknown symbol")
            for symbol_id in dict.fromkeys(event.writes):
                definition_id = event.id + ":" + symbol_id
                if definition_id in definitions:
                    raise Unsupported("RD static definition identity collision")
                definition = Definition(
                    definition_id, symbol_id, event.id, ir.id, event.anchor)
                definitions[definition_id] = definition
                by_symbol[symbol_id].add(definition_id)
    return definitions, by_symbol, predecessors


def _reachable_order(ir):
    order, seen = [], {ir.entry}
    pending = deque([ir.entry])
    while pending:
        identifier = pending.popleft()
        order.append(identifier)
        for successor in sorted(ir.blocks[identifier].successors):
            if successor not in seen:
                seen.add(successor)
                pending.append(successor)
    return order, seen


def solve(ir, max_iterations=100000):
    """Return direct def-to-read facts after a real fixed point.

    uses_total/resolved count distinct (event, symbol) reads in reachable blocks;
    a read with several reaching definitions counts once, with several facts.
    iterations counts worklist block evaluations, including unchanged blocks.
    Unreachable static definitions remain in the identity index for auditing,
    but never enter IN, OUT, facts, or use-coverage counts.
    """
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    definitions, by_symbol, predecessors = _validate_and_index(ir)
    order, reachable = _reachable_order(ir)
    generated, killed = {}, {}
    for identifier in order:
        last_definition, writes = {}, set()
        for event in ir.blocks[identifier].events:
            for symbol_id in dict.fromkeys(event.writes):
                writes.add(symbol_id)
                last_definition[symbol_id] = event.id + ":" + symbol_id
        generated[identifier] = frozenset(last_definition.values())
        killed[identifier] = set()
        for symbol_id in writes:
            killed[identifier].update(by_symbol[symbol_id])
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
    # Resolve individual reads only now: a block's final GEN does not describe
    # a read occurring before a later write inside that same block.
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
        if current != out_sets[identifier]:
            raise AssertionError("RD block transfer and ordered event replay disagree")
    return RDResult(
        facts, in_sets, out_sets, definitions, reachable, iterations,
        uses_total, uses_resolved)
