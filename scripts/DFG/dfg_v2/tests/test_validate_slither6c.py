"""6c validation adapters: synthetic Slither objects, no compiler execution."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest

from scripts.DFG.dfg_v2 import validate_slither as vs


def record(tmp_path, source="pragma solidity ^0.5.0; contract C {}", metadata=False):
    path = tmp_path/"s.sol"
    path.write_text(source)
    result = dict(path=str(path), sha256=vs._sha(path), metadata=None)
    if metadata:
        result["metadata"] = dict(version="0.5.11", source_sha256=result["sha256"])
    return result


def mapping(path, start, length=1):
    return dict(filename_absolute=str(path), start=start, length=length, lines=[1])


def model(path, raw=b"function f(uint x){x;}", modifier=False, name="x"):
    variable = NS(name=name, canonical_name="C.f.x", location="default",
                  source_mapping=mapping(path, raw.index(name.encode())))
    node = NS(source_mapping=mapping(path, raw.rindex(name.encode())),
              local_variables_read=[variable], local_variables_written=[],
              state_variables_read=[], state_variables_written=[])
    function = NS(name="f", canonical_name="C.f(uint)",
                  source_mapping=mapping(path, 0, len(raw)), nodes=[node])
    contract = NS(functions=[] if modifier else [function],
                  modifiers=[function] if modifier else [])
    return NS(contracts=[contract]), function, variable, node


def test_metadata_version_wins_without_changing_record(tmp_path):
    row = record(tmp_path, metadata=True)
    before = copy.deepcopy(row)
    selected = vs.select_version(row)
    assert selected["version"] == "0.5.11" and selected["origin"] == "metadata"
    assert row == before


def test_pragma_rule_keeps_first_match_even_when_later_is_stricter(tmp_path):
    row = record(tmp_path, "pragma solidity ^0.4.16; pragma solidity ^0.4.20;")
    selected = vs.select_version(row)
    assert selected["version"] == "0.4.16"
    assert selected["origin"] == "pragma_derived"
    assert selected["pragma_matches"] == ["0.4.16", "0.4.20"]


def test_no_pragma_is_default_not_pragma_derived(tmp_path):
    selected = vs.select_version(record(tmp_path, "contract C {}"))
    assert selected["version"] == "0.4.25" and selected["origin"] == "fallback_default"


def test_version_listing_never_invokes_compiler_and_refuses_overwrite(tmp_path, monkeypatch):
    row = record(tmp_path)
    path = tmp_path/"store.json"; path.write_text("{}")
    manifest = dict(tasks={t:dict(sources={"s.sol":row}) for t in vs.TASKS})
    monkeypatch.setattr(vs, "_load_inputs", lambda p:(path, {}, {}, manifest))
    monkeypatch.setattr(vs, "_compile", lambda *a:pytest.fail("must not compile"))
    report = vs.list_versions(path, tmp_path/"versions")
    assert report["origin_counts"] == {"pragma_derived": 2}
    assert not report["compilation_executed"] and not report["installation_attempted"]
    assert (tmp_path/"versions/versions.seal.json").exists()
    with pytest.raises(FileExistsError):
        vs.list_versions(path, tmp_path/"versions")


def test_selected_compiler_requires_authorized_matching_inventory(tmp_path):
    row = record(tmp_path)
    selection = vs.select_version(row)
    env = dict(skip_reasons=[], installed_compilers=[])
    assert vs.compiler_for_selection(selection, env)[1] == "local_compiler_not_explicitly_authorized"
    binary = tmp_path/"solc"; binary.write_bytes(b"mock");binary.chmod(0o700)
    ref = dict(path=str(binary),sha256=vs._sha(binary))
    with pytest.raises(ValueError, match="inventoried"):
        vs.compiler_for_selection(selection, env, {"0.5.0":ref})
    env["installed_compilers"] = [ref]
    assert vs.compiler_for_selection(selection, env, {"0.5.0":ref}) == (str(binary),None)


def test_full_reference_records_declaration_and_does_not_add_parameters(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither, fn, var, _ = model(path,raw)
    fn.parameters=[var]
    facts, result = vs.slither_full_facts(slither,path,raw)
    assert set(facts["L1"]) == {(1,"x","USE")}
    assert not result["parameter_writes_synthesized"]
    row=result["occurrences"][0]
    assert row["function"]["start"] == 0
    assert row["declaration"]["start"] == raw.index(b"x")


def test_reference_invalid_source_offset_is_error_not_silent_skip(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither, _, _, node = model(path,raw)
    node.source_mapping["start"] = len(raw)+1
    with pytest.raises(ValueError,match="byte offset"):
        vs.slither_full_facts(slither,path,raw)


def test_reference_invalid_declaration_identity_is_error(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither, _, var, _ = model(path,raw)
    var.source_mapping["length"] = -1
    with pytest.raises(ValueError,match="identity length"):
        vs.slither_full_facts(slither,path,raw)


def test_reference_modifier_excluded_and_inheritance_duplicates_audited(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither, fn, _, _ = model(path,raw,modifier=True)
    slither.contracts.append(NS(functions=[],modifiers=[copy.copy(fn)]))
    facts, report = vs.slither_full_facts(slither,path,raw)
    assert "modifier_inlining" in facts["L1"][(1,"x","USE")]
    assert report["counts"]["duplicate_function_contexts"] == 1
    comparison=vs.compare_facts({},facts["L1"])
    assert comparison["reference_count"] == 0 and len(comparison["excluded"]) == 1


def test_reference_function_scopes_use_byte_identity_not_name(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither, _, _, _ = model(path,raw)
    facts, extraction=vs.slither_full_facts(slither,path,raw)
    groups=vs.reference_function_scopes(facts["L1"],extraction,
        dict(functions=[dict(start=0,status="fallback")]))
    assert not groups["supported"] and len(groups["fallback"]) == 1
    groups=vs.reference_function_scopes(facts["L1"],extraction,
        dict(functions=[dict(start=1,status="supported")]))
    assert not groups["supported"] and len(groups["unmapped"]) == 1


def test_identity_mismatch_does_not_silently_change_primary_triples():
    candidate=dict(occurrences=[dict(line=1,name="x",kind="USE",function_start=0,
        declaration=dict(start=10))],ambiguous_triples=[])
    reference=dict(occurrences=[dict(layer="L1",fact=[1,"x","USE"],function=dict(start=0),
        declaration=dict(start=20))],ambiguous_triples=[])
    audit=vs.identity_audit(candidate,reference)
    assert len(audit["shared_triples_without_common_declaration"]) == 1
    assert audit["primary_comparison"] == "line_name_kind_triples"
    assert audit["triple_matches_do_not_prove_exact_binding"]


def test_complete_summary_reports_l1_recall_and_fallback_scope():
    a,b=(1,"x","USE"),(2,"y","USE")
    comp=dict(L1=vs.compare_facts({a:set()},{a:set(),b:set()}),
              L2=vs.compare_facts({},{}))
    records=[dict(status="compared",comparison=comp,
        L1_reference_scopes=dict(
            supported=vs.compare_facts({a:set()},{a:set()}),
            fallback=vs.compare_facts({},{b:set()}),
            unmapped=vs.compare_facts({},{})),
        v2_scope=dict(L1=dict(functions_fallback=1)))]
    summary=vs.summarize_complete(records)
    assert summary["metrics"]["L1"]["recall"] == .5
    assert summary["L1_reference_scopes"]["supported"]["recall"] == 1
    assert summary["L1_reference_scopes"]["fallback"]["recall"] == 0
    assert not summary["metrics"]["L1"]["ddg_edge_recall"]


def test_inheritance_is_a_category_not_an_automatic_denominator_exclusion():
    fact = (1, "x", "USE")
    report = vs.compare_facts({}, {fact: {"inheritance"}})
    assert report["reference_count"] == 1
    assert report["missing"] == [list(fact)]
    assert not report["excluded"]
    assert report["recall"] == 0
    assert vs._category(fact, {"inheritance"}, "L1", {}, {"fallback": {}}) == "inheritance"


def test_inherited_first_context_does_not_exclude_later_local_function(tmp_path):
    path = tmp_path/"s.sol"
    raw = b"function f(uint x){x;}"
    slither, function, _, _ = model(path, raw)
    base = slither.contracts[0]
    base.name = "Base"
    function.contract_declarer = base
    inherited_function = copy.copy(function)
    derived = NS(name="Derived", functions=[inherited_function], modifiers=[])
    slither.contracts = [derived, base]
    facts, extraction = vs.slither_full_facts(slither, path, raw)
    assert extraction["counts"]["duplicate_function_contexts"] == 1
    report = vs.compare_facts({}, facts["L1"])
    assert report["reference_count"] == 1 and not report["excluded"]
    assert report["recall"] == 0


def test_all_inherited_context_facts_are_unioned_independent_of_order(tmp_path):
    path=tmp_path/"s.sol"
    raw=b"function f(uint x,uint y){x;y;}"
    slither, function, _, _=model(path,raw)
    base=slither.contracts[0]
    base.name="Base"
    function.contract_declarer=base
    y=NS(name="y",canonical_name="Base.f.y",location="default",
         source_mapping=mapping(path,raw.index(b"y")))
    y_node=NS(source_mapping=mapping(path,raw.rindex(b"y")),
              local_variables_read=[y],local_variables_written=[],
              state_variables_read=[],state_variables_written=[])
    derived_function=copy.copy(function)
    derived_function.nodes=list(function.nodes)+[y_node]
    derived=NS(name="Derived",functions=[derived_function],modifiers=[])
    slither.contracts=[base,derived]
    first,first_detail=vs.slither_full_facts(slither,path,raw)
    slither.contracts=[derived,base]
    second,second_detail=vs.slither_full_facts(slither,path,raw)
    assert first == second
    assert set(first["L1"]) == {(1,"x","USE"),(1,"y","USE")}
    candidate={(1,"x","USE"):set()}
    assert vs.compare_facts(candidate,first["L1"]) == vs.compare_facts(candidate,second["L1"])
    assert vs.compare_facts(candidate,first["L1"])["recall"] == .5
    assert len(first_detail["functions"]) == len(second_detail["functions"]) == 2
    assert len(first_detail["occurrences"]) == len(second_detail["occurrences"]) == 3
    assert {row["context_contract"] for row in first_detail["occurrences"]} == {"Base","Derived"}
    assert first_detail["counts"]["duplicate_function_contexts"] == 1


def test_external_failure_phase_keeps_compile_and_analysis_distinct():
    from crytic_compile.platform.exceptions import InvalidCompilation
    from slither.exceptions import SlitherException
    assert vs.failure_phase(InvalidCompilation("compiler error")) == "solc_compile"
    assert vs.failure_phase(SlitherException("analysis error")) == "slither_analysis"
    assert vs.failure_phase(RuntimeError("other error")) == "external_pipeline_unknown"


def controlled_run_fixture(tmp_path, monkeypatch):
    source = "pragma solidity ^0.5.0; contract C { function f(uint x) public returns(uint) { return x; } }"
    row = record(tmp_path, source)
    raw = source.encode("utf8")
    graph = tmp_path/"g.bin";graph.write_bytes(b"frozen graph")
    audit = tmp_path/"audit.json"
    audit.write_text(json.dumps(dict(layers=dict(
        L1=dict(files={},evidence=[]),L2=dict(evidence=[])))))
    ref = lambda path: dict(path=str(path),sha256=vs._sha(path))
    store_path=tmp_path/"store.json";store_path.write_text("{}")
    manifest=dict(tasks={task:dict(sources={"s.sol":row}) for task in vs.TASKS})
    store=dict(tasks={task:dict(graphs=dict(F3=dict(graph=ref(graph),audit=ref(audit))))
                      for task in vs.TASKS})
    monkeypatch.setattr(vs,"_load_inputs",lambda path:(store_path,{},store,manifest))
    binary=tmp_path/"solc";binary.write_bytes(b"mock compiler");binary.chmod(0o700)
    compiler_ref=ref(binary)
    trust=tmp_path/"trusted.json";trust.write_text(json.dumps(dict(compilers={"0.5.0":compiler_ref})))
    monkeypatch.setattr(vs,"inspect_environment",lambda:dict(skip_reasons=[],installed_compilers=[compiler_ref]))
    return source, raw, row, store_path, trust, graph


def test_complete_runner_uses_original_metadata_and_does_not_construct_graph(tmp_path,monkeypatch):
    from scripts.DFG.dfg_v2 import l1_occurrences
    source,raw,row,store_path,trust,graph=controlled_run_fixture(tmp_path,monkeypatch)
    before=copy.deepcopy(row)
    original=l1_occurrences.extract
    seen=[]
    def checked_extract(text,file,metadata):
        seen.append(metadata)
        assert metadata is None
        return original(text,file,metadata)
    monkeypatch.setattr(l1_occurrences,"extract",checked_extract)
    slither,fn,_,_=model(Path(row["path"]),raw)
    fn.source_mapping=mapping(Path(row["path"]),raw.index(b"function"),
                              raw.rindex(b"}")-raw.index(b"function"))
    monkeypatch.setattr(vs,"_compile",lambda *args:slither)
    report=vs.run(store_path,tmp_path/"complete",trust)
    assert report["status"]=="compared" and len(seen)==2
    assert row==before and graph.read_bytes()==b"frozen graph"
    assert not report["graph_construction_executed"] and not report["training_executed"]
    for task in report["tasks"].values():
        item=task["files"][0]
        assert item["version_origin"]=="pragma_derived"
        assert item["comparison"]["L1"]["full_occurrence_metrics"]
        assert item["v2_scope"]["L1"]["event_symbol_occurrences"]==2
        assert item["L1_reference_scopes"]["supported"]["reference_count"]==1


def test_runner_records_slither_analysis_failure_without_version_retry(tmp_path,monkeypatch):
    from slither.exceptions import SlitherException
    _,_,_,store_path,trust,_=controlled_run_fixture(tmp_path,monkeypatch)
    calls=[]
    def fail(path,compiler):
        calls.append((path,compiler))
        raise SlitherException("synthetic analyzer error")
    monkeypatch.setattr(vs,"_compile",fail)
    report=vs.run(store_path,tmp_path/"failed",trust)
    assert len(calls)==2  # One attempt in each cohort, no second compiler version.
    for task in report["tasks"].values():
        row=task["files"][0]
        assert row["status"]=="compile_failed"
        assert row["failure_phase"]=="slither_analysis"
        assert row["exception_module"]=="slither.exceptions"
        assert task["summary"]["external_failure_phases"]=={"slither_analysis":1}


def test_partial_missing_cfg_filename_is_not_a_complete_reference(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither,function,_,node=model(path,raw)
    unmapped=copy.deepcopy(node)
    del unmapped.source_mapping["filename_absolute"]
    function.nodes.append(unmapped)
    facts,result=vs.slither_full_facts(slither,path,raw)
    assert facts["L1"]  # Some valid evidence exists, but the file is incomplete.
    assert result["counts"]["cfg_nodes"]==1
    assert result["counts"]["missing_filename"]==1
    assert result["comparability"]["status"]=="not_comparable"
    assert result["comparability"]["blockers"]=={"missing_filename":1}


def test_missing_declaration_filename_never_borrows_target_file(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither,_,variable,_=model(path,raw)
    del variable.source_mapping["filename_absolute"]
    facts,result=vs.slither_full_facts(slither,path,raw)
    assert facts["L1"] and result["counts"]["unknown_variable_identity"]==1
    assert result["occurrences"][0]["declaration"] is None
    audit=vs.identity_audit(dict(occurrences=[],ambiguous_triples=[]),result)
    assert len(audit["reference_occurrences_missing_identity"])==1


def test_missing_function_filename_remains_unknown(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither,function,_,_=model(path,raw)
    del function.source_mapping["filename_absolute"]
    _,result=vs.slither_full_facts(slither,path,raw)
    assert result["counts"]["unknown_function_identity"]==1
    assert result["functions"][0]["source"] is None
    assert result["occurrences"][0]["function"] is None


def test_real_foreign_cfg_node_does_not_poison_comparability(tmp_path):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither,function,_,node=model(path,raw)
    foreign=copy.deepcopy(node)
    foreign.source_mapping["filename_absolute"]=str(tmp_path/"dependency.sol")
    foreign.source_mapping["start"]=999999  # Offset belongs to the other file.
    function.nodes.append(foreign)
    _,result=vs.slither_full_facts(slither,path,raw)
    assert result["counts"]["foreign_nodes"]==1
    assert result["comparability"]["status"]=="comparable"
    assert result["comparability"]["foreign_nodes_excluded"]==1


@pytest.mark.parametrize("bad_filename", [None,"",23,"relative.sol"])
def test_missing_or_invalid_filename_is_not_a_foreign_file(tmp_path,bad_filename):
    path=tmp_path/"s.sol";raw=b"function f(uint x){x;}"
    slither,function,_,node=model(path,raw)
    bad=copy.deepcopy(node);bad.source_mapping["filename_absolute"]=bad_filename
    function.nodes.append(bad)
    _,result=vs.slither_full_facts(slither,path,raw)
    assert result["comparability"]["status"]=="not_comparable"
    assert not result["counts"].get("foreign_nodes")
    assert result["counts"].get("missing_filename",0)+result["counts"].get("invalid_filename",0)==1


def test_runner_refuses_metrics_for_partially_unmapped_file(tmp_path,monkeypatch):
    _,raw,row,store_path,trust,_=controlled_run_fixture(tmp_path,monkeypatch)
    slither,function,_,node=model(Path(row["path"]),raw)
    bad=copy.deepcopy(node);del bad.source_mapping["filename_absolute"]
    function.nodes.append(bad)
    monkeypatch.setattr(vs,"_compile",lambda *args:slither)
    report=vs.run(store_path,tmp_path/"not_comparable",trust)
    for task in report["tasks"].values():
        item=task["files"][0]
        assert item["status"]=="not_comparable"
        assert item["comparability"]["blockers"]=={"missing_filename":1}
        assert "comparison" not in item
        assert task["summary"]["not_comparable_files"]==1
        assert task["summary"]["compared_files"]==0
        assert task["summary"]["metrics"]["L1"]["recall"] is None


@pytest.mark.parametrize("link", ["__cause__", "__context__"])
def test_failure_phase_unwraps_slither_compile_exception(link):
    from crytic_compile.platform.exceptions import InvalidCompilation
    from slither.exceptions import SlitherError
    compiler = InvalidCompilation("source compiler rejected")
    wrapped = SlitherError("opaque external error message")
    setattr(wrapped, link, compiler)
    assert vs.failure_phase(wrapped) == "solc_compile"


def test_failure_phase_context_cycles_do_not_hang_or_change_real_analysis_error():
    from slither.exceptions import SlitherException
    analysis = SlitherException("analyzer error")
    middle = RuntimeError("wrapper context")
    analysis.__context__ = middle
    middle.__context__ = analysis
    assert vs.failure_phase(analysis) == "slither_analysis"
    unknown = RuntimeError("unknown error")
    unknown.__context__ = unknown
    assert vs.failure_phase(unknown) == "external_pipeline_unknown"


def test_failure_phase_compiler_cause_wins_even_with_a_context_cycle():
    from crytic_compile.platform.exceptions import InvalidCompilation
    from slither.exceptions import SlitherException
    wrapped = SlitherException("analysis-looking wrapper")
    context = RuntimeError("cyclic wrapper")
    wrapped.__context__ = context
    context.__context__ = wrapped
    context.__cause__ = InvalidCompilation("actual compiler failure")
    assert vs.failure_phase(wrapped) == "solc_compile"
