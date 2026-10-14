"""Focused post-implementation review: nested event args must be read once."""
from dataclasses import replace
import pytest
from scripts.DFG.models import Unsupported
from scripts.DFG.state.tests.test_semantics import run,events
from scripts.DFG.state.reaching_definitions import solve

def test_emit_nested_call_evaluates_argument_once_before_havoc():
    _,r=run("x=1;emit E(foo(x));",extra="event E(uint a);function foo(uint a) internal returns(uint){return a;}")
    assert r.status=="supported_subset"
    assert len(events(r,"READ"))==1
    assert len(events(r,"HAVOC"))==1
    assert not r.unknown_reads
    assert len(r.facts)==1

def test_unknown_event_kind_cannot_silently_enter_semantic_cfg():
    _,r=run("x=1;require(x>0);")
    bid=next(b for b,es in r.ir.events.items() if es)
    r.ir.events[bid][0]=replace(r.ir.events[bid][0],kind="UNVERIFIED")
    with pytest.raises(Unsupported,match="kind"):solve(r.ir)
