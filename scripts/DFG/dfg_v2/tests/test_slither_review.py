import copy
import json
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2.slither_review import (
    prepare, sample_other, sha256, validate,
)


def row(i, task="R", layer="L1", direction="FP"):
    return dict(difference_id="%s-%s-%s-%04d" % (task, layer, direction, i),
                task=task, layer=layer, direction=direction, category="other")


def test_fixed_seed_all_small_and_thirty_large_groups():
    rows = [row(i) for i in range(55)] + [row(i, task="A") for i in range(4)]
    selected, strata = sample_other(rows)
    assert len(selected) == 34
    assert [s["selected"] for s in strata] == [4, 30]
    assert sample_other(list(reversed(rows))) == (selected, strata)
    assert selected == sample_other(rows)[0]
    assert selected != sample_other(rows, seed=1)[0]
    assert all(x["category"] == "other" for x in selected)


def test_non_other_not_sampled_and_duplicates_rejected():
    normal = row(0)
    excluded = dict(row(1), category="entry_initialization")
    assert sample_other([normal, excluded])[0] == [normal]
    with pytest.raises(ValueError, match="Duplicate"):
        sample_other([normal, normal])


def bundle(tmp_path):
    source = tmp_path / "c.sol"
    source.write_text("contract C { uint x; }\n")
    event = dict(row(1), source_path=str(source), source_sha256=sha256(source))
    alignment = tmp_path / "alignment.json"
    alignment.write_text(json.dumps(dict(differences=[event])))
    result = prepare(alignment, tmp_path / "review")
    selection = tmp_path / "review/selection.json"
    decisions = tmp_path / "decisions.json"
    content = dict(selection_sha256=sha256(selection), decisions=[
        dict(difference_id=event["difference_id"], verdict="unclear", reason="No verified counterpart.",
             evidence=dict(inspected_source=source.read_text()))])
    decisions.write_text(json.dumps(content))
    return selection, decisions, content, source, alignment


def test_valid_explicit_review_and_no_automatic_verdict(tmp_path):
    selection, decisions, _, _, _ = bundle(tmp_path)
    assert json.loads(selection.read_text())["verdicts_assigned"] is False
    result = validate(selection, decisions)
    assert result["reviewed"] == 1
    assert result["counts"][0]["verdict"] == "unclear"
    assert result["semantic_verdicts_are_analyst_supplied"] is True
    assert result["prompt7_gate"] == "no_sampled_v2_defect"


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown_verdict", "empty_reason",
                                   "empty_evidence", "wrong_selection", "defect_no_pattern"])
def test_reject_incomplete_or_unbound_decisions(tmp_path, change):
    selection, decisions, content, _, _ = bundle(tmp_path)
    if change == "missing":
        content["decisions"] = []
    elif change == "duplicate":
        content["decisions"] *= 2
    elif change == "unknown_verdict":
        content["decisions"][0]["verdict"] = "correct"
    elif change == "empty_reason":
        content["decisions"][0]["reason"] = " "
    elif change == "empty_evidence":
        content["decisions"][0]["evidence"] = {}
    elif change == "wrong_selection":
        content["selection_sha256"] = "bad"
    else:
        content["decisions"][0]["verdict"] = "v2_defect"
    decisions.write_text(json.dumps(content))
    with pytest.raises(ValueError):
        validate(selection, decisions)


def test_defect_blocks_gate_and_preserves_pattern(tmp_path):
    selection, decisions, content, _, _ = bundle(tmp_path)
    content["decisions"][0].update(verdict="v2_defect", pattern="synthetic_test_shape")
    decisions.write_text(json.dumps(content))
    result = validate(selection, decisions)
    assert result["prompt7_gate"] == "blocked_v2_defect"
    assert len(result["defect_patterns"]["synthetic_test_shape"]) == 1


@pytest.mark.parametrize("target", ["selection", "source", "alignment"])
def test_reject_changed_bound_input(tmp_path, target):
    selection, decisions, _, source, alignment = bundle(tmp_path)
    paths = dict(selection=selection, source=source, alignment=alignment)
    with paths[target].open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="modified"):
        validate(selection, decisions)


