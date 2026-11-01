"""User-authorized local checkpoint loading with immediate checksum checks.

NS-P1 approval (2026-11-01): only sealed local 8H prepared initial states,
8H run checkpoints, and NodeSem-generated sealed files. PyTorch 1.8 uses
pickle; this is an explicit trust boundary, not a safe unpickler.
"""
import hashlib
import re
from pathlib import Path

import torch
from scripts.DFG.experiments.common import tensor_digest

ROOT = Path(__file__).resolve().parents[2]
H8_ROOT = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1"
GENERATED_ROOT = ROOT / "scripts/node_sem/artifacts"


def _allowed(path):
    for root in (H8_ROOT / "prepared_attempt3", H8_ROOT / "runs", GENERATED_ROOT):
        try:
            path.relative_to(root.resolve())
            return True
        except ValueError:
            pass
    return False


def load_checked(reference, map_location="cpu"):
    """Hash the same open file immediately before authorized deserialization."""
    if not isinstance(reference, dict) or set(("path", "sha256")) - set(reference):
        raise ValueError("Checkpoint requires a sealed path/SHA reference")
    expected = reference["sha256"]
    if not isinstance(expected, str) or re.fullmatch("[0-9a-f]{64}", expected) is None:
        raise ValueError("Invalid checkpoint SHA256")
    path = Path(reference["path"]).resolve(strict=True)
    if not _allowed(path) or not path.is_file():
        raise ValueError("Checkpoint outside the explicitly authorized roots")
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError("Checkpoint file SHA mismatch before torch.load")
        stream.seek(0)
        result = torch.load(stream, map_location=map_location)
    if not isinstance(result, dict):
        raise ValueError("Checkpoint payload must be a dictionary")
    if "state_dict" in result:
        actual = tensor_digest(result["state_dict"])
        if result.get("state_sha256") != actual:
            raise ValueError("Checkpoint tensor digest differs from payload")
        if "state_sha256" in reference and reference["state_sha256"] != actual:
            raise ValueError("Checkpoint tensor digest differs from sealed reference")
    elif "state_sha256" in reference:
        raise ValueError("Checkpoint has no state_dict")
    return result
