"""NS-P1 authorized checkpoint boundary tests using only self-created files."""
import hashlib
from pathlib import Path
import pytest
import torch

from scripts.node_sem import checkpoint_io as cio
from scripts.DFG.experiments.common import tensor_digest


def _write(root, filename="initial.pt", payload=None):
    path = root / filename
    if payload is None:
        state = {"weight": torch.arange(6, dtype=torch.float32).view(2, 3)}
        payload = {"kind": "untrained_initial", "optimizer_steps": 0,
                   "state_dict": state, "state_sha256": tensor_digest(state)}
    torch.save(payload, str(path))
    ref = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if isinstance(payload, dict) and "state_sha256" in payload:
        ref["state_sha256"] = payload["state_sha256"]
    return path, ref


def test_authorized_self_created_sealed_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(cio, "GENERATED_ROOT", tmp_path)
    path, ref = _write(tmp_path)
    before = path.read_bytes()
    loaded = cio.load_checked(ref)
    assert loaded["optimizer_steps"] == 0
    assert tensor_digest(loaded["state_dict"]) == ref["state_sha256"]
    assert path.read_bytes() == before


def test_file_sha_checked_before_invalid_pickle_is_read(tmp_path, monkeypatch):
    monkeypatch.setattr(cio, "GENERATED_ROOT", tmp_path)
    path = tmp_path / "changed.pt"
    path.write_bytes(b"not a serialized object")
    with pytest.raises(ValueError, match="SHA mismatch before torch.load"):
        cio.load_checked({"path": str(path), "sha256": "0" * 64})


def test_state_reference_and_payload_digests_are_independently_checked(tmp_path, monkeypatch):
    monkeypatch.setattr(cio, "GENERATED_ROOT", tmp_path)
    _, ref = _write(tmp_path)
    ref["state_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="sealed reference"):
        cio.load_checked(ref)
    state = {"x": torch.ones(1)}
    _, bad = _write(tmp_path, "bad-state.pt",
                    {"state_dict": state, "state_sha256": "0" * 64})
    with pytest.raises(ValueError, match="payload"):
        cio.load_checked(bad)


def test_outside_path_and_symlink_escape_rejected(tmp_path, monkeypatch):
    allowed = tmp_path / "authorized"
    allowed.mkdir()
    monkeypatch.setattr(cio, "GENERATED_ROOT", allowed)
    outside, ref = _write(tmp_path)
    with pytest.raises(ValueError, match="authorized roots"):
        cio.load_checked(ref)
    link = allowed / "escape.pt"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="authorized roots"):
        cio.load_checked(dict(ref, path=str(link)))


@pytest.mark.parametrize("ref", [{}, {"path": "irrelevant", "sha256": ""}])
def test_incomplete_sealed_reference_rejected(ref):
    with pytest.raises(ValueError):
        cio.load_checked(ref)