def test_refuse_overwriting_selection(tmp_path):
    selection, _, _, _, alignment = bundle(tmp_path)
    with pytest.raises(FileExistsError):
        prepare(alignment, selection.parent)

def test_comparator_artifact_requires_recompute(tmp_path):
    selection, decisions, content, _, _ = bundle(tmp_path)
    content["decisions"][0].update(verdict="comparator_artifact")
    decisions.write_text(json.dumps(content))
    result = validate(selection, decisions)
    assert result["prompt7_gate"] == "pending_comparator_recompute"


from scripts.DFG.dfg_v2.slither_review import (
    FOLLOWUP_VERSION, DEFAULT_PREDICATES, evidence_for, digest_json,
    prepare_followup, sample_followup,
)


def complete_event(i, source, **overrides):
    event = dict(row(i), source_path=str(source), source_sha256=sha256(source),
                 span=[0, 8], source_excerpt="contract",
                 primary=dict(name="x", kind="READ", span=[0, 8],
                              evidence=[dict(declaration=[9, 15])]),
                 nearby_candidate=[dict(name="x", span=[1, 2])],
                 nearby_reference=[dict(name="x", span=[0, 8])])
    event.update(overrides)
    return event


def followup_bundle(tmp_path):
    source = tmp_path / "followup.sol"
    source.write_text("contract C { uint x; }\n")
    original = complete_event(1, source)
    old_alignment = tmp_path / "old_alignment.json"
    old_alignment.write_text(json.dumps(dict(differences=[original])))
    old_dir = tmp_path / "old"
    prepare(old_alignment, old_dir)
    old_decision = dict(
        difference_id=original["difference_id"], verdict="slither_convention",
        reason="Old result had no scope label.", evidence=dict(original_fact="Preserve me."))
    old_decisions = tmp_path / "old_decisions.json"
    old_decisions.write_text(json.dumps(dict(
        selection_sha256=sha256(old_dir / "selection.json"),
        decisions=[old_decision])))
    new_alignment = tmp_path / "new_alignment.json"
    remaining = complete_event(2, source)
    matched = complete_event(3, source, category="aggregate_base_use")
    new_alignment.write_text(json.dumps(
        dict(differences=[remaining, matched],
             unit_comparison=dict(eliminated_fp=1))))
    probe = tmp_path / "probes.json"
    probe.write_text(json.dumps(dict(cases=[dict(
        name="array", source="a[i] = v", read=[], written=["a"])])))
    output = tmp_path / "followup"
    prepare_followup(new_alignment, old_dir / "selection.json", old_decisions,
                     output, conventions=[probe])
    selection_path = output / "selection.json"
    selection = json.loads(selection_path.read_text())
    decisions = []
    for records in selection["review_sets"].values():
        for record in records:
            decision = dict(
                review_id=record["review_id"], difference_id=record["difference_id"],
                verdict="unclear", reason="Inspect source and exact evidence.",
                evidence=evidence_for(record["event"]))
            if record["purpose"] == "reclassification":
                decision["previous_decision"] = record["previous_decision"]
            decisions.append(decision)
    document = dict(version=FOLLOWUP_VERSION,
                    selection_sha256=sha256(selection_path), decisions=decisions)
    decisions_path = output / "decisions.json"
    decisions_path.write_text(json.dumps(document))
    return selection_path, decisions_path, document, probe, new_alignment


def save_decisions(path, document):
    path.write_text(json.dumps(document))


def json_evidence(path, pointer, value):
    return dict(path=str(path), sha256=sha256(path), pointer=pointer,
                value=value, interpretation="Directly inspected this recorded example.")


def test_followup_threshold_all_150_and_sample_151():
    rows = [row(i) for i in range(150)]
    all_rows = sample_followup(rows)
    assert len(all_rows["remaining_other"]) == 150
    assert all_rows["other_mode"] == "all"
    assert all_rows["other_unreviewed"] == 0
    sampled = sample_followup(rows + [row(150)])
    assert len(sampled["remaining_other"]) == 30
    assert sampled["other_mode"] == "30_per_stratum"
    assert sampled["other_unreviewed"] == 121
    assert sampled == sample_followup(list(reversed(rows + [row(150)])))


