"""Read the approved local index and verify candidate byte changes from on-disk receipts."""
from collections import Counter
import hashlib
from pathlib import Path

from population import CP5, OUT, load
from compile_repair.core.store import read_checked_json, sha256
from compile_repair.rules.dependencies import OfflineIndex
from compile_repair.toolchain.project import import_directives

POLICIES = ("latest", "oldest", "closest")


def verified_index():
    auth = load(CP5 / "d23/authorization.json")
    request = read_checked_json(CP5 / "d23_download_request.json", auth["request_sha256"])
    summary = load(OUT / "download_summary.json")
    root = Path(auth["storage"])
    catalog = read_checked_json(root / "archives.json", summary["catalog_sha256"])
    db = OfflineIndex(root / "index")
    expected = {(p,v["version"]):v for p,desc in request["by_package"].items() for v in desc["releases"]}
    assert set(expected) == {(r["package"],r["version"]) for r in catalog["releases"]}
    assert set(expected) == {(name, v) for name, versions in db.packages.items() for v in versions}
    assert db.seal["releases"] == len(catalog["releases"]) == len(expected) == 172
    assert db.seal["archive_catalog_sha256"] == summary["catalog_sha256"]
    for r in catalog["releases"]:
        key = r["package"], r["version"]
        release = db.packages[key[0]][key[1]]
        assert r["verified"] and r["integrity"] == expected[key]["integrity"] == release["integrity"]
        assert r["url"] == expected[key]["registry_url"] and r["sha256"] == release["archive_sha256"]
    return db


def verify_source(path, proof):
    raw = Path(path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == proof["result_sha256"] and len(raw) == proof["result_length"]
    edits = proof["changes"]
    for edit in reversed(edits):
        assert edit["new"]["encoding"] == edit["old"]["encoding"] == "hex"
        old, new = bytes.fromhex(edit["old"]["data"]), bytes.fromhex(edit["new"]["data"])
        start, end = edit["start"], edit["end"]
        assert end - start == len(old) and raw[start:start + len(new)] == new
        raw = raw[:start] + old + raw[start+len(new):]
        if edit["step"] == "relative_import":
            assert any((r["literal_start"]+1, r["literal_end"]-1) == (start, end)
                       and r["literal_hex"] == old.hex() for r in import_directives(raw))
        elif edit["step"] == "dependency":
            assert not old and start == end == 0 and proof["level"] == "additive"
        else:
            raise ValueError("Unexpected change in an accepted CP5 step: " + edit["step"])
    assert len(raw) == proof["original_length"] and hashlib.sha256(raw).hexdigest() == proof["original_sha256"]
    if proof["level"] == "additive":
        assert not raw and len(edits) == 1 and edits[0]["step"] == "dependency"
    return len(edits)


def steps_facts(directory, uid, result):
    folder = directory / "units" / uid
    path = folder / "repair_steps.json"
    steps = load(path) if path.is_file() else []
    accepted = [r for r in steps if r.get("accepted")]
    counts, files, releases = Counter(), {}, {}
    for step in accepted:
        ref = directory / step["receipt"]
        attempt = load(ref)
        for name, proof in attempt["provenance"].items():
            counts[proof["level"]] += 1
            counts["edits_checked"] += verify_source(name, proof)
        files.update(step.get("files", {}))
        releases.update(step.get("releases", {}))
    combos = [dict(ordinal=r["combination_ordinal"], d3=r["d3_verified"], accepted=r["accepted"],
                   releases={k:v["version"] for k,v in r["releases"].items()}, receipt=r["receipt"])
              for r in steps if "combination_ordinal" in r]
    assert [r["ordinal"] for r in combos] == list(range(1, len(combos)+1))
    first = next((r["ordinal"] for r in combos if r["d3"]), None)
    selected = next((r["ordinal"] for r in reversed(combos) if r["d3"] and r["accepted"]), None)
    checks = [r for r in steps if r.get("operation") == "candidate_checks"]
    truncated = "dependency_search_truncated" in result.flags
    if checks:
        assert checks[-1]["compiled_combinations"] == len(combos) and checks[-1]["first_d3_combination"] == first
        assert truncated == any(r["truncated"] for r in checks)
    good = result.status == "success"
    if good:
        last = result.attempts[-1]
        assert last["solc"]["returncode"] == 0 and last["slither"]["d3"] and last["slither"]["graph_usable"]
        assert sha256(folder/"graph.json") == last["slither"]["graph_sha256"]
    return dict(d3=good, accepted_steps=[r["step"] for r in accepted],
                last_step=accepted[-1]["step"] if accepted else 1, releases=releases, added_files=files,
                mechanical=counts, combinations=combos, compiled_combinations=len(combos), first_d3=first,
                selected_ordinal=selected, truncated=truncated,
                step3_seconds=sum(r["elapsed_seconds"] for r in checks),
                result_path=str(folder/"result.json"), result_sha256=sha256(folder/"result.json"),
                steps_sha256=sha256(path) if path.is_file() else None)


def lock_reference(target, facts, db):
    """Only called after masked repair. Compare the closure actually used to each locked release."""
    reference = {}
    for pending in target["pending"].values():
        keys = {(p,v) for tier,p,v in pending["manifest_evidence"] if tier == "T1"}
        assert len(keys) == 1
        key, = keys
        reference.setdefault(key,set()).update(pending["paths"])
    if not reference:
        raise ValueError("Masked T1 reference has no lock evidence")
    matches = {}
    for (name, pin), paths in sorted(reference.items()):
        candidate = facts["releases"].get(name)
        chosen = candidate["version"] if candidate and facts["d3"] else None
        used, equal = {}, False
        if chosen:
            assert candidate["tier"] == "T3"
            prefix = ".compile_repair/deps/" + name + "@" + chosen + "/"
            used = {n[len(prefix):]: d for n,d in facts["added_files"].items() if n.startswith(prefix)}
            locked = db.packages[name][pin]["files"]
            equal = bool(used) and paths <= set(used) and all(k in locked and locked[k]["sha256"] == d for k,d in used.items())
        matches[name] = dict(locked=pin, chosen=chosen, exact_version=chosen == pin,
                             equal_files=equal, compared_files=len(used))
    return dict(packages=matches, all_versions=all(r["exact_version"] for r in matches.values()),
                all_version_or_bytes=all(r["exact_version"] or r["equal_files"] for r in matches.values()))
