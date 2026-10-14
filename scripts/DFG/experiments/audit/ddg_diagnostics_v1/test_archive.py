"""Diagnostic archive guard tests; all mutations use pytest temporary files."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("diagnostic_archive_audit", Path(__file__).with_name("archive_audit.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def test_snapshot_unchanged(tmp_path):
    p = tmp_path / "source.py"
    p.write_bytes(b"original\n")
    before = audit.collect_snapshot([p])
    assert audit.compare_snapshot(before) == {"checked": 1, "unchanged": True, "changes": []}

@pytest.mark.parametrize("change", ["edit", "delete"])
def test_snapshot_detects_byte_drift_and_deleted_asset(tmp_path, change):
    p = tmp_path / "frozen.pt"
    p.write_bytes(b"original\n")
    before = audit.collect_snapshot([p])
    if change == "edit":
        p.write_bytes(b"changed\n")
    else:
        p.unlink()
    result = audit.compare_snapshot(before)
    assert not result["unchanged"]
    assert result["changes"][0]["path"] == str(p)
    assert result["changes"][0]["before"]["sha256"] != result["changes"][0]["after"]["sha256"]

def test_snapshot_deduplicates_file_identity(tmp_path):
    p = tmp_path / "one.json"
    p.write_text("{}")
    assert len(audit.collect_snapshot([p, str(p), p])) == 1

def test_missing_asset_is_explicit(tmp_path):
    p = tmp_path / "absent.pt"
    assert audit.file_record(p) == {"exists": False, "size": None, "sha256": None}

def test_output_does_not_overwrite_existing_audit(tmp_path):
    p = tmp_path / "audit.json"
    audit.write_new(p, {"old": True})
    with pytest.raises(FileExistsError):
        audit.write_new(p, {"old": False})
    assert audit.read_json(p) == {"old": True}

def test_manifest_resolves_relative_paths_without_guessing(tmp_path):
    data = {"graphs": {"E0": {"path": "E0/node.gpickle", "sha256": "abc"}},
            "feature": {"asset_hashes": {"/tmp/tokenizer.json": "def"}}}
    records = audit.manifest_assets(data, tmp_path, "manifest")
    assert records[str(tmp_path / "E0/node.gpickle")]["expected_sha256"] == "abc"
    assert records["/tmp/tokenizer.json"]["expected_sha256"] == "def"

def test_archive_path_escape_rejected(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        audit.checked_relative(tmp_path / "attempt", "../other/best.pt")

def test_archive_path_inside_root_is_resolved(tmp_path):
    assert audit.checked_relative(tmp_path, "fold_0/E1/best.pt") == tmp_path / "fold_0/E1/best.pt"

def test_fixed_pilot_identities_not_metric_selected():
    assert len(audit.PILOTS) == 7
    assert "reentrancy_author_node_fold8" in audit.PILOTS
    assert "access_control_author_node_fold7" in audit.PILOTS
    assert "access_control_author_node_fold8" in audit.PILOTS
    assert sum(p.endswith("fold0") for p in audit.PILOTS) == 4
