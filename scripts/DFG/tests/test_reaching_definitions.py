"""Hand-authored semantic CFGs exercise the fixed point independently of parsing."""
import pytest
from scripts.DFG.models import Block, Event, FunctionIR, Span, Symbol, Unsupported
from scripts.DFG.reaching_definitions import solve


FILE, FUNC = "a.sol", "a.sol:0"


def symbol(name):
    return Symbol(name, name, FUNC, Span(FILE, 0, 1, "local"), "local", "uint")


def event(name, reads=(), writes=()):
    return Event(name, FUNC, Span(FILE, 1, 2, "statement"), tuple(reads), tuple(writes))


def graph(blocks, names=("x", "y"), entry="entry"):
    return FunctionIR(FUNC, FILE, entry, {b.id: b for b in blocks},
                      {name: symbol(name) for name in names})


def pairs(result):
    return {(fact.definition.event, fact.use.id, fact.symbol) for fact in result.facts}


def test_ordered_block_kills_and_direct_not_transitive_facts():
    ir = graph([Block("entry", [
        event("x0", writes=("x",)), event("y0", reads=("x",), writes=("y",)),
        event("x1", writes=("x",)), event("read", reads=("x", "y")),
    ])])
    result = solve(ir)
    assert pairs(result) == {("x0", "y0", "x"), ("x1", "read", "x"), ("y0", "read", "y")}
    assert result.out_sets["entry"] == frozenset({"x1:x", "y0:y"})
    assert result.uses_total == result.uses_resolved == 3
    assert ("x0", "read", "x") not in pairs(result)


def test_if_join_merges_definitions_and_counts_read_once():
    ir = graph([
        Block("entry", [], {"left", "right"}),
        Block("left", [event("left_x", writes=("x",))], {"join"}),
        Block("right", [event("right_x", writes=("x",))], {"join"}),
        Block("join", [event("use_x", reads=("x",))]),
    ])
    result = solve(ir)
    assert pairs(result) == {("left_x", "use_x", "x"), ("right_x", "use_x", "x")}
    assert result.in_sets["join"] == frozenset({"left_x:x", "right_x:x"})
    assert result.uses_total == result.uses_resolved == 1


def test_unreachable_definition_with_edge_to_reachable_join_does_not_leak():
    ir = graph([
        Block("entry", [], {"live"}),
        Block("live", [event("live_x", writes=("x",))], {"join"}),
        Block("dead", [event("dead_x", writes=("x",)), event("dead_use", reads=("x",))], {"join"}),
        Block("join", [event("use", reads=("x",))]),
    ])
    result = solve(ir)
    assert result.reachable == {"entry", "live", "join"}
    assert result.in_sets["dead"] == result.out_sets["dead"] == frozenset()
    assert pairs(result) == {("live_x", "use", "x")}
    assert "dead_x:x" in result.definitions
    assert result.uses_total == 1


def test_loop_needs_multiple_visits_and_reaches_real_fixed_point():
    ir = graph([
        Block("entry", [event("initial", writes=("x",))], {"head"}),
        Block("head", [event("condition", reads=("x",))], {"body", "exit"}),
        Block("body", [event("increment", reads=("x",), writes=("x",))], {"head"}),
        Block("exit", [event("after", reads=("x",))]),
    ])
    result = solve(ir)
    assert result.iterations > len(result.reachable)
    assert result.in_sets["head"] == frozenset({"initial:x", "increment:x"})
    assert ("initial", "condition", "x") in pairs(result)
    assert ("increment", "condition", "x") in pairs(result)
    assert ("increment", "increment", "x") in pairs(result)  # Prior loop iteration.
    assert ("initial", "increment", "x") in pairs(result)
    assert result.uses_total == result.uses_resolved == 3
    # IN equals the union of final reachable predecessor OUT sets.
    for name in result.reachable:
        expected = set()
        for predecessor in result.reachable:
            if name in ir.blocks[predecessor].successors:
                expected.update(result.out_sets[predecessor])
        assert result.in_sets[name] == frozenset(expected)


def test_same_event_reads_old_definition_before_write():
    result = solve(graph([Block("entry", [
        event("initial", writes=("x",)), event("update", reads=("x",), writes=("x",)),
        event("later", reads=("x",)),
    ])]))
    assert pairs(result) == {("initial", "update", "x"), ("update", "later", "x")}


def test_use_without_reaching_definition_not_invented():
    result = solve(graph([Block("entry", [event("use", reads=("x",))])]))
    assert result.facts == []
    assert result.uses_total == 1 and result.uses_resolved == 0


def test_empty_blocks_propagate_and_empty_entry_does_not_skip_definitions():
    result = solve(graph([
        Block("entry", [], {"empty"}),
        Block("empty", [], {"write"}),
        Block("write", [event("definition", writes=("x",))], {"empty2"}),
        Block("empty2", [], {"read"}),
        Block("read", [event("use", reads=("x",))]),
    ]))
    assert pairs(result) == {("definition", "use", "x")}
    assert result.uses_resolved == 1


def test_iteration_limit_discards_partial_result():
    ir = graph([
        Block("entry", [event("initial", writes=("x",))], {"loop"}),
        Block("loop", [event("update", reads=("x",), writes=("x",))], {"loop"}),
    ])
    with pytest.raises(Unsupported, match="converge"):
        solve(ir, max_iterations=2)
    assert solve(ir).iterations > 2


@pytest.mark.parametrize("corruption", ["symbol_function", "event_function", "unknown_symbol",
                                       "duplicate_event", "missing_successor", "block_key",
                                       "event_file", "missing_entry"])
def test_invalid_or_cross_function_ir_rejected(corruption):
    ir = graph([Block("entry", [event("initial", writes=("x",))])])
    if corruption == "symbol_function":
        ir.symbols["x"] = Symbol("x", "x", "other", Span(FILE, 0, 1, "local"), "local", "uint")
    elif corruption == "event_function":
        ir.blocks["entry"].events = [Event("e", "other", Span(FILE, 0, 1, "statement"), (), ("x",))]
    elif corruption == "unknown_symbol":
        ir.blocks["entry"].events = [event("e", reads=("z",))]
    elif corruption == "duplicate_event":
        ir.blocks["entry"].events.append(event("initial", reads=("x",)))
    elif corruption == "missing_successor":
        ir.blocks["entry"].successors.add("absent")
    elif corruption == "block_key":
        ir.blocks["entry"].id = "renamed"
    elif corruption == "event_file":
        ir.blocks["entry"].events = [Event("e", FUNC, Span("other.sol", 0, 1, "statement"), (), ("x",))]
    else:
        ir.entry = "absent"
    with pytest.raises(Unsupported):
        solve(ir)