def test_followup_uses_total_threshold_but_stratified_samples():
    rows = [row(i) for i in range(100)] + [row(i, task="A") for i in range(60)]
    result = sample_followup(rows)
    assert result["other_population"] == 160
    assert len(result["remaining_other"]) == 60
    assert [s["selected"] for s in result["other_strata"]] == [30, 30]


def test_followup_predicates_sample_five_deterministically_including_small_and_zero():
    rows = [dict(row(i), category="first") for i in range(12)]
    rows += [dict(row(i, task="A"), category="second") for i in range(2)]
    result = sample_followup(rows, predicates=("first", "second", "zero"))
    assert result == sample_followup(list(reversed(rows)), ("first", "second", "zero"))
    assert [p["selected"] for p in result["predicate_strata"]] == [5, 2, 0]
    assert len(result["predicate_checks"]) == 7
    assert result["other_population"] == 0


@pytest.mark.parametrize("predicates", [("x", "x"), ("other",), ("",), (1,)])
def test_followup_invalid_predicate_list_rejected(predicates):
    with pytest.raises(ValueError, match="predicate"):
        sample_followup([], predicates)


def test_followup_selection_preserves_old_facts_and_assigns_no_verdicts(tmp_path):
    selection_path, decisions_path, document, _, _ = followup_bundle(tmp_path)
    selection = json.loads(selection_path.read_text())
    assert selection["verdicts_assigned"] is False
    assert selection["human_edge_review"] is False
    assert {k: len(v) for k, v in selection["review_sets"].items()} == {
        "reclassification": 1, "remaining_other": 1, "predicate_checks": 1}
    record = selection["review_sets"]["reclassification"][0]
    assert record["previous_decision"]["evidence"] == {"original_fact": "Preserve me."}
    result = validate(selection_path, decisions_path)
    assert result["reviewed"] == 3
    assert result["unclear_count"] == 3
    assert result["prompt7_gate"] == "unresolved_analyst_findings"
    assert result["evidence_binding_does_not_prove_semantic_correctness"] is True


def test_followup_scope_limit_requires_exact_bound_documented_basis(tmp_path):
    selection, decisions, content, _, _ = followup_bundle(tmp_path)
    scope_doc = tmp_path / "scope.md"
    scope_doc.write_text("No implicit legacy aliases without version evidence.\n")
    item = content["decisions"][0]
    item["verdict"] = "v2_scope_limit"
    item["scope_basis"] = dict(path=str(scope_doc), sha256=sha256(scope_doc),
                               quote="No implicit legacy aliases without version evidence.")
    save_decisions(decisions, content)
    assert validate(selection, decisions)["reviewed"] == 3
    item["scope_basis"]["quote"] = "Full Solidity supported."
    save_decisions(decisions, content)
    with pytest.raises(ValueError, match="quote"):
        validate(selection, decisions)


def test_followup_convention_requires_frozen_probe_and_exact_fact(tmp_path):
    selection, decisions, content, probe, _ = followup_bundle(tmp_path)
    item = content["decisions"][2]
    item.update(verdict="slither_convention",
                convention_evidence=[json_evidence(
                    probe, "/cases/0", json.loads(probe.read_text())["cases"][0])])
    save_decisions(decisions, content)
    assert validate(selection, decisions)["reviewed"] == 3
    item["convention_evidence"][0]["value"]["read"] = ["a"]
    save_decisions(decisions, content)
    with pytest.raises(ValueError, match="bound JSON"):
        validate(selection, decisions)


def test_followup_convention_cannot_use_unregistered_evidence_file(tmp_path):
    selection, decisions, content, probe, _ = followup_bundle(tmp_path)
    fake = tmp_path / "unregistered_probe.json"
    fake.write_text(probe.read_text())
    item = content["decisions"][2]
    item.update(verdict="slither_convention", convention_evidence=[
        json_evidence(fake, "/cases/0", json.loads(fake.read_text())["cases"][0])])
    save_decisions(decisions, content)
    with pytest.raises(ValueError, match="frozen probe"):
        validate(selection, decisions)


