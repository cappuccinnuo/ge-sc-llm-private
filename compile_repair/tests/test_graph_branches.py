"""CP2.1 branch occurrences: merged targets, order and malformed CFGs."""
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace as Item

import pytest

from compile_repair.tests.test_production import production_required, trusted_compilers
from compile_repair.toolchain.slither import graph_facts

FIXTURE = Path(__file__).parent / "fixtures/graph_branches.sol"


def model_for(kind):
    def node(start, node_kind):
        return Item(type=Item(name=node_kind),
                    source_mapping={"start": start, "length": 1},
                    irs=[], sons=[], son_true=None, son_false=None)
    branch, first, second = node(0, kind), node(1, "ENDIF"), node(2, "ENDIF")
    branch.son_true, branch.son_false = first, second
    branch.sons = [second, first]
    function = Item(full_name="f()", nodes=[branch, first, second])
    model = Item(contracts=[Item(name="C", functions_and_modifiers_declared=[function])],
                 compilation_units=[])
    return model, branch, first, second


@pytest.mark.parametrize("kind", ["IF", "IFLOOP"])
@pytest.mark.parametrize("shared_target", [False, True])
def test_branch_occurrences_preserve_order(kind, shared_target):
    model, branch, first, second = model_for(kind)
    if shared_target:
        branch.son_false = first
        branch.sons = [first, first]
    edges = graph_facts(model)["cfg_edges"]
    assert Counter(e["kind"] for e in edges) == {"true": 1, "false": 1}
    assert [e["kind"] for e in edges] == (
        ["true", "false"] if shared_target else ["false", "true"])
    assert [e["target"][3] for e in edges] == ([1, 1] if shared_target else [2, 1])


@pytest.mark.parametrize("kind", ["IF", "IFLOOP"])
@pytest.mark.parametrize("broken", ["empty", "missing", "duplicate_true", "extra",
                                   "missing_pointer", "foreign"])
def test_invalid_conditional_graph_fails(kind, broken):
    model, branch, first, second = model_for(kind)
    if broken == "empty":
        branch.sons = []
    elif broken == "missing":
        branch.sons = [first]
    elif broken == "duplicate_true":
        branch.sons = [first, first]
    elif broken == "extra":
        branch.sons.append(first)
    elif broken == "missing_pointer":
        branch.son_false = None
    else:
        branch.sons.append(Item())
    with pytest.raises(ValueError, match="outside" if broken == "foreign" else "one true and one false"):
        graph_facts(model)


def test_nonconditional_sons_are_next_even_with_branch_attributes():
    model, branch, first, second = model_for("EXPRESSION")
    assert [e["kind"] for e in graph_facts(model)["cfg_edges"]] == ["next", "next"]


def test_real_empty_branches_and_loop_edges(tmp_path):
    production_required()
    from slither import Slither
    compiler = trusted_compilers()["0.5.0"]
    model = Slither(str(FIXTURE.resolve()), solc=compiler.path, solc_disable_warnings=True)
    graph = graph_facts(model)
    branches = [n for n in graph["nodes"] if n["node_type"] in ("IF", "IFLOOP")]
    assert Counter(n["node_type"] for n in branches) == {"IF": 4, "IFLOOP": 2}
    functions = {f.full_name: f for c in model.contracts for f in c.functions_and_modifiers_declared}
    for branch in branches:
        key = branch["key5"]
        edges = [e for e in graph["cfg_edges"] if e["source"] == key]
        assert Counter(e["kind"] for e in edges) == {"true": 1, "false": 1}
        original = next(n for n in functions[key[1]].nodes
                        if n.type.name == key[2] and n.source_mapping.start == key[3])
        assert [e["target"][3] for e in edges] == [n.source_mapping.start for n in original.sons]
        targets = {e["kind"]: e["target"][3] for e in edges}
        assert targets == {"true": original.son_true.source_mapping.start,
                           "false": original.son_false.source_mapping.start}
        if key[1] in ("emptyIf(address)", "bothEmpty(bool)"):
            assert edges[0]["target"] == edges[1]["target"]
            assert [e["kind"] for e in edges] == ["true", "false"]
    (tmp_path / "branches.json").write_text(json.dumps(graph, sort_keys=True), encoding="utf8")
