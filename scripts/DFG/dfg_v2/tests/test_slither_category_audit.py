"""Synthetic-input regression checks for the Prompt 6d.2 review gate."""
import copy
import json
import random

import pytest

from scripts.DFG.dfg_v2.slither_align import SourceFacts
from scripts.DFG.dfg_v2.slither_category_audit import (
    VERSION, gate_status, histogram, normalized_shape, prepare, sample_categories, validate)
from scripts.DFG.dfg_v2.slither_review import sha256, evidence_for


def write(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf8")


def basic_event(identity, task="task", direction="FN", category="scope", **extra):
    event = dict(difference_id=identity, task=task, layer="L2",
                 direction=direction, category=category)
    event.update(extra)
    return event


def test_sampling_seed_zero_ten_per_nonempty_stratum_and_all_small():
    rows = [basic_event(str(i).zfill(3)) for i in range(25)]
    rows += [basic_event("small" + str(i), task="small") for i in range(3)]
    selected, groups = sample_categories(list(reversed(rows)))
    assert [x["difference_id"] for x in selected if x["task"] == "task"] == sorted(
        x["difference_id"] for x in random.Random(0).sample(rows[:25], 10))
    assert len(selected) == 13
    assert sorted(x["population"] for x in groups) == [3, 25]
    assert sample_categories(rows) == (selected, groups)


@pytest.mark.parametrize("mutation", ["duplicate", "direction", "layer"])
def test_invalid_sampling_population_rejected(mutation):
    rows = [basic_event("a")]
    if mutation == "duplicate": rows.append(copy.deepcopy(rows[0]))
    elif mutation == "direction": rows[0]["direction"] = "TP"
    else: rows[0]["layer"] = "L3"
    with pytest.raises(ValueError):
        sample_categories(rows)


def test_shape_preserves_member_selectors_and_repeated_variable_identity():
    source = "contract C { uint a; uint b; function f() public { a.value = b + b; } }"
    ast = SourceFacts(source)
    n = next(n for n in ast.nodes if n.type == "expression_statement")
    shape = normalized_shape({"span": [n.start_byte, n.end_byte]}, ast)
    assert shape == "VAR_1.value = VAR_2 + VAR_2;"


def test_shape_preserves_field_whose_name_matches_another_variable():
    source = "contract C { uint a; uint value; function f() public { a.value = value; } }"
    ast = SourceFacts(source)
    n = next(n for n in ast.nodes if n.type == "expression_statement")
    assert normalized_shape({"span": [n.start_byte, n.end_byte]}, ast) == \
        "VAR_1.value = VAR_2;"


def bundle(tmp_path, direction="FN"):
    source = tmp_path / "sample.sol"
    source.write_text("contract C { uint a; function f() public { a = 1; } }", encoding="utf8")
    ast = SourceFacts(source.read_text())
    n = next(n for n in ast.nodes if n.type == "expression_statement")
    event = basic_event("one", direction=direction, source_path=str(source),
                        source_sha256=sha256(source), span=[n.start_byte, n.end_byte],
                        source_excerpt=ast.text(n), primary={"identity": 1},
                        nearby_candidate=[], nearby_reference=[])
    alignment = tmp_path / "report.json"
    write(alignment, {"differences": [event]})
    write(tmp_path / "report.seal.json", {"report_sha256": sha256(alignment)})
    out = tmp_path / "selection"
    prepare(alignment, out)
    selection_path = out / "selection.json"
    selection = json.loads(selection_path.read_text())
    policy = tmp_path / "policy.md"
    policy.write_text("The supported scope excludes this synthetic case.", encoding="utf8")
    scope = dict(path=str(policy), sha256=sha256(policy), quote=policy.read_text())
    probe = tmp_path / "probe.json"
    write(probe, {"observed": True, "impact": {"changes_definition_kill": False,
                                             "changes_existing_dependency_facts": False}})
    empirical = dict(path=str(probe), sha256=sha256(probe), pointer="/observed",
                     value=True, interpretation="Synthetic probe fact used only by validator tests.")
    decisions = dict(version=VERSION, selection_sha256=sha256(selection_path),
                     decisions=[dict(difference_id="one", evidence=evidence_for(event),
                                     reason="Scope excludes this case.", predicate_holds=True,
                                     verdict="v2_scope_limit", scope_basis=scope)])
    group = selection["strata"][0]
    categories = dict(version=VERSION, selection_sha256=sha256(selection_path),
                      evidence_inputs=[dict(path=str(probe), sha256=sha256(probe))],
                      categories=[dict(key=group["key"], population=1, sample_ids=["one"],
                                       mechanical_predicate="test_scope", reason="Documented scope.",
                                       status="accepted",
                                       rationale=[dict(kind="scope", reference=scope)])],
                      residuals=[], additional_defect_ids=[])
    return dict(selection=selection_path, decisions=tmp_path/"decisions.json",
                categories=tmp_path/"categories.json", decisions_doc=decisions,
                categories_doc=categories, event=event, empirical=empirical,
                source=source, alignment=alignment)


def check(b):
    write(b["decisions"], b["decisions_doc"])
    write(b["categories"], b["categories_doc"])
    return validate(b["selection"], b["decisions"], b["categories"])


def residual(b):
    event = b["event"]
    b["decisions_doc"]["decisions"][0]["verdict"] = "unclear"
    b["categories_doc"]["categories"][0]["status"] = "accepted_with_residual"
    ref = b["empirical"]
    b["categories_doc"]["residuals"] = [dict(
        difference_id="one", direction=event["direction"], evidence=evidence_for(event),
        reason="Mechanism remains unconfirmed after probe.", empirical_checks=[ref],
        impact=dict(checked=True, changes_definition_kill=False,
                    changes_existing_dependency_facts=False, reason="Checked independently.",
                    evidence=[ref]))]


def test_bound_scope_accepts_and_does_not_modify_inputs(tmp_path):
    b = bundle(tmp_path)
    before = copy.deepcopy((b["decisions_doc"], b["categories_doc"]))
    assert check(b)["gate"] == "passed_all_categories"
    assert (b["decisions_doc"], b["categories_doc"]) == before


def test_convention_requires_exact_empirical_fact(tmp_path):
    b = bundle(tmp_path)
    row = b["decisions_doc"]["decisions"][0]
    row.update(verdict="slither_convention", convention_evidence=[b["empirical"]])
    b["categories_doc"]["categories"][0]["rationale"] = [
        dict(kind="empirical", reference=b["empirical"])]
    assert check(b)["gate"] == "passed_all_categories"
    row["convention_evidence"][0]["value"] = False
    with pytest.raises(ValueError, match="match"):
        check(b)


@pytest.mark.parametrize("mutation", ["source", "event", "scope_quote", "sample_ids",
                                     "missing_decision", "duplicate_decision",
                                     "missing_category", "duplicate_category"])
def test_tampered_bindings_and_coverage_rejected(tmp_path, mutation):
    b = bundle(tmp_path)
    if mutation == "source": b["source"].write_text("changed")
    elif mutation == "event": b["decisions_doc"]["decisions"][0]["evidence"]["primary"] = {}
    elif mutation == "scope_quote": b["decisions_doc"]["decisions"][0]["scope_basis"]["quote"] = "absent"
    elif mutation == "sample_ids": b["categories_doc"]["categories"][0]["sample_ids"] = []
    elif mutation == "missing_decision": b["decisions_doc"]["decisions"] = []
    elif mutation == "duplicate_decision": b["decisions_doc"]["decisions"] *= 2
    elif mutation == "missing_category": b["categories_doc"]["categories"] = []
    else: b["categories_doc"]["categories"] *= 2
    with pytest.raises(ValueError):
        check(b)


@pytest.mark.parametrize("field", ["source_bindings", "histograms"])
def test_resealed_selection_cannot_drop_sources_or_histograms(tmp_path, field):
    b = bundle(tmp_path)
    selection = json.loads(b["selection"].read_text())
    selection[field] = {}
    write(b["selection"], selection)
    write(b["selection"].with_name("selection.seal.json"),
          dict(version=VERSION, selection_sha256=sha256(b["selection"])))
    for key in ("decisions_doc", "categories_doc"):
        b[key]["selection_sha256"] = sha256(b["selection"])
    with pytest.raises(ValueError, match="bindings or shape"):
        check(b)


def test_false_predicate_and_hidden_unclear_cannot_be_accepted(tmp_path):
    b = bundle(tmp_path)
    b["decisions_doc"]["decisions"][0]["predicate_holds"] = False
    with pytest.raises(ValueError, match="failed predicate"):
        check(b)
    b["decisions_doc"]["decisions"][0].update(predicate_holds=True, verdict="unclear")
    with pytest.raises(ValueError, match="Unclear"):
        check(b)


def test_defect_is_blocking_even_when_category_marked_blocked(tmp_path):
    b = bundle(tmp_path)
    b["decisions_doc"]["decisions"][0]["verdict"] = "v2_defect"
    b["categories_doc"]["categories"][0]["status"] = "blocked"
    assert check(b)["gate"] == "blocked_v2_defect"


def test_additional_defect_ids_must_be_unique_real_events(tmp_path):
    b = bundle(tmp_path)
    for ids in [["absent"], ["one", "one"]]:
        b["categories_doc"]["additional_defect_ids"] = ids
        with pytest.raises(ValueError, match="Additional defect"):
            check(b)
    b["categories_doc"]["additional_defect_ids"] = ["one"]
    assert check(b)["gate"] == "blocked_v2_defect"


def test_bounded_fn_residual_needs_independent_kill_and_dependency_impact_check(tmp_path):
    b = bundle(tmp_path); residual(b)
    assert check(b)["gate"] == "passed_with_bounded_FN_residuals"
    for field, value in [("checked", False), ("changes_definition_kill", True),
                         ("changes_existing_dependency_facts", True), ("evidence", [])]:
        previous = b["categories_doc"]["residuals"][0]["impact"][field]
        b["categories_doc"]["residuals"][0]["impact"][field] = value
        assert check(b)["gate"] == "blocked_residual_impact_unverified"
        b["categories_doc"]["residuals"][0]["impact"][field] = previous


def test_fp_residual_is_blocking_despite_safe_impact_claim(tmp_path):
    b = bundle(tmp_path, direction="FP"); residual(b)
    assert check(b)["gate"] == "blocked_residual_count_or_direction"


def test_duplicate_residual_rejected_even_when_category_blocked(tmp_path):
    b = bundle(tmp_path); residual(b)
    b["categories_doc"]["categories"][0]["status"] = "blocked"
    b["categories_doc"]["residuals"] *= 2
    with pytest.raises(ValueError, match="Residual identities"):
        check(b)


def test_residual_cannot_change_direction_or_hide_under_accepted(tmp_path):
    b = bundle(tmp_path); residual(b)
    b["categories_doc"]["residuals"][0]["direction"] = "FP"
    with pytest.raises(ValueError, match="Residual needs"):
        check(b)
    b["categories_doc"]["residuals"][0]["direction"] = "FN"
    b["categories_doc"]["categories"][0]["status"] = "accepted"
    with pytest.raises(ValueError, match="hide residuals"):
        check(b)


def test_twenty_one_fn_residuals_are_not_passed():
    rows = [dict(difference_id=str(i), direction="FN", impact=dict(
        checked=True, changes_definition_kill=False, changes_existing_dependency_facts=False,
        reason="checked", evidence=[{}])) for i in range(21)]
    states = [dict(status="accepted_with_residual")]
    assert gate_status(states, rows, []) == "blocked_residual_count_or_direction"
    assert gate_status(states, rows[:20], []) == "passed_with_bounded_FN_residuals"


def test_histogram_source_excerpt_must_match(tmp_path):
    b = bundle(tmp_path)
    event = dict(b["event"], source_excerpt="incorrect")
    with pytest.raises(ValueError, match="source excerpt"):
        histogram([event])


def test_prepare_does_not_overwrite_previous_selection(tmp_path):
    b = bundle(tmp_path)
    with pytest.raises(FileExistsError):
        prepare(b["alignment"], b["selection"].parent)