@pytest.mark.parametrize("target", [
    "primary", "nearby_candidate", "nearby_reference", "span", "source_sha256",
    "source_path", "source_excerpt", "event_sha256", "missing", "extra",
    "old_fact", "wrong_id", "old_reuse_on_new",
])
def test_followup_rejects_fact_tampering(tmp_path, target):
    selection, decisions, content, _, _ = followup_bundle(tmp_path)
    item = content["decisions"][0]
    if target == "old_fact":
        item["previous_decision"]["evidence"]["original_fact"] = "Changed."
    elif target == "wrong_id":
        item["difference_id"] = "another"
    elif target == "old_reuse_on_new":
        content["decisions"][1]["previous_decision"] = item["previous_decision"]
    elif target == "missing":
        item["evidence"] = {"note": "I inspected this."}
    elif target == "extra":
        item["evidence"]["unbound_statement"] = "Not a frozen fact."
    else:
        item["evidence"][target] = "tampered"
    save_decisions(decisions, content)
    with pytest.raises(ValueError):
        validate(selection, decisions)


@pytest.mark.parametrize("target", [
    "old_selection", "old_decisions", "old_alignment", "old_selection_seal",
    "alignment", "convention",
])
def test_followup_rejects_modified_bound_old_and_new_inputs(tmp_path, target):
    selection, decisions, _, _, _ = followup_bundle(tmp_path)
    bundle_data = json.loads(selection.read_text())
    binding = (bundle_data["convention_inputs"][0] if target == "convention"
               else bundle_data["inputs"][target])
    with Path(binding["path"]).open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="modified"):
        validate(selection, decisions)


def test_followup_historical_artifact_resolution_must_bind_current_comparison(tmp_path):
    selection, decisions, content, _, alignment = followup_bundle(tmp_path)
    item = content["decisions"][0]
    item["verdict"] = "comparator_artifact"
    save_decisions(decisions, content)
    assert validate(selection, decisions)["prompt7_gate"] == "pending_comparator_recompute"
    item["artifact_resolution"] = json_evidence(
        alignment, "/unit_comparison", dict(eliminated_fp=1))
    save_decisions(decisions, content)
    assert validate(selection, decisions)["prompt7_gate"] == "unresolved_analyst_findings"
    item["artifact_resolution"]["value"]["eliminated_fp"] = 99
    save_decisions(decisions, content)
    with pytest.raises(ValueError, match="bound JSON"):
        validate(selection, decisions)


def test_followup_new_artifact_is_not_cleared_by_historical_resolution(tmp_path):
    selection, decisions, content, _, alignment = followup_bundle(tmp_path)
    content["decisions"][1].update(
        verdict="comparator_artifact",
        artifact_resolution=json_evidence(alignment, "/unit_comparison",
                                          dict(eliminated_fp=1)))
    save_decisions(decisions, content)
    assert validate(selection, decisions)["prompt7_gate"] == "pending_comparator_recompute"


def test_followup_defect_gate_and_pattern(tmp_path):
    selection, decisions, content, _, _ = followup_bundle(tmp_path)
    item = content["decisions"][1]
    item.update(verdict="v2_defect", pattern="test_pattern")
    save_decisions(decisions, content)
    result = validate(selection, decisions)
    assert result["prompt7_gate"] == "blocked_v2_defect"
    assert result["defect_patterns"] == {"test_pattern": [item["review_id"]]}


def test_followup_duplicate_and_missing_review_ids_rejected(tmp_path):
    selection, decisions, content, _, _ = followup_bundle(tmp_path)
    original = copy.deepcopy(content)
    content["decisions"].append(copy.deepcopy(content["decisions"][0]))
    save_decisions(decisions, content)
    with pytest.raises(ValueError, match="every review identity"):
        validate(selection, decisions)
    content = original
    content["decisions"].pop()
    save_decisions(decisions, content)
    with pytest.raises(ValueError, match="every review identity"):
        validate(selection, decisions)


