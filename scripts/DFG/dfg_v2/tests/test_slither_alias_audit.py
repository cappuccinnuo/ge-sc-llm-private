"""Parser-only audit tests; these fixtures do not claim solc validation."""
import copy
import json

import pytest

from scripts.DFG.dfg_v2.slither_align import SourceFacts
from scripts.DFG.dfg_v2.slither_alias_audit import audit_alias, run, _sha


def exact(ast, kind, text):
    return next(n for n in ast.nodes if n.type == kind and ast.text(n) == text)


def fp_fixture(two_roots=False, kind="READ"):
    src = ("contract C { struct Box { uint value; } Box first; Box second; "
           "function f() public { Box storage ref = first; " +
           ("ref = second; " if two_roots else "") +
           "uint v = ref.value; } }")
    ast = SourceFacts(src)
    context = next(n for n in ast.nodes if n.type == "function_definition")
    state = exact(ast, "state_variable_declaration", "Box first;")
    local = exact(ast, "variable_declaration", "Box storage ref")
    occurrence = exact(ast, "member_expression", "ref.value")
    cid = "sample.sol:" + str(context.start_byte)
    roots = []
    for name in ("first", "second") if two_roots else ("first",):
        node = exact(ast, "state_variable_declaration", "Box " + name + ";")
        rhs = next(n for n in ast.nodes if n.type == "identifier" and ast.text(n) == name
                   and n.start_byte > local.end_byte)
        roots.append(dict(name="ref", local_start=local.start_byte, local_end=local.end_byte,
                          state_start=node.start_byte, state_end=node.end_byte,
                          state_name=name, source_start=rhs.start_byte, source_end=rhs.end_byte))
    event = dict(function_start=context.start_byte, declaration=[state.start_byte, state.end_byte],
                 name="first", kind=kind, evidence=[dict(via_alias=True, file="sample.sol",
                 callable=cid, occurrence=dict(start=occurrence.start_byte,
                                               end=occurrence.end_byte, role=occurrence.type))])
    d = dict(difference_id="id", task="sample_task", file="sample.sol", source_sha256="sha",
             direction="FP", layer="L2", category="alias", name="first", kind=kind,
             line=1, source_excerpt="ref.value", primary=event)
    audit = dict(binding_audits={cid: dict(callable=cid, scope_fallback=None,
                                         aliases=roots, diagnostics=[])})
    return d, ast, audit


def test_single_root_read_and_write_distinguished_without_claiming_convention():
    for kind, subtype in [("READ", "single_root_state_read_missing"),
                          ("WRITE", "single_root_state_write_missing")]:
        d, ast, audit = fp_fixture(kind=kind)
        row = audit_alias(d, ast, audit)
        assert row["subtype"] == subtype
        assert row["semantic_verdict"] == "pending_probe"
        assert row["convention_acceptance_requires_direct_probe"]
        assert len(row["occurrences"][0]["state_root_set"]) == 1


def test_multiple_roots_require_individual_review_not_automatic_extra_root_claim():
    d, ast, audit = fp_fixture(two_roots=True)
    row = audit_alias(d, ast, audit)
    assert row["subtype"] == "multiple_root_union_requires_individual_review"
    assert len(row["occurrences"][0]["state_root_set"]) == 2
    assert row["semantic_verdict"] == "pending_probe"


@pytest.mark.parametrize("mutation", ["callable", "occurrence_span", "state_identity",
                                     "local_identity", "rhs_identity", "alias_flag",
                                     "empty_evidence"])
def test_tampered_alias_identity_is_rejected(mutation):
    d, ast, audit = fp_fixture()
    binding = next(iter(audit["binding_audits"].values()))
    if mutation == "callable":
        d["primary"]["evidence"][0]["callable"] = "sample.sol:0"
    elif mutation == "occurrence_span":
        d["primary"]["evidence"][0]["occurrence"]["start"] += 1
    elif mutation == "state_identity":
        d["primary"]["declaration"][0] += 1
    elif mutation == "local_identity":
        binding["aliases"][0]["local_start"] += 1
    elif mutation == "rhs_identity":
        binding["aliases"][0]["source_start"] += 1
    elif mutation == "alias_flag":
        d["primary"]["evidence"][0]["via_alias"] = False
    else:
        d["primary"]["evidence"] = []
    with pytest.raises(ValueError):
        audit_alias(d, ast, audit)


