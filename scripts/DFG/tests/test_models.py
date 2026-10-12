from scripts.DFG.models import Span, Event, Block, FunctionIR, DDGConfig
import pytest

def test_immutable_identity_and_config():
    assert Span("a.sol", 1, 2, "expression") != Span("b.sol", 1, 2, "expression")
    assert hash(Span("a.sol", 1, 2, "expression"))
    assert not DDGConfig().use_ddg
    with pytest.raises(ValueError): Span("x", 3, 2, "x")
    with pytest.raises(ValueError): DDGConfig(use_ddg=1)

def test_mutable_containers_not_shared():
    a, b = Block("a"), Block("b")
    a.successors.add("b")
    assert not b.successors
    e = Event("e", "f", Span("x", 0, 1, "statement"), ("s",), ("s",))
    assert e.reads == e.writes == ("s",)
