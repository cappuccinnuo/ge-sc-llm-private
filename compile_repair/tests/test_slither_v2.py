"""CP0.1: mapping APIs, declaration coverage, occurrence identity and profiles."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as Item

import pytest

from compile_repair.core.model import Compiler
from compile_repair.toolchain.solc import compile_file
from compile_repair.toolchain.slither import (
    check_profile, read_mapping, node_facts, contract_coverage, run_slither)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
SOURCE = str((FIXTURES / "counter.sol").resolve())


def fake_function(irs, mapping=None, name="f()"):
    mapping = {"filename_absolute": SOURCE, "start": 10, "length": 7} if mapping is None else mapping
    return Item(full_name=name, nodes=[Item(type="RETURN", source_mapping=mapping, irs=[ir]) for ir in irs])


def fake_slither(functions=(), top_level=()):
    return Item(contracts=[Item(name="C", functions_and_modifiers_declared=functions)],
                compilation_units=[Item(functions_top_level=top_level)])


@pytest.mark.parametrize("object_style", [False, True])
def test_mapping_apis_have_equal_node_facts(object_style):
    mapping = (Item(filename=Item(absolute=SOURCE), start=10, length=7) if object_style else
               {"filename_absolute": SOURCE, "start": 10, "length": 7})
    assert read_mapping(mapping) == {"filename": SOURCE, "start": 10, "length": 7}
    result = node_facts(fake_slither([fake_function(["return x"], mapping)]), [SOURCE])
    assert result["mapping_complete"]
    assert result["nodes"] == [{"key5": ["C", "f()", "RETURN", 10, 1],
                                "ir": ["return x"], "length": 7, "declaration_kind": "function"}]


@pytest.mark.parametrize("mapping", [None, 7, [], Item(start=0),
    Item(filename="wrong API", start=0, length=1)])
def test_unreadable_mapping_is_an_explicit_error(mapping):
    function = fake_function(["return"])
    function.nodes[0].source_mapping = mapping
    with pytest.raises(ValueError, match="source_mapping"):
        node_facts(fake_slither([function]), [SOURCE])


def test_object_mapping_missing_filename_or_start_fails_d3():
    for mapping, key in [(Item(filename=None, start=0, length=1), "missing_filename"),
                         (Item(filename=Item(absolute=SOURCE), start=None, length=1), "missing_start")]:
        result = node_facts(fake_slither([fake_function(["x"], mapping)]), [SOURCE])
        assert not result["mapping_complete"] and result["counts"][key] == 1


def test_ordinal_assigned_before_sort_and_reset_per_function():
    result = node_facts(fake_slither([fake_function(["z", "a"]), fake_function(["b"], name="g()")]), [SOURCE])
    by_ir = {r["ir"][0]: r["key5"] for r in result["nodes"]}
    assert by_ir["z"][-1] == 1 and by_ir["a"][-1] == 2 and by_ir["b"][-1] == 1
    assert result["counts"]["nodes"] == 3
    assert list(result["duplicate_key4"].values()) == [2]


def test_free_function_nodes_participate_in_d3():
    bad = fake_function(["free"], mapping={"start": 0})
    result = node_facts(fake_slither([], [bad]), [SOURCE])
    assert not result["mapping_complete"] and result["counts"]["top_level_functions"] == 1
    assert result["nodes"][0]["key5"][0] == "<top-level>"
    assert result["nodes"][0]["declaration_kind"] == "top_level_function"


def coverage_fixture(names, actual, legacy=False):
    tree = ({"name": "SourceUnit", "children": [
                {"name": "ContractDefinition", "attributes": {"name": name}} for name in names]}
            if legacy else {"nodeType": "SourceUnit", "nodes": [
                {"nodeType": "ContractDefinition", "name": name} for name in names]})
    contracts = [Item(name=name, source_mapping={"filename_absolute": SOURCE}) for name in actual]
    return Item(contracts=contracts, crytic_compile=Item(
        compilation_units={"unit": Item(asts={SOURCE: tree})}))


@pytest.mark.parametrize("legacy", [False, True])
def test_contract_coverage_retains_multiplicity_and_rejects_omissions(legacy):
    model = coverage_fixture(["C", "C", "Interface", "Library"], ["C", "Interface", "Library"], legacy)
    result = contract_coverage(model, [SOURCE])
    assert not result["complete"] and result["missing"] == {"C": 1}
    model.contracts.append(Item(name="C", source_mapping=Item(filename=Item(absolute=SOURCE), start=0, length=1)))
    assert contract_coverage(model, [SOURCE])["complete"]
    model.contracts.append(Item(name="Extra", source_mapping={"filename_absolute": SOURCE}))
    assert contract_coverage(model, [SOURCE])["unexpected"] == {"Extra": 1}


@pytest.mark.parametrize("asts", [{}, {SOURCE: {}}, {SOURCE: {"nodeType": "SourceUnit"}}])
def test_absent_or_malformed_ast_cannot_pass_vacuously(asts):
    model = Item(contracts=[], crytic_compile=Item(compilation_units={"unit": Item(asts=asts)}))
    with pytest.raises(ValueError, match="AST"):
        contract_coverage(model, [SOURCE])


def test_ast_and_contracts_outside_inputs_do_not_change_coverage():
    model = coverage_fixture(["C"], ["C"])
    model.crytic_compile.compilation_units["unit"].asts["/foreign.sol"] = {}
    model.contracts.append(Item(name="Foreign", source_mapping={"filename_absolute": "/foreign.sol"}))
    assert contract_coverage(model, [SOURCE])["complete"]


@pytest.mark.parametrize("profile,installed", [("production", ("0.8.0", "0.2.4")),
    ("regression_6c", ("0.8.3", "0.2.4")), ("regression_6c", ("0.8.0", "0.3.11"))])
def test_unconfigured_versions_are_rejected(profile, installed):
    with pytest.raises(ValueError, match="profile"):
        check_profile(profile, installed)


def installed_probe(version, fixture, tmp_path):
    # Use sealed CP0 identities, never trust-on-first-use of the local binary.
    recon_path = ROOT / "artifacts/cp0_v2/recon.json"
    assert hashlib.sha256(recon_path.read_bytes()).hexdigest() == "bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6"
    compiler = Compiler(**json.loads(recon_path.read_text())["compilers"][version])
    if not Path(compiler.path).is_file():
        pytest.skip("Previously trusted compiler unavailable: " + version)
    compilation = compile_file(FIXTURES / fixture, compiler)
    assert compilation.returncode == 0
    result = run_slither(compilation, cp0_projection=fixture.startswith("compat_"))
    (tmp_path / (fixture + ".json")).write_text(json.dumps({"solc": asdict(compilation), "slither": result}, indent=2))
    assert result["constructed"] and result["d3_a"] and result["d3_b"] and result["d3"]
    assert result["profile"] == "regression_6c"
    return result


@pytest.mark.parametrize("version,fixture,ast_format", [
    ("0.4.12", "compat_04.sol", "legacy"), ("0.8.0", "compat_08.sol", "compact")])
def test_real_ast_formats_and_cp0_projection(version, fixture, ast_format, tmp_path):
    result = installed_probe(version, fixture, tmp_path)
    assert {a["format"] for a in result["contract_coverage"]["asts"]} == {ast_format}
    expected = []
    with (ROOT / "artifacts/cp0_v2/invocations.jsonl").open() as stream:
        for line in stream:
            item = json.loads(line)
            if (item["kind"] == "slither" and item["version"] == version and
                    item["source_sha256"] == result["source_sha256"]):
                expected.append(item["node_facts_sha256"])
    assert expected and set(expected) == {result["cp0_projection_sha256"]}


def test_real_ternary_duplicate_return_ordinals(tmp_path):
    result = installed_probe("0.4.13", "ternary.sol", tmp_path)
    returns = [r for r in result["nodes"] if r["key5"][2] == "RETURN"]
    assert len(returns) == 2 and returns[0]["key5"][:4] == returns[1]["key5"][:4]
    assert {r["key5"][-1] for r in returns} == {1, 2}


def test_real_free_function_in_compilation_units(tmp_path):
    result = installed_probe("0.7.6", "free_function.sol", tmp_path)
    assert result["counts"]["top_level_functions"] == 1
    free = [r for r in result["nodes"] if r["key5"][0] == "<top-level>"]
    assert free and {r["key5"][1] for r in free} == {"increment(uint256)"}
    assert all(r["declaration_kind"] == "top_level_function" for r in free)
