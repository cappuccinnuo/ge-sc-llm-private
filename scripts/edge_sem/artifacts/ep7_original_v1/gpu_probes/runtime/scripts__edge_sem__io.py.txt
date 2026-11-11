"""Task-independent, exclusive-write EdgeSem provenance helpers.

Extracted from recon/common.py for production use; no historical batch binding.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def ref(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return dict(path=str(path), sha256=h.hexdigest(), bytes=path.stat().st_size)

def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))

def checked(row):
    p = Path(row["path"])
    if ref(p)["sha256"] != row["sha256"]:
        raise ValueError("SHA mismatch: " + str(p))
    return p

def write(path, value):
    path = Path(path).resolve()
    if ROOT / "scripts/edge_sem" not in path.parents:
        raise ValueError("Output outside EdgeSem")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
