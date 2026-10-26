"""Prompt 6d.2 extraction tests; these tests never execute solc or Slither."""
import copy
from pathlib import Path
import pytest

from scripts.DFG.dfg_v2 import slither_targeted_probes as probes


def node(function, source, writes=(), reads=(), local_writes=(), local_reads=(), phi=False):
    return dict(function=function + "(uint256)", source=source, node_type_name="IFLOOP",
                context_kind="function", span=dict(start=10, end=10 + len(source)),
                ir=[dict(class_name="Binary", text="ordinary operation")],
                ir_ssa=([dict(class_name="Phi", text="x_2 := phi(x_0,x_1)")] if phi else []),
                state_variables_written=[dict(name=x) for x in writes],
                state_variables_read=[dict(name=x) for x in reads],
                local_variables_written=[dict(name=x) for x in local_writes],
                local_variables_read=[dict(name=x) for x in local_reads])


def case(version, name, nodes):
    return dict(compiler_version=version, case=name, status="compiled", nodes=nodes)


def test_fixed_matrix_is_eleven_unique_and_legacy_only_0424():
    matrix = probes.invocation_matrix()
    assert len(matrix) == len(set(matrix)) == 11
    assert matrix.count(("0.4.24", probes.LEGACY_CASE)) == 1
    assert ("0.5.11", probes.LEGACY_CASE) not in matrix
    assert {v for v, _ in matrix} == {"0.4.24", "0.5.11"}


def test_fixtures_stay_in_new_directory_and_have_bound_pragma():
    paths = probes.case_paths()
    assert len(paths) == 6
    assert all(p.parent.name == "p6d2" for p in paths.values())
    assert "var p = m[k]" in paths[probes.LEGACY_CASE].read_text()
    assert "msg.sender.send(1)" in paths["StateExternalLoops.sol"].read_text()
    assert all("pragma solidity >=0.4.24 <=0.5.11;" in p.read_text()
               for name, p in paths.items() if name != probes.LEGACY_CASE)


def test_version_and_send_control_observations_are_not_conflated():
    cases = [
        case("0.4.24", "StateExternalLoops.sol", [
            node("withSend", "balance > x", writes=("balance",), reads=("balance",), phi=True),
            node("withoutSend", "balance > x", reads=("balance",))]),
        case("0.5.11", "StateExternalLoops.sol", [
            node("withSend", "balance > x", reads=("balance",)),
            node("withoutSend", "balance > x", reads=("balance",))]),
    ]
    snapshot = copy.deepcopy(cases)
    result = probes.observations(cases)
    assert result["0.4.24"]["state_loop_send"]["target_state_write"] is True
    assert result["0.4.24"]["state_loop_no_send"]["target_state_write"] is False
    assert result["0.5.11"]["state_loop_send"]["target_state_write"] is False
    assert result["0.4.24"]["state_loop_send"]["phi_in_ssa"]
    assert not result["0.5.11"]["state_loop_send"]["phi_in_ssa"]
    assert cases == snapshot


def test_alias_root_sets_and_local_sets_retained_separately():
    result = probes.observations([
        case("0.4.24", "AliasRebinding.sol", [
            node("rebindAlias", "ref.value = 7", writes=("first", "second"),
                 local_writes=("ref",))])])
    obs = result["0.4.24"]["alias_rebound_write"]
    assert obs["state_variables_written"] == ["first", "second"]
    assert obs["local_variables_written"] == ["ref"]
    assert obs["target_state_write"]
    assert obs["raw_node_pointer"] == "/cases/0/nodes/0"
    assert obs["ordinary_ir"] == ["ordinary operation"]


def test_absent_failed_or_duplicate_expression_never_becomes_observed():
    failed = dict(compiler_version="0.4.24", case="StateExternalLoops.sol", status="failed")
    result = probes.observations([failed])
    assert result["0.4.24"]["state_loop_send"]["status"] == "missing_or_ambiguous"
    duplicates = case("0.4.24", "StateExternalLoops.sol", [
        node("withSend", "balance > x"), node("withSend", "balance > x")])
    assert probes.observations([duplicates])["0.4.24"]["state_loop_send"]["matched_nodes"] == 2


