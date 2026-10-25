"""Synthetic supplemental review integrity; no real verdicts are filled."""
import copy
import json
from pathlib import Path

import pytest

from scripts.DFG.dfg_v2 import review_sheet as rs, review_supplement as supplement
from scripts.DFG.dfg_v2.score_review import score_review
from scripts.DFG.integration.io import sha256, write_json
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.tests.test_review_sheet import fake_store, read_rows, NAME, fixture


def prepare(tmp_path, monkeypatch):
    store_path = fake_store(tmp_path, monkeypatch)
    exported = rs.export_review(store_path, tmp_path / "original", files_per_task=1)
    seal_path = Path(exported["seal"])
    seal = json.loads(seal_path.read_text())
    proof_path = seal_path.parent / seal["provenance"]["path"]
    proof = json.loads(proof_path.read_text())
    # Synthetic prior sample excludes DDU; task cohort remains the same.
    proof["rows"] = [p for p in proof["rows"] if p["relation"] != rs.DATA_DEF_USE]
    rows = [r for r in read_rows(Path(exported["csv"])) if r["relation"] != rs.DATA_DEF_USE]
    for name in ("review_sheet.csv", "review_sheet.blank.csv"):
        (seal_path.parent / name).write_bytes(rs._csv_bytes(rows))
    write_json(proof_path, proof)
    seal["provenance"]["sha256"] = sha256(proof_path)
    seal["row_count"] = len(rows)
    seal["blank_csv"]["sha256"] = sha256(seal_path.parent / seal["blank_csv"]["path"])
    seal["csv_sha256"] = seal["blank_csv"]["sha256"]
    write_json(seal_path, seal)
    document = json.loads(store_path.read_text())
    manifest = json.loads(Path(document["input_manifest"]["path"]).read_text())
    tasks = {}
    for task, rec in document["tasks"].items():
        entry = rec["graphs"]["F3"]
        graph = read_graph(Path(entry["graph"]["path"]))
        audit = json.loads(Path(entry["audit"]["path"]).read_text())
        source, target, key, attrs = next(
            e for e in graph.edges(keys=True, data=True) if e[3]["edge_type"] == rs.DATA_DEF_USE)
        record = dict(source=source, target=target, key=key,
            relation=rs.DATA_DEF_USE, attributes=attrs, file=NAME,
            source_sha256=manifest["tasks"][task]["sources"][NAME]["sha256"],
            evidence=audit["layers"]["L1"]["evidence"])
        tasks[task] = dict(F3=dict(new_graph=entry["graph"], new_audit=entry["audit"],
                                   added=[record], added_edges=1))
    diff = dict(version=supplement.DIFF_VERSION, status="accepted",
        new_store=dict(path=str(store_path), sha256=sha256(store_path)),
        review=dict(seal=dict(path=str(seal_path), sha256=sha256(seal_path))), tasks=tasks)
    diff_path = tmp_path / "store_diff.json"
    write_json(diff_path, diff)
    write_json(diff_path.with_name("store_diff.seal.json"), dict(
        version=supplement.DIFF_VERSION, status="accepted", report_sha256=sha256(diff_path)))
    calls = []
    def validate(path, review_seal):
        calls.append((str(path), str(review_seal)))
        return dict(status="verified", new_edges_outside_review=2)
    monkeypatch.setattr(supplement, "verify_equivalence", validate)
    return diff_path, calls


