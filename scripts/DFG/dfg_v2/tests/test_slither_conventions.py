"""Synthetic unit tests; no compiler/Slither execution in this test module."""
from types import SimpleNamespace

import pytest

from scripts.DFG.dfg_v2 import slither_conventions as sc


def node(source, function="f()", reads=(), writes=(), state_reads=(), state_writes=(),
         context="function", node_type="NodeType.EXPRESSION"):
    value = dict(node_id=1, node_type=node_type, span=dict(start=0, end=len(source)),
                 source=source, function=function, context_kind=context, ir_ssa=[])
    for attr, names in zip(sc.SET_ATTRIBUTES, (reads, writes, state_reads, state_writes)):
        value[attr] = [dict(name=name) for name in names]
    return value


def cases(**entries):
    return [dict(case=name + ".sol", status="compiled", nodes=nodes)
            for name, nodes in entries.items()]


def test_exactly_six_fixed_sources_no_import_and_exact_version():
    paths = sc.case_paths()
    assert len(paths) == len(sc.CASE_FILES) == 6
    assert len(set(p.name for p in paths)) == 6
    assert all(p.parent.name == "convention_cases" for p in paths)
    assert all(p.read_text().startswith("pragma solidity 0.5.11;") for p in paths)


def test_existing_output_rejected_before_compiler_discovery(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "inspect_environment", lambda: pytest.fail("not reached"))
    with pytest.raises(ValueError, match="overwrite"):
        sc.run(tmp_path, tmp_path / "missing.json")


def test_no_authorized_compiler_stops_before_output_or_invocation(tmp_path, monkeypatch):
    trust = tmp_path / "trusted.json"
    trust.write_text('{"compilers": {}}')
    monkeypatch.setattr(sc, "inspect_environment", lambda: {"skip_reasons": []})
    out = tmp_path / "not_created"
    with pytest.raises(ValueError, match="not_explicitly_authorized"):
        sc.run(out, trust)
    assert not out.exists()


@pytest.mark.parametrize("reads,expected", [(("m",), True), ((), False)])
def test_mapping_read_and_write_must_both_exist(reads, expected):
    report = sc.observations(cases(MappingWrites=[
        node("m[k] = v", state_reads=reads, state_writes=("m",))]))
    assert report["mapping_write_base_read"]["confirmed"] is expected
    assert not report["mapping_delete_base_read"]["confirmed"]


def test_absent_cases_do_not_confirm_conventions():
    assert all(not c["confirmed"] for c in sc.observations([]).values())


def test_loop_observation_keeps_actual_false_instead_of_assuming_phi_write():
    report = sc.observations(cases(Loops=[
        node("i < n", "whileLocal(uint256)", reads=("i", "n"), writes=()),
        node("i < n", "forLocal(uint256)", writes=("i",)),
        node("s < n", "whileState(uint256)", state_writes=("s",))]))
    loop = report["loop_header_merge_write"]
    assert not loop["confirmed"]
    assert [n["written"] for n in loop["observations"]] == [False, True, True]


@pytest.mark.parametrize("reads,expected", [((), True), (("a",), False)])
def test_memory_aggregate_requires_write_only(reads, expected):
    report = sc.observations(cases(MemoryArray=[
        node("a[i] = v", reads=reads, writes=("a",))]))
    assert report["aggregate_base_use"]["confirmed"] is expected


def test_repeated_read_is_unit_observation_not_general_correctness():
    report = sc.observations(cases(RepeatedReads=[
        node("return m[k] + m[k]", state_reads=("m",)),
        node("return s + s", state_reads=("s",))]))
    assert report["repeated_state_read"]["confirmed"]
    assert "comparator artifact" in report["repeated_state_read"]["limitation"]