def test_same_text_in_different_function_does_not_match():
    result = probes.observations([
        case("0.4.24", "StateExternalLoops.sol", [node("unrelated", "balance > x")])])
    assert result["0.4.24"]["state_loop_send"]["matched_nodes"] == 0


def test_duplicate_case_version_rejected():
    item = case("0.4.24", "AliasRebinding.sol", [])
    with pytest.raises(ValueError, match="Duplicate"):
        probes.observations([item, item])


def test_existing_output_rejected_before_any_compiler_access(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No compiler or source work allowed before overwrite guard")
    monkeypatch.setattr(probes, "case_paths", forbidden)
    with pytest.raises(ValueError, match="overwrite"):
        probes.run(tmp_path, tmp_path / "not-a-manifest.json")


def test_legacy_incompatible_version_is_explicitly_not_applicable():
    result = probes.observations([])
    assert result["0.5.11"]["legacy_storage_member_write"]["status"] == "not_applicable"
    assert result["0.4.24"]["legacy_storage_member_write"]["status"] == "missing_or_ambiguous"


def test_function_declaration_metadata_is_read_only_and_deduplicated():
    from types import SimpleNamespace
    param = SimpleNamespace(name="input", source_mapping=dict(start=5, length=5))
    returned = SimpleNamespace(name="named", source_mapping=dict(start=20, length=5))
    function = SimpleNamespace(name="declarations", full_name="declarations(uint256)",
                               source_mapping=dict(start=1, length=90),
                               parameters=[param], returns=[returned],
                               variables=[param, returned])
    contract = SimpleNamespace(name="Fake", functions=[function], modifiers=[function])
    analysis = SimpleNamespace(contracts=[contract])
    result = probes.collect_functions(analysis)
    assert len(result) == 1
    assert result[0]["parameters"][0]["name"] == "input"
    assert result[0]["returns"][0]["name"] == "named"
    assert result[0]["parameters"][0]["source_mapping"] == dict(start=5, length=5)
    assert function.parameters == [param]


def test_retry_fixture_changes_only_reserved_function_identifier():
    from scripts.DFG.dfg_v2 import slither_composite_retry as retry
    directory = Path(retry.__file__).parent / "convention_cases" / "p6d2"
    original = (directory / "CompositeStateWrites.sol").read_bytes()
    fixed = (directory / "CompositeStateWritesRetry.sol").read_bytes()
    assert fixed == original.replace(b"function indexed(", b"function arrayWrite(")
    assert original != fixed


def test_retry_observes_actual_renamed_identity_not_fabricated_name():
    from scripts.DFG.dfg_v2 import slither_composite_retry as retry
    result = retry.observations([
        case("0.4.24", "CompositeStateWrites.sol",
             [node("arrayWrite", "arr[i].f = v", writes=("arr",), reads=("arr",))])])
    obs = result["0.4.24"]["array_member_write"]
    assert obs["function"] == "arrayWrite"
    assert obs["target_state_write"]
    assert obs["target_state_read"]


def test_retry_rejects_existing_output_before_reading_inputs(tmp_path):
    from scripts.DFG.dfg_v2 import slither_composite_retry as retry
    with pytest.raises(ValueError, match="overwrite"):
        retry.run(tmp_path, tmp_path / "no-trusted", tmp_path / "no-report")


def test_future_default_selects_corrected_fixture_and_actual_arraywrite_identity():
    paths = probes.case_paths()
    path = paths["CompositeStateWrites.sol"]
    assert path.name == "CompositeStateWritesRetry.sol"
    assert "function arrayWrite(" in path.read_text()
    assert "function indexed(" not in path.read_text()
    selector = [c for c in probes.CHECKS if c[0] == "array_member_write"]
    assert len(selector) == 1
    assert selector[0][2] == "arrayWrite"