def test_followup_refuses_overwrite(tmp_path):
    selection, _, _, _, alignment = followup_bundle(tmp_path)
    frozen = json.loads(selection.read_text())
    with pytest.raises(FileExistsError):
        prepare_followup(
            alignment, frozen["inputs"]["old_selection"]["path"],
            frozen["inputs"]["old_decisions"]["path"], selection.parent)


def test_event_digest_covers_other_identity_fields(tmp_path):
    source = tmp_path / "x.sol"
    source.write_text("contract C {}")
    original = complete_event(0, source)
    changed = dict(original, name="misleading_name")
    assert evidence_for(original)["event_sha256"] != evidence_for(changed)["event_sha256"]
    assert digest_json({"a": 1, "b": 2}) == digest_json({"b": 2, "a": 1})


@pytest.mark.parametrize("pointer", ["/cases/-1", "/cases/00", "/cases/+0", "/missing"])
def test_followup_rejects_ambiguous_or_missing_json_pointer(tmp_path, pointer):
    selection, decisions, content, probe, _ = followup_bundle(tmp_path)
    item = content["decisions"][2]
    item.update(verdict="slither_convention",
                convention_evidence=[json_evidence(
                    probe, pointer, json.loads(probe.read_text())["cases"][0])])
    save_decisions(decisions, content)
    with pytest.raises(ValueError, match="pointer"):
        validate(selection, decisions)


@pytest.mark.parametrize("verdict,basis", [
    ("slither_convention", "convention_evidence"),
    ("v2_scope_limit", "scope_basis"),
])
def test_followup_new_labels_require_explicit_bound_basis(tmp_path, verdict, basis):
    selection, decisions, content, _, _ = followup_bundle(tmp_path)
    item = content["decisions"][0]
    item["verdict"] = verdict
    item.pop(basis, None)
    save_decisions(decisions, content)
    with pytest.raises(ValueError):
        validate(selection, decisions)


def test_followup_resample_rejects_resealed_different_primary(tmp_path):
    selection, decisions, _, _, _ = followup_bundle(tmp_path)
    data = json.loads(selection.read_text())
    data["review_sets"]["remaining_other"][0]["event"]["primary"]["name"] = "changed"
    selection.write_text(json.dumps(data))
    seal_path = selection.with_name("selection.seal.json")
    seal = json.loads(seal_path.read_text())
    seal["selection_sha256"] = sha256(selection)
    seal_path.write_text(json.dumps(seal))
    with pytest.raises(ValueError, match="frozen exact selections"):
        validate(selection, decisions)


def test_followup_zero_population_is_explicit_without_automatic_verdict(tmp_path):
    source = tmp_path / "empty.sol"
    source.write_text("contract C {}")
    alignment = tmp_path / "alignment.json"
    alignment.write_text(json.dumps(dict(differences=[])))
    prepare(alignment, tmp_path / "old")
    old_decisions = tmp_path / "old_decisions.json"
    old_decisions.write_text(json.dumps(dict(
        selection_sha256=sha256(tmp_path / "old/selection.json"), decisions=[])))
    result = prepare_followup(alignment, tmp_path / "old/selection.json", old_decisions,
                              tmp_path / "new")
    assert result["selected_by_purpose"] == {
        "reclassification": 0, "remaining_other": 0, "predicate_checks": 0}
    assert result["sampling"]["other_unreviewed"] == 0
    selection = tmp_path / "new/selection.json"
    decisions = tmp_path / "new/decisions.json"
    decisions.write_text(json.dumps(dict(
        version=FOLLOWUP_VERSION, selection_sha256=sha256(selection), decisions=[])))
    outcome = validate(selection, decisions)
    assert outcome["reviewed"] == 0
    assert outcome["prompt7_gate"] == "no_reviewed_v2_defect"
    assert outcome["evidence_binding_does_not_prove_semantic_correctness"] is True
