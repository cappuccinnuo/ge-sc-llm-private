"""Independent v2 transfer checks and exact parity with frozen scalar RD.

Hand-authored IR tests are algorithm tests, not Solidity compilation claims.
Parser tests use the installed Tree-sitter grammar; solc is not invoked.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.l1_models import V2Event
from scripts.DFG.dfg_v2.l1_rd import SOURCE_SHA256, solve_v2
from scripts.DFG.frontend import parse_source
from scripts.DFG.models import Block, Event, FunctionIR, Span, Symbol, Unsupported
from scripts.DFG.reaching_definitions import solve
from scripts.DFG.semantic_cfg import analyze


FILE, FUNCTION = "rd.sol", "rd.sol:0"


def _event(name, reads=(), writes=(), weak_writes=()):
    return V2Event(name, FUNCTION, Span(FILE, 1, 2, "statement"),
                   tuple(reads), tuple(writes), tuple(weak_writes))


def _ir(blocks, names=("x", "y"), entry="entry"):
    return FunctionIR(
        FUNCTION, FILE, entry, {b.id: b for b in blocks},
        {n: Symbol(n, n, FUNCTION, Span(FILE, 0, 1, "local"), "local", "S")
         for n in names})


def _pairs(result):
    return {(f.definition.event, f.use.id, f.symbol) for f in result.facts}


def _assert_fixed_point(ir, result):
    for identifier in result.reachable:
        incoming = set()
        for predecessor in result.reachable:
            if identifier in ir.blocks[predecessor].successors:
                incoming.update(result.out_sets[predecessor])
        assert result.in_sets[identifier] == frozenset(incoming)


def test_source_digest_tracks_frozen_solver():
    source = Path(__file__).resolve().parents[2] / "reaching_definitions.py"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256


def test_weak_write_keeps_original_value_and_records_read_before_write():
    result = solve_v2(_ir([Block("entry", [
        _event("decl", writes=("x",)),
        _event("member", reads=("x",), weak_writes=("x",)),
        _event("use", reads=("x",)),
    ])]))
    assert _pairs(result) == {
        ("decl", "member", "x"), ("decl", "use", "x"), ("member", "use", "x")}
    assert result.out_sets["entry"] == frozenset({"decl:x", "member:x"})
    assert result.uses_total == result.uses_resolved == 2
    assert ("member", "member", "x") not in _pairs(result)


def test_whole_assignment_kills_old_strong_and_weak_definitions():
    result = solve_v2(_ir([
        Block("entry", [_event("decl", writes=("x",))], {"body"}),
        Block("body", [
            _event("member", reads=("x",), weak_writes=("x",)),
            _event("replace", writes=("x",)),
            _event("use", reads=("x",)),
            _event("member2", weak_writes=("x",)),
        ], {"after"}),
        Block("after", [_event("later", reads=("x",))]),
    ]))
    assert _pairs(result) == {
        ("decl", "member", "x"), ("replace", "use", "x"),
        ("replace", "later", "x"), ("member2", "later", "x")}
    assert result.out_sets["body"] == frozenset({"replace:x", "member2:x"})


def test_branch_union_keeps_possible_weak_and_strong_definitions():
    ir = _ir([
        Block("entry", [_event("decl", writes=("x",))], {"left", "right"}),
        Block("left", [_event("left", weak_writes=("x",))], {"join"}),
        Block("right", [_event("right", writes=("x",))], {"join"}),
        Block("join", [_event("use", reads=("x",))]),
    ])
    result = solve_v2(ir)
    assert _pairs(result) == {
        ("decl", "use", "x"), ("left", "use", "x"), ("right", "use", "x")}
    assert result.in_sets["join"] == frozenset({"decl:x", "left:x", "right:x"})
    _assert_fixed_point(ir, result)


def test_loop_weak_write_reaches_fixed_point_and_prior_iteration():
    ir = _ir([
        Block("entry", [_event("decl", writes=("x",))], {"head"}),
        Block("head", [_event("condition", reads=("x",))], {"body", "exit"}),
        Block("body", [_event("member", reads=("x",), weak_writes=("x",))], {"head"}),
        Block("exit", [_event("after", reads=("x",))]),
    ])
    result = solve_v2(ir)
    assert result.iterations > len(result.reachable)
    assert result.in_sets["head"] == frozenset({"decl:x", "member:x"})
    assert _pairs(result) == {
        (d, u, "x") for d in ("decl", "member")
        for u in ("condition", "member", "after")}
    assert result.uses_total == result.uses_resolved == 3
    _assert_fixed_point(ir, result)


def test_weak_write_does_not_invent_transitive_symbol_dependencies():
    result = solve_v2(_ir([Block("entry", [
        _event("xdecl", writes=("x",)), _event("xmember", weak_writes=("x",)),
        _event("ydecl", reads=("x",), writes=("y",)),
        _event("usey", reads=("y",)),
    ])]))
    assert _pairs(result) == {
        ("xdecl", "ydecl", "x"), ("xmember", "ydecl", "x"), ("ydecl", "usey", "y")}
    assert not any(f.definition.event.startswith("x") and f.use.id == "usey"
                   for f in result.facts)


def test_unreachable_weak_definition_cannot_leak_into_live_join():
    ir = _ir([
        Block("entry", [_event("live", writes=("x",))], {"join"}),
        Block("dead", [_event("dead", weak_writes=("x",)),
                       _event("deadread", reads=("x",))], {"join"}),
        Block("join", [_event("use", reads=("x",))]),
    ])
    result = solve_v2(ir)
    assert result.reachable == {"entry", "join"}
    assert _pairs(result) == {("live", "use", "x")}
    assert "dead:x" in result.definitions
    assert result.in_sets["dead"] == result.out_sets["dead"] == frozenset()
    assert result.uses_total == 1


def test_declaration_identity_prevents_same_name_collision():
    ir = _ir([Block("entry", [
        _event("outer", writes=("x",)), _event("inner", weak_writes=("y",)),
        _event("read_outer", reads=("x",)),
    ])])
    ir.symbols["y"] = replace(ir.symbols["y"], name="x")
    assert _pairs(solve_v2(ir)) == {("outer", "read_outer", "x")}


@pytest.mark.parametrize("corruption", [
    "unknown_weak", "overlap", "duplicate_event", "event_file", "event_function",
    "symbol_function", "symbol_file", "symbol_key", "missing_successor",
    "block_key", "missing_entry",
])
def test_v2_ir_validation_rejects_invalid_inputs(corruption):
    ir = _ir([Block("entry", [_event("write", weak_writes=("x",))])])
    if corruption == "unknown_weak":
        ir.blocks["entry"].events = [_event("write", weak_writes=("missing",))]
    elif corruption == "overlap":
        ir.blocks["entry"].events = [_event("write", writes=("x",), weak_writes=("x",))]
    elif corruption == "duplicate_event":
        ir.blocks["entry"].events.append(_event("write", reads=("x",)))
    elif corruption == "event_file":
        ir.blocks["entry"].events = [replace(
            ir.blocks["entry"].events[0], anchor=Span("other.sol", 1, 2, "statement"))]
    elif corruption == "event_function":
        ir.blocks["entry"].events = [replace(ir.blocks["entry"].events[0], function="other")]
    elif corruption == "symbol_function":
        ir.symbols["x"] = replace(ir.symbols["x"], function="other")
    elif corruption == "symbol_file":
        ir.symbols["x"] = replace(ir.symbols["x"], declaration=Span("other.sol", 0, 1, "local"))
    elif corruption == "symbol_key":
        ir.symbols["x"] = replace(ir.symbols["x"], id="other")
    elif corruption == "missing_successor":
        ir.blocks["entry"].successors.add("missing")
    elif corruption == "block_key":
        ir.blocks["entry"].id = "renamed"
    else:
        ir.entry = "missing"
    with pytest.raises(Unsupported):
        solve_v2(ir)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_iteration_limit_is_rejected(limit):
    with pytest.raises(ValueError):
        solve_v2(_ir([Block("entry")]), limit)


def test_nonconverged_result_is_not_published_and_ir_is_not_mutated():
    ir = _ir([
        Block("entry", [_event("decl", writes=("x",))], {"loop"}),
        Block("loop", [_event("update", reads=("x",), weak_writes=("x",))], {"loop"}),
    ])
    before = deepcopy(ir)
    with pytest.raises(Unsupported, match="converge"):
        solve_v2(ir, max_iterations=2)
    assert ir == before
    assert solve_v2(ir).iterations > 2


PARSER_SOURCES = [
    # Real original regression fixture, including conditional union.
    (Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "minimal.sol").read_text(),
    """pragma solidity ^0.5.17;
    contract C {
      function f(uint x, bool c) public pure returns (uint) {
        uint y = x;
        while (c) { y += x; if (y > 10) { break; } }
        return y;
        y = 999;
      }
    }""",
    """pragma solidity ^0.5.17;
    contract C {
      function f(uint x, uint n) public pure returns (uint) {
        for (uint i = 0; i < n; i++) { x += i; }
        return x;
      }
    }""",
]


@pytest.mark.parametrize("source", PARSER_SOURCES)
@pytest.mark.parametrize("use_v2_events", [False, True])
def test_weak_empty_real_parser_ir_is_exactly_equivalent(source, use_v2_events):
    analysis = analyze(parse_source(source, "scalar_parity.sol"))
    assert analysis.functions
    assert not any(d["kind"] == "function_fallback" for d in analysis.diagnostics)
    for ir in analysis.functions:
        if use_v2_events:
            for block in ir.blocks.values():
                block.events = [V2Event(e.id, e.function, e.anchor, e.reads, e.writes,
                                        (), e.kind) for e in block.events]
        before = deepcopy(ir)
        reference = solve(ir)
        actual = solve_v2(ir)
        # Full dataclass equality includes facts/order, IN/OUT, definitions,
        # reachable blocks, iterations, and both use-coverage counters.
        assert actual == reference
        assert actual.facts == reference.facts
        assert actual.in_sets == reference.in_sets
        assert actual.out_sets == reference.out_sets
        assert actual.iterations == reference.iterations
        assert ir == before
