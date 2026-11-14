"""CP2 ordered graph schema, exact call kinds and storage determinism."""
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace as Item

import pytest

from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.tests.test_pipeline import unit_for
from compile_repair.tests.test_production import production_required, trusted_compilers
from compile_repair.toolchain.solc import compile_file
from compile_repair.toolchain.slither import graph_facts, node_facts, _graph_text, run_slither

FIXTURE = Path(__file__).parent / "fixtures/graph_calls.sol"


def test_graph_keeps_sons_order_and_duplicate_node_occurrences():
    def node(start, kind="EXPRESSION"):
        return Item(type=Item(name=kind), source_mapping={"start": start, "length": 1},
                    irs=[], sons=[], son_true=None, son_false=None)
    entry, branch, first, second = node(0, "ENTRYPOINT"), node(1, "IF"), node(2), node(2)
    entry.sons = [branch]
    branch.sons, branch.son_true, branch.son_false = [second, first], first, second
    fn = Item(full_name="f()", nodes=[entry, branch, first, second])
    model = Item(contracts=[Item(name="C", functions_and_modifiers_declared=[fn])],
                 compilation_units=[])
    graph = graph_facts(model)
    assert [n["key5"][-1] for n in graph["nodes"]] == [1, 1, 1, 2]
    assert [e["kind"] for e in graph["cfg_edges"]] == ["next", "false", "true"]
    assert [e["target"][-1] for e in graph["cfg_edges"]] == [1, 2, 1]
    branch.sons.append(node(9))
    with pytest.raises(ValueError, match="outside"):
        graph_facts(model)


def test_graph_text_normalizes_only_python_objects_and_rejects_residual():
    assert _graph_text("<pkg.Type object at 0xABC> 0x123") == "<pkg.Type> 0x123"
    with pytest.raises(ValueError, match="Residual"):
        _graph_text("malformed object at 0x123")


def test_real_all_call_kinds_and_reference_order(tmp_path):
    production_required()
    from slither import Slither
    from slither.slithir.operations import Call
    from slither.slithir.operations.library_call import LibraryCall
    from slither.slithir.operations.high_level_call import HighLevelCall
    compiler = trusted_compilers()["0.8.0"]
    compiled = compile_file(FIXTURE, compiler)
    assert compiled.returncode == 0
    model = Slither(str(FIXTURE.resolve()), solc=compiler.path, solc_disable_warnings=True)
    graph = graph_facts(model)
    assert issubclass(LibraryCall, HighLevelCall)
    kinds = {c["kind"] for c in graph["calls"]}
    assert kinds == {"internal", "high-level", "low-level", "library", "InternalDynamicCall",
                     "Send", "Transfer", "SolidityCall", "EventCall", "NewContract"}
    assert all(c["kind"] == "library" for c in graph["calls"] if c["operation"] == "LibraryCall")
    declared = [f for c in model.contracts for f in c.functions_and_modifiers_declared]
    declared += [f for u in model.compilation_units for f in u.functions_top_level]
    expected_calls = [(type(ir).__name__, i) for f in declared for n in f.nodes
                      for i, ir in enumerate(n.irs) if isinstance(ir, Call)]
    assert [(c["operation"], c["ir_index"]) for c in graph["calls"]] == expected_calls
    assert len(graph["cfg_edges"]) == sum(len(n.sons) for f in declared for n in f.nodes)
    assert {e["kind"] for e in graph["cfg_edges"]} == {"true", "false", "next"}
    for c in graph["calls"]:
        if c["kind"] in ("internal", "high-level", "library"):
            assert c["callee"]["function"] and c["callee"]["contract"]
        else:
            assert c["callee"]["text"]
    assert any(c["callee"].get("contract") == "<top-level>" for c in graph["calls"])
    facts = node_facts(model, [FIXTURE])
    projection = [{k:v for k,v in n.items() if k != "node_type"} for n in graph["nodes"]]
    assert sorted(projection, key=lambda n: json.dumps(n, sort_keys=True)) == facts["nodes"]
    keys = {tuple(n["key5"]) for n in graph["nodes"]}
    assert len(keys) == len(graph["nodes"])
    assert all(tuple(e["source"]) in keys and tuple(e["target"]) in keys for e in graph["cfg_edges"])
    assert any(d["declaration_kind"] == "modifier" for d in graph["declarations"])
    assert any(d["declaration_kind"] == "top_level_function" for d in graph["declarations"])
    (tmp_path / "graph_probe.json").write_text(json.dumps({"solc":compiled.command,"graph":graph},sort_keys=True),encoding="utf8")


def test_real_graph_storage_is_path_independent_and_marked(tmp_path):
    production_required()
    compilers = {"0.8.0": trusted_compilers()["0.8.0"]}
    raw = FIXTURE.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    payloads = []
    for name in ("one", "different_path"):
        store = ArtifactStore(tmp_path / name)
        with store.journal("invocations.jsonl") as journal:
            record = repair_unit(unit_for(raw), compilers, store, journal)
        assert record.status == "success"
        path = store.path / "units/test_input/graph.json"
        graph = json.loads(path.read_text())
        assert all(n["provenance"] == "original" for n in graph["nodes"])
        assert all(n["node_type"] == n["key5"][2] for n in graph["nodes"])
        assert str(tmp_path) not in path.read_text() and " object at 0x" not in path.read_text()
        assert record.attempts[-1]["slither"]["graph_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        payloads.append(path.read_bytes())
    assert payloads[0] == payloads[1]
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == before


def test_acceptance_callback_stops_and_seals_after_flushed_record(tmp_path):
    production_required()
    from compile_repair.cli import main
    raw = b"pragma solidity 0.8.0; contract Empty {}"
    paths = [tmp_path / "first.sol", tmp_path / "second.sol"]
    for p in paths:
        p.write_bytes(raw)
    seen = []
    def check(record, output):
        seen.append(record.unit_id)
        assert len((output / "manifest.jsonl").read_text().splitlines()) == 1
        raise ValueError("Injected acceptance discrepancy")
    output = tmp_path / "stopped"
    assert main(["repair"] + [str(p) for p in paths] + ["--output", str(output)],
                result_check=check) == 2
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "stopped" and seen == ["input_0001"]
    assert not (output / "units/input_0002").exists()
    seal = json.loads((output / "seal.json").read_text())
    assert all(hashlib.sha256((output / p).read_bytes()).hexdigest() == h
               for p,h in seal["files"].items())