def fn_fixture():
    src = ("contract C { struct Box { uint value; } Box first; function f() public { "
           "{ Box storage ref = first; ref.value = 0; } "
           "{ Box storage ref = first; ref.value = 1; } } }")
    ast = SourceFacts(src)
    context = next(n for n in ast.nodes if n.type == "function_definition")
    state = exact(ast, "state_variable_declaration", "Box first;")
    assignment = exact(ast, "assignment_expression", "ref.value = 0")
    declarations = [n for n in ast.nodes if n.type == "variable_declaration"
                    and ast.text(n) == "Box storage ref"]
    cid = "sample.sol:" + str(context.start_byte)
    d = dict(difference_id="fn", task="sample_task", file="sample.sol", source_sha256="sha",
             direction="FN", layer="L2", category="alias", name="first", kind="WRITE",
             line=1, source_excerpt="ref.value = 0", primary=dict(
             function_start=context.start_byte, name="first",
             declaration=[state.start_byte, state.end_byte],
             span=[assignment.start_byte, assignment.end_byte]))
    diagnostic = dict(reason="ambiguous_local_declaration", name="ref",
                      declaration_count=len(declarations), callable=cid)
    audit = dict(binding_audits={cid: dict(callable=cid, scope_fallback=None,
                                         aliases=[], diagnostics=[diagnostic])})
    return d, ast, audit


def test_same_local_name_in_distinct_blocks_is_analysis_limit_not_language_ambiguity():
    d, ast, audit = fn_fixture()
    row = audit_alias(d, ast, audit)
    assert row["subtype"] == "ambiguous_callable_local_alias"
    assert row["semantic_verdict"] == "v2_scope_limit"
    assert row["not_language_ambiguity"]
    assert len({x["lexical_scope"]["start"] for x in row["declaration_checks"]}) == 2
    assert row["impact"]["l1_fact_generation_depends_on_l2"] is False
    assert row["impact"]["l2_write_kill_or_propagation"] is False


def test_missing_ambiguity_diagnostic_is_not_guessed():
    d, ast, audit = fn_fixture()
    next(iter(audit["binding_audits"].values()))["diagnostics"] = []
    assert audit_alias(d, ast, audit)["subtype"] == "unresolved"


def test_ambiguity_count_mismatch_rejected():
    d, ast, audit = fn_fixture()
    next(iter(audit["binding_audits"].values()))["diagnostics"][0]["declaration_count"] = 3
    with pytest.raises(ValueError, match="count mismatch"):
        audit_alias(d, ast, audit)


def test_audit_does_not_modify_evidence():
    d, ast, audit = fn_fixture()
    before = copy.deepcopy((d, audit))
    audit_alias(d, ast, audit)
    assert (d, audit) == before


def test_refuses_existing_output_before_loading(tmp_path):
    with pytest.raises(FileExistsError):
        run(tmp_path / "nonexistent.json", tmp_path)


def test_alignment_digest_mismatch_rejected(tmp_path):
    alignment = tmp_path / "report.json"
    alignment.write_text(json.dumps({"inputs": {}}))
    (tmp_path / "report.seal.json").write_text(json.dumps({"report_sha256": "wrong"}))
    with pytest.raises(ValueError, match="alignment seal"):
        run(alignment, tmp_path / "new")


def test_real_report_inputs_are_verified_before_processing(tmp_path):
    store = tmp_path / "store.json"
    store.write_text("{}")
    alignment = tmp_path / "report.json"
    alignment.write_text(json.dumps({"inputs": {"store": {
        "path": str(store), "sha256": "wrong"}}, "differences": []}))
    (tmp_path / "report.seal.json").write_text(json.dumps({"report_sha256": _sha(alignment)}))
    with pytest.raises(ValueError, match="input digest"):
        run(alignment, tmp_path / "new")

def test_memory_declaration_in_other_block_is_an_audited_collision_not_alias():
    d, ast, audit = fn_fixture()
    source = ast.raw.decode("utf8")
    start = source.rfind("Box storage ref")
    source = source[:start] + source[start:].replace("Box storage ref", "Box memory ref", 1)
    changed = SourceFacts(source)
    row = audit_alias(d, changed, audit)
    assert row["subtype"] == "ambiguous_callable_local_alias"
    assert sorted(x["location"] for x in row["declaration_checks"]) == ["memory", "storage"]
    assert [x["location"] for x in row["declaration_checks"] if x["contains_target_write"]] == ["storage"]
