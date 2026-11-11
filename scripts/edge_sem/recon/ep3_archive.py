"""Explicit read-only EP2 loading after the approved EP3 builder revision.

Checks the EP2 receipt and recorded source hashes, using the pre-EP3 snapshots
only for the two explicitly changed files. Production build_f4.load_edges
continues to require the current implementation SHA.
"""
from pathlib import Path
from collections import Counter
from .common import ROOT, read, checked
from .ep3_common import OUT

EP2 = ROOT / "scripts/edge_sem/artifacts/ep2_v1"


def _check_source(record, snapshots):
    replacement = snapshots.get(record["path"])
    if replacement is None:
        return checked(record)
    if replacement["sha256"] != record["sha256"]:
        raise ValueError("Archived implementation identity differs")
    return checked(replacement)


def load_ep2_edges(manifest_path):
    path = Path(manifest_path).resolve()
    if path not in [EP2/t/"manifest.json" for t in ("reentrancy_node","access_control_node")]:
        raise ValueError("Only the two recorded EP2 manifests may be archived")
    before = read(OUT/"before.json")
    verification = read(checked(before["historical_verification"]))
    if not verification["passed"]:
        raise ValueError("Historical EP2 verification did not pass")
    summary = read(checked(verification["summary"]))
    checked(verification["report"])
    snapshots = {r["original"]["path"]:r["snapshot"] for r in before["authorized_source_changes"]}
    if set(snapshots) != {str(ROOT/p) for p in
            ("scripts/edge_sem/build_f4.py","scripts/edge_sem/tests/test_build_f4_model.py")}:
        raise ValueError("Unexpected archive exceptions")
    for record in summary["source_refs"]:
        _check_source(record,snapshots)
    task = path.parent.name
    expected = summary["tasks"][task]["manifest"]
    if Path(expected["path"]) != path:
        raise ValueError("Historical manifest identity differs")
    manifest = read(checked(expected))
    if manifest["task_id"] != task or manifest["version"] != "edgesem-f4-ep2-v1":
        raise ValueError("Unexpected historical task or version")
    for record in manifest["implementation"]:
        _check_source(record,snapshots)
    for record in list(manifest["source_refs"].values())+list(manifest["inputs"]["graphs"].values()):
        checked(record)
    for name in ("plan","store","audit"):
        checked(manifest["inputs"][name])
    checked(manifest["audit"])
    rows = [__import__("json").loads(s) for s in checked(manifest["edges"]).read_text(encoding="utf8").splitlines()]
    if len(rows)!=manifest["row_count"] or dict(Counter(r["relation"] for r in rows))!=manifest["counts_by_relation"]:
        raise ValueError("Historical edge counts differ")
    return rows