def test_all_added_edges_blank_same_schema_and_original_scorer_works(tmp_path, monkeypatch):
    diff, calls = prepare(tmp_path, monkeypatch)
    before = {p.name: p.read_bytes() for p in (tmp_path / "original").iterdir()}
    result = supplement.export_supplement(diff, tmp_path / "review_v1b")
    assert result["rows"] == 2
    rows = read_rows(Path(result["csv"]))
    assert [r["review_id"] for r in rows] == ["S000001", "S000002"]
    assert [r["task"] for r in rows] == ["alpha_contract", "beta_contract"]
    assert all(r["verdict"] == r["note"] == "" for r in rows)
    assert all(r["relation"] == rs.DATA_DEF_USE for r in rows)
    score = score_review(result["csv"], result["seal"])
    assert score["row_count"] == 2 and not score["completed"]
    assert score["relations"][rs.DATA_DEF_USE]["blank"] == 2
    assert score["relations"][rs.DATA_DEF_USE]["correct_proportion"] is None
    assert calls and calls[0][0] == str(diff)
    assert before == {p.name: p.read_bytes() for p in (tmp_path / "original").iterdir()}
    again = supplement.export_supplement(diff, tmp_path / "again")
    assert Path(result["csv"]).read_bytes() == Path(again["csv"]).read_bytes()
    with pytest.raises(FileExistsError):
        supplement.export_supplement(diff, tmp_path / "again")


def test_bad_diff_hash_or_rejected_equivalence_no_output(tmp_path, monkeypatch):
    diff, _ = prepare(tmp_path, monkeypatch)
    raw = diff.read_bytes()
    diff.write_bytes(raw + b" ")
    with pytest.raises(ValueError):
        supplement.export_supplement(diff, tmp_path / "bad_hash")
    assert not (tmp_path / "bad_hash").exists()
    diff.write_bytes(raw)
    def reject(*args):
        raise ValueError("equivalence rejected")
    monkeypatch.setattr(supplement, "verify_equivalence", reject)
    with pytest.raises(ValueError, match="equivalence rejected"):
        supplement.export_supplement(diff, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_added_rows_validate_identity_evidence_source_and_original_exclusion(tmp_path):
    graph, audit, ref = fixture(tmp_path)
    source, target, key, attrs = next(
        e for e in graph.edges(keys=True, data=True) if e[3]["edge_type"] == rs.DATA_DEF_USE)
    rec = dict(source=source, target=target, key=key, attributes=attrs,
        relation=rs.DATA_DEF_USE, file=NAME, source_sha256=ref["sha256"],
        evidence=audit["layers"]["L1"]["evidence"])
    def call(records, old=()):
        return supplement._added_rows("fake", graph, audit,
                                      dict(sources={NAME: ref}), records, set(old))
    assert len(call([rec])[0]) == 1
    with pytest.raises(ValueError, match="Duplicate"):
        call([rec, rec])
    with pytest.raises(ValueError, match="original review"):
        call([rec], [("fake", source, target, key)])
    for field, value, message in [
        ("relation", rs.ENV_FLOW, "DATA_DEF_USE"),
        ("key", 99, "missing"),
        ("file", "other.sol", "identity"),
        ("source_sha256", "0" * 64, "SHA"),
        ("attributes", dict(attrs, unknown=True), "attributes"),
        ("evidence", [], "evidence"),
    ]:
        bad = copy.deepcopy(rec)
        bad[field] = value
        with pytest.raises(ValueError, match=message):
            call([bad])


def test_export_rejects_missing_addition_even_with_passing_diff_stub(tmp_path, monkeypatch):
    diff, _ = prepare(tmp_path, monkeypatch)
    document = json.loads(diff.read_text())
    document["tasks"]["alpha_contract"]["F3"].update(added=[], added_edges=0)
    write_json(diff, document)
    seal_path = diff.with_name("store_diff.seal.json")
    seal = json.loads(seal_path.read_text())
    seal["report_sha256"] = sha256(diff)
    write_json(seal_path, seal)
    with pytest.raises(ValueError, match="all new"):
        supplement.export_supplement(diff, tmp_path / "incomplete")
    assert not (tmp_path / "incomplete").exists()


def test_supplement_immutable_csv_field_still_rejected(tmp_path, monkeypatch):
    diff, _ = prepare(tmp_path, monkeypatch)
    result = supplement.export_supplement(diff, tmp_path / "review_v1b")
    table = Path(result["csv"])
    rows = read_rows(table)
    rows[0]["src_line"] = "999"
    table.write_bytes(rs._csv_bytes(rows))
    with pytest.raises(ValueError, match="Immutable"):
        score_review(table, result["seal"])
