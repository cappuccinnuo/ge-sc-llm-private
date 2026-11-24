"""Replay the four CP5.2 partial-IR units with the frozen CP5 dependency policy."""
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / "compile_repair/artifacts"
CP51 = ART / "cp5_1_v1"
OUT = ROOT.parent / "compile-repair-local/cp6_0_v1"
UNITS = ("cp3_19463", "cp3_19496", "cp3_19497", "cp3_19507")
sys.path[:0] = [str(ROOT), str(CP51)]
from evidence import verified_index
from population import entry, load, population, save
from compile_repair.core.store import ArtifactStore, read_checked_json, sha256
from compile_repair.evaluation.report import primary_causes
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import classify_slither, load_trusted_compilers


def candidates(record):
    rows = []
    for attempt in record["attempts"]:
        if not attempt.get("solc"):
            continue
        slither = attempt.get("slither") or {}
        ir = slither.get("partial_ir") or {}
        failure = classify_slither(slither) if slither and not slither.get("d3") else {}
        rows.append(dict(version=attempt["version"], solc_returncode=attempt["solc"]["returncode"],
                         compiler_sha256=attempt["solc"]["compiler"]["sha256"],
                         settings=attempt["settings"], slither_ran=bool(slither),
                         d3_a=slither.get("d3_a"), d3_b=slither.get("d3_b"), d3_c=slither.get("d3_c"),
                         d3=slither.get("d3"), partial_ir_recorded="partial_ir" in slither,
                         contracts=ir.get("incorrectly_constructed_contracts"), top_level_errors=ir.get("top_level_errors"),
                         subtype=failure.get("subtype"), error_first_line=slither.get("error_first_line")))
    return rows


def main():
    started = time.monotonic()
    check_profile("production")
    tools, _, _ = load_trusted_compilers()
    db = verified_index()
    policy = load(CP51 / "policy.json")
    assert (policy["status"], policy["policy"], policy["limit"]) == ("frozen", "oldest", 21)
    assert db.seal["index_sha256"] == policy["index_sha256"]
    old_file = CP51 / "real_dev.jsonl"
    assert sha256(old_file) == load(CP51 / "real_dev_summary.json")["rows_sha256"]
    with old_file.open("rb") as f:
        old = {r["unit_id"]: r for r in map(json.loads, f) if r["unit_id"] in UNITS and r["rule"] == "oldest"}
    targets, _ = population()
    ir_data = gzip.decompress((ART / "cp5_2_v1/packed/continuation/ir_real_dev.jsonl.gz").read_bytes())
    assert hashlib.sha256(ir_data).hexdigest() == load(ART / "cp5_2_v1/continuation/ir_real_dev.json")["sha256"]
    flagged = {r["unit_id"]: r for r in map(json.loads, ir_data.splitlines())
               if r["incorrectly_constructed_contracts"] or r["top_level_errors"]}
    assert set(old) == set(flagged) == set(UNITS)
    summary = dict(command=[sys.executable, "-B", str(Path(__file__).resolve())],
                   commit=subprocess.check_output(["git","rev-parse","HEAD"], cwd=ROOT, text=True).strip(),
                   expected="Reject with no graph and primary slither_incomplete / slither_partial_ir, or pass D3(c) on another version with empty partial IR.",
                   policy="oldest", limit=21, historical_development_limit=old[UNITS[0]]["limit"],
                   index_sha256=db.seal["index_sha256"], units=[], cost_usd=0)
    work = OUT / "partial_ir_units"
    work.mkdir()
    for uid in UNITS:
        tick = time.monotonic()
        target = targets[uid]
        prior = read_checked_json(old[uid]["result_path"], old[uid]["result_sha256"])
        assert target["split"] == "dev" and target["corpus"] == "DAppSCAN"
        assert target["entry_sha256"] == old[uid]["entry_sha256"]
        assert prior["status"] == "success" and prior["selected_version"] == "0.8.4"
        unit, project, inventory = entry(target)
        store = ArtifactStore(work / uid)
        with store.journal("invocations.jsonl") as journal:
            result = repair_unit(unit, tools, store, journal, project=project, project_index=inventory,
                                 offline_index=db, dependency_policy="oldest", dependency_limit=21, mask_versions=False)
        record = asdict(result)
        folder = store.path / "units" / uid
        assert record["unit_id"] == uid
        final = load(folder / "result.json")
        assert final["status"] == result.status and final["reason"] == result.reason
        paths = [folder / "environment_result.json", *sorted(folder.glob("round_*/result.json"))]
        rounds = {str(p.relative_to(folder)): candidates(load(p)) for p in paths if p.is_file()}
        final_candidates = candidates(final)
        all_attempts = [a for rs in rounds.values() for a in rs] + final_candidates
        original = [a for a in all_attempts if a["version"]=="0.8.4" and a["d3_c"] is False]
        old_compiler = prior["attempts"][-1]["solc"]["compiler"]["sha256"]
        binding_verified = any(a["compiler_sha256"]==old_compiler and a["d3_a"] and a["d3_b"] and
                               a["subtype"]=="slither_partial_ir" and
                               a["contracts"]==flagged[uid]["incorrectly_constructed_contracts"] and
                               a["top_level_errors"]==flagged[uid]["top_level_errors"] for a in original)
        graph = folder / "graph.json"
        primary = primary_causes(final)["categories"]
        if result.status == "success":
            valid = graph.is_file() and result.selected_version != "0.8.4" and any(
                a["version"]==result.selected_version and a["d3"] and a["d3_c"] is True and
                a["contracts"]==[] and a["top_level_errors"]==0 for a in final_candidates)
        else:
            valid = not graph.exists() and primary==["slither_incomplete"] and any(
                a["subtype"]=="slither_partial_ir" for a in final_candidates)
        matched = bool(valid)
        row = dict(unit_id=uid, elapsed_seconds=round(time.monotonic()-tick,3),status=result.status,
                   reason=result.reason,primary=primary,selected_version=result.selected_version,
                   prior_flagged_contracts=flagged[uid]["incorrectly_constructed_contracts"],
                   prior_result_sha256=old[uid]["result_sha256"], entry_sha256=target["entry_sha256"],
                   old_compiler_sha256=old_compiler, binding_verified=binding_verified,
                   graph_present=graph.exists(), result_sha256=sha256(folder/"result.json"),
                   journal_sha256=sha256(store.path/"invocations.jsonl"), rounds=rounds,
                   final_candidates=final_candidates,matches_expected=matched)
        save(work/(uid+".json"),row)
        summary["units"].append(row)
        if not matched:
            break
    summary.update(elapsed_seconds=round(time.monotonic()-started,3),
                   unrun=[u for u in UNITS if u not in {r["unit_id"] for r in summary["units"]}],
                   passed=len(summary["units"])==4 and all(r["matches_expected"] for r in summary["units"]))
    save(OUT/"partial_ir_units.json",summary)
    return 0 if summary["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
