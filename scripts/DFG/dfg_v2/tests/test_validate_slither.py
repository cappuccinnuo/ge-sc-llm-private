"""Offline adapter tests: no Slither compilation or external binary execution."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.DFG.dfg_v2 import validate_slither as vs


def source_record(tmp_path, text="pragma solidity ^0.4.25;"):
    path = tmp_path / "sample.sol"
    path.write_text(text)
    sha = vs._sha(path)
    return dict(path=str(path), sha256=sha, metadata=dict(version="0.4.25", source_sha256=sha))


def environment():
    return dict(skip_reasons=[], installed_compilers=[])


@pytest.mark.parametrize("missing", ["slither", "solc_select", "crytic_compile"])
def test_dependency_inventory_never_executes_compiler(tmp_path, monkeypatch, missing):
    monkeypatch.setattr(vs.importlib.util, "find_spec", lambda name:
                        None if name == missing else SimpleNamespace(origin="/installed/"+name))
    monkeypatch.setattr(vs.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    result = vs.inspect_environment()
    assert not result["compiler_executed"]
    assert not result["installation_attempted"]
    assert not result["network_requested"]
    assert "no_local_solc_select_artifacts" in result["skip_reasons"]
    assert "solc_select_unavailable" in result["skip_reasons"]
    if missing == "slither":
        assert "slither_analyzer_unavailable" in result["skip_reasons"]


def test_no_exact_version_never_uses_pragma_or_default(tmp_path):
    row = source_record(tmp_path)
    row["metadata"] = None
    assert vs.compiler_for(row, environment()) == (None, "no_bound_exact_compiler_version")
    row["metadata"] = dict(version="^0.4.25", source_sha256=row["sha256"])
    assert vs.exact_version(row) is None


def test_metadata_must_belong_to_source(tmp_path):
    row = source_record(tmp_path)
    row["metadata"]["source_sha256"] = "0"*64
    with pytest.raises(ValueError, match="different source"):
        vs.exact_version(row)


def test_dependency_missing_is_explicit_skip(tmp_path):
    row = source_record(tmp_path)
    env = dict(skip_reasons=["slither_analyzer_unavailable"], installed_compilers=[])
    assert vs.compiler_for(row, env)[1] == "slither_analyzer_unavailable"


def test_installed_compiler_not_implicitly_authorized(tmp_path):
    row = source_record(tmp_path)
    assert vs.compiler_for(row, environment())[1] == "local_compiler_not_explicitly_authorized"


def test_compiler_hash_and_inventory_required_without_execution(tmp_path):
    row = source_record(tmp_path)
    binary = tmp_path / "solc"
    binary.write_bytes(b"not executable binary")
    binary.chmod(0o700)
    ref = dict(path=str(binary), sha256=vs._sha(binary))
    with pytest.raises(ValueError, match="inventoried"):
        vs.compiler_for(row, environment(), {"0.4.25": ref})
    env = dict(skip_reasons=[], installed_compilers=[ref])
    assert vs.compiler_for(row, env, {"0.4.25": ref}) == (str(binary), None)
    binary.write_bytes(b"modified")
    with pytest.raises(ValueError, match="SHA mismatch"):
        vs.compiler_for(row, env, {"0.4.25": ref})


def audit_fixture():
    return dict(layers=dict(
        L1=dict(files={"sample.sol": dict(anchors=[
            dict(node_id=1, start=2, end=6, role="variable_declaration_statement"),
            dict(node_id=2, start=7, end=11, role="expression_statement")],
            analysis=dict(functions=[]))},
            evidence=[dict(source=1, target=2, symbol="sample.sol:0:2:x")]),
        L2=dict(files={}, evidence=[
            dict(file="sample.sol", relation="READS_STATE", state=dict(name="balance"),
                 occurrence=dict(start=7, end=8), status="projected",
                 via_alias=False, callable_kind="function_definition"),
            dict(file="sample.sol", relation="WRITES_STATE", state=dict(name="balance"),
                 occurrence=dict(start=7, end=8), status="unit_unmapped",
                 via_alias=True, callable_kind="function_definition")])))


def test_l2_uses_raw_byte_occurrences_and_l1_declares_partial_scope():
    raw = b"a\nx=1;\ny=x;"
    facts, scopes = vs.v2_facts(audit_fixture(), "sample.sol", raw)
    assert set(facts["L1"]) == {(2, "x", "DEF"), (3, "x", "USE")}
    assert set(facts["L2"]) == {(3, "balance", "READ"), (3, "balance", "WRITE")}
    assert facts["L2"][(3, "balance", "WRITE")] == {"alias"}
    assert scopes["L2_projection_statuses"] == {"projected": 1, "unit_unmapped": 1}
    assert "partial" in scopes["L1_scope"]


def test_utf8_coordinate_conversion_not_character_index():
    text = "// \u4e2d\u6587\nuint x;\n"
    offset = text.encode("utf8").index(b"uint")
    assert vs.raw_line(text, offset) == 2
    with pytest.raises(ValueError, match="byte offset"):
        vs.raw_line(text, -1)


def test_parameter_definition_uses_declaration_not_function_start():
    audit = audit_fixture()
    audit["layers"]["L1"]["files"]["sample.sol"]["anchors"][0]["role"] = "function_definition"
    audit["layers"]["L1"]["files"]["sample.sol"]["anchors"][0]["start"] = 0
    facts, _ = vs.v2_facts(audit, "sample.sol", b"a\nx=1;\ny=x;")
    assert (2, "x", "DEF") in facts["L1"]


def test_alias_and_modifier_context_excluded_but_reported():
    a, b, c, d = (1, "x", "READ"), (2, "x", "READ"), (3, "x", "WRITE"), (4, "x", "READ")
    result = vs.compare_facts({a:set(), b:{"alias"}, c:{"modifier_inlining"}},
                              {a:set(), d:set()})
    assert result["candidate_count"] == 1
    assert result["reference_count"] == 2
    assert result["precision"] == 1
    assert result["recall"] == .5
    assert len(result["excluded"]) == 2


def test_partial_l1_never_reports_full_recall():
    a, b = (1, "x", "DEF"), (2, "y", "DEF")
    result = vs.compare_facts({a:set()}, {a:set(), b:set()}, partial=True)
    assert result["precision"] == 1
    assert result["recall"] is None
    assert not result["recall_defined"]
    assert not result["full_occurrence_metrics"]
    assert result["missing_role"] == "outside_partial_endpoint_evidence"


def test_only_comparable_files_enter_summary_denominator():
    a = (1, "x", "READ")
    comparison = dict(L1=vs.compare_facts({a:set()}, {a:set()}, partial=True),
                      L2=vs.compare_facts({a:set()}, {a:set()}))
    records = [dict(status="compared", comparison=comparison),
               dict(status="skipped", reason="no_solc"),
               dict(status="compile_failed", reason="bad_input")]
    result = vs.summarize(records)
    assert result["compared_files"] == 1
    assert result["skipped_files"] == result["failed_files"] == 1
    assert result["metrics"]["L2"]["recall"] == 1
    assert result["metrics"]["L1"]["recall"] is None


def test_zero_compared_files_report_null_metrics():
    result = vs.summarize([dict(status="skipped", reason="no_solc")])
    for layer in ("L1", "L2"):
        assert result["metrics"][layer]["comparable_files"] == 0
        assert result["metrics"][layer]["precision"] is None
        assert result["metrics"][layer]["recall"] is None


def test_slither_adapter_filters_foreign_nodes_and_retains_modifier_exclusion(tmp_path):
    path = tmp_path / "sample.sol"
    variable = SimpleNamespace(name="balance", location="storage")
    node = SimpleNamespace(source_mapping=dict(filename_absolute=str(path), start=2, lines=[2]),
        state_variables_read=[variable], state_variables_written=[],
        local_variables_read=[variable], local_variables_written=[])
    foreign = SimpleNamespace(source_mapping=dict(filename_absolute="/foreign.sol", start=2))
    modifier = SimpleNamespace(nodes=[node, foreign])
    contract = SimpleNamespace(functions=[], modifiers=[modifier])
    facts, counts = vs.slither_facts(SimpleNamespace(contracts=[contract]), path, b"a\nb;")
    assert facts["L2"][(2, "balance", "READ")] == {"modifier_inlining", "alias"}
    assert counts["foreign_or_unmapped_nodes"] == 1


def test_no_compiler_run_emits_sealed_explicit_skip_report(tmp_path, monkeypatch):
    from scripts.DFG.dfg_v2 import inputs, store
    row = source_record(tmp_path)
    graph = tmp_path / "graph.bin"
    graph.write_bytes(b"frozen graph bytes; never loaded by this test")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps(audit_fixture()))
    manifest_path = tmp_path / "manifest.json"
    manifest = dict(tasks={t: dict(sources={"sample.sol":row}) for t in vs.TASKS})
    manifest_path.write_text(json.dumps(manifest))
    ref = lambda p: dict(path=str(p), sha256=vs._sha(p))
    document = dict(input_manifest=ref(manifest_path), tasks={
        t: dict(graphs=dict(F3=dict(graph=ref(graph), audit=ref(audit)))) for t in vs.TASKS})
    store_path = tmp_path / "store.json"
    store_path.write_text(json.dumps(document))
    monkeypatch.setattr(store, "verify_store", lambda p: dict(status="accepted"))
    monkeypatch.setattr(inputs, "load_manifest", lambda *a, **kw: manifest)
    monkeypatch.setattr(vs, "inspect_environment", lambda: dict(
        skip_reasons=["solc_select_unavailable"], installed_compilers=[]))
    monkeypatch.setattr(vs, "_compile", lambda *args: pytest.fail("must not compile"))
    before = graph.read_bytes()
    report = vs.run(store_path, tmp_path/"out")
    assert report["status"] == "skipped"
    assert not report["compilation_executed"]
    assert graph.read_bytes() == before
    assert (tmp_path/"out"/"report.seal.json").exists()
    assert set(report["tasks"]) == set(vs.TASKS)
    for result in report["tasks"].values():
        assert result["summary"]["compared_files"] == 0
        assert result["summary"]["skip_reasons"] == {"solc_select_unavailable": 1}
    with pytest.raises(FileExistsError):
        vs.run(store_path, tmp_path/"out")


def test_non_dict_slither_mapping_is_explicitly_unavailable(tmp_path):
    node = SimpleNamespace(source_mapping=SimpleNamespace(start=0))
    function = SimpleNamespace(nodes=[node])
    contract = SimpleNamespace(functions=[function], modifiers=[])
    facts, counts = vs.slither_facts(SimpleNamespace(contracts=[contract]),
                                   tmp_path/"sample.sol", b"x")
    assert counts["unsupported_source_mapping"] == 1
    assert counts["source_nodes_seen"] == 1
    assert not facts["L1"] and not facts["L2"]


def test_unknown_slither_version_is_not_silently_accepted(tmp_path, monkeypatch):
    import importlib_metadata
    monkeypatch.setattr(importlib_metadata, "version", lambda name: "9.9.9")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert "unsupported_or_unverified_slither_version" in vs.inspect_environment()["skip_reasons"]