def test_bare_invoked_counterexample_is_not_counted_as_bare():
    report = sc.observations(cases(BareExpressions=[
        node("x", "bare(uint256)"),
        node("to.call.value(amount)", "unused(address,uint256)", reads=("to",)),
        node('(bool ok,) = to.call.value(amount)("")', "called(address,uint256)",
             reads=("to", "amount"))]))
    bare = report["bare_expression_use"]
    assert bare["confirmed"]
    assert len(bare["observations"]) == 2
    assert len(bare["invoked_call_counterexample"]) == 1
    assert "amount" in bare["invoked_call_counterexample"][0]["local_variables_read"]


def test_modifier_context_is_recorded_not_inferred_from_name():
    report = sc.observations(cases(ParameterizedModifier=[
        node("require(n > threshold)", "above(uint256)", context="function")]))
    assert not report["modifier_body_unanalyzed"]["confirmed"]


def test_collector_preserves_byte_span_sets_and_ssa(tmp_path):
    path = tmp_path / "fixed.sol"
    path.write_text("i < n")
    var = SimpleNamespace(name="i", location="default", source_mapping={"start": 0})
    phi = SimpleNamespace(read=[var], lvalue=var)
    mapping = dict(start=0, length=5, filename_absolute=str(path))
    fn = SimpleNamespace(name="f", full_name="f(uint256)", source_mapping=mapping)
    cfg = SimpleNamespace(node_id=7, type="IFLOOP", source_mapping=mapping,
                          expression="i < n", function=fn, irs=[], irs_ssa=[phi],
                          local_variables_read=[var], local_variables_written=[var],
                          state_variables_read=[], state_variables_written=[])
    fn.nodes = [cfg]
    contract = SimpleNamespace(name="C", functions=[fn], modifiers=[])
    rows = sc.collect_nodes(SimpleNamespace(contracts=[contract]), path)
    assert len(rows) == 1
    assert rows[0]["source"] == "i < n"
    assert rows[0]["span"] == {"start": 0, "end": 5}
    assert rows[0]["local_variables_written"][0]["name"] == "i"
    assert rows[0]["ir_ssa"][0]["lvalue"]["name"] == "i"


def test_collector_rejects_foreign_source(tmp_path):
    path = tmp_path / "fixed.sol"
    path.write_text("x")
    fn = SimpleNamespace(name="f", full_name="f()")
    cfg = SimpleNamespace(source_mapping=dict(start=0, length=1,
                          filename_absolute=str(tmp_path / "other.sol")))
    fn.nodes = [cfg]
    with pytest.raises(ValueError, match="Foreign"):
        sc.collect_nodes(SimpleNamespace(contracts=[
            SimpleNamespace(name="C", functions=[fn], modifiers=[])]), path)


def test_scoped_conclusions_do_not_generalize_local_phi_to_state(tmp_path):
    rows = []
    for fn, text, name, attr, written in (
            ("whileLocal", "i < n", "i", "local_variables_written", True),
            ("forLocal", "i < n", "i", "local_variables_written", True),
            ("whileState", "s < n", "s", "state_variables_written", False)):
        row = node(text, fn + "(uint256)", writes=(name,) if written else ())
        if written:
            row["ir_ssa"] = [dict(class_name="Phi", text=name + " := phi")]
        rows.append(row)
    report = tmp_path / "report.json"
    sc.write_json(report, dict(version=sc.VERSION, slither_invocations=6,
                               cases=cases(Loops=rows)))
    sc.write_json(tmp_path / "report.seal.json", dict(report_sha256=sc.sha(report)))
    target = tmp_path / "conclusions.json"
    result = sc.derive_conclusions(report, target)
    assert result["loop_header_merge_write"]["L1"]["confirmed"]
    assert not result["loop_header_merge_write"]["L2"]["confirmed"]
    assert result["additional_slither_invocations"] == 0
    with pytest.raises(ValueError, match="overwrite"):
        sc.derive_conclusions(report, target)


def test_scoped_conclusions_reject_tampered_raw_report(tmp_path):
    report = tmp_path / "report.json"
    sc.write_json(report, {})
    sc.write_json(tmp_path / "report.seal.json", dict(report_sha256="wrong"))
    with pytest.raises(ValueError, match="SHA mismatch"):
        sc.derive_conclusions(report, tmp_path / "conclusions.json")
