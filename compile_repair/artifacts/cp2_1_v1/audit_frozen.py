"""CP2.1 frozen-source audit; compare identities, never modify protected files."""
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.DFG.dfg_v2.experiment.run import _code_refs
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute():
    baseline = json.loads((OUT / "baseline.json").read_text())
    code_allowed = {"compile_repair/" + s for s in
                    ("toolchain/slither.py",)}
    docs_allowed = set(baseline["docs"])
    allowed = code_allowed | docs_allowed
    frozen = {p:h for p,h in baseline["tracked"].items() if p not in allowed}
    changed = [p for p,h in frozen.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
    historical = baseline["historical_sources"]
    original_changes = [p for p,h in historical.items() if sha(Path(p)) != h]
    old_sealed_changes = [p for p,h in baseline["old_sealed"].items() if sha(ROOT/p) != h]
    refs = _code_refs()
    env_changes = {name:[p for p,h in rows.items() if not Path(p).is_file() or sha(Path(p)) != h]
                   for name,rows in baseline["environment"].items()}
    current_environment = {}
    for name in baseline["environment"]:
        base = Path("/home/zhao/miniconda3/envs") / name
        selected = set(base.glob("lib/python*/site-packages/*.dist-info/METADATA"))
        selected.update(base.glob("conda-meta/*.json"))
        selected.add(base/"conda-meta/history")
        current_environment[name] = {str(p):sha(p) for p in selected if p.is_file()}
    solc = {str(p):sha(p) for p in (Path.home() / ".solc-select").rglob("*") if p.is_file()}
    module = ROOT / "compile_repair"
    files = list(module.glob("*.py")) + [p for folder in module.iterdir()
        if folder.is_dir() and folder.name not in ("tests", "docs", "artifacts")
        for p in folder.rglob("*.py")]
    implementation = {str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}
    relative = "compile_repair/toolchain/slither.py"
    old = subprocess.check_output(["git", "show", baseline["head"] + ":" + relative], cwd=str(ROOT)).decode()
    before = {n.name:ast.dump(n) for n in ast.parse(old).body if isinstance(n, ast.FunctionDef)}
    after = {n.name:ast.dump(n) for n in ast.parse((ROOT / relative).read_text()).body if isinstance(n, ast.FunctionDef)}
    preserved = {k:before[k] == after.get(k) for k in before if k != "graph_facts"}
    evidence = json.loads(gzip.decompress((OUT / "test_evidence_production.json.gz").read_bytes()))
    tested = [json.loads(raw)["implementation_sha256"] for p,raw in evidence.items() if p.endswith("/seal.json")]
    history = {}
    for relative in ("compile_repair/CP2_REPORT.md", "compile_repair/PROGRESS.md", "compile_repair/docs/CHANGE_LOG.md"):
        old = subprocess.check_output(["git", "show", baseline["head"] + ":" + relative], cwd=str(ROOT))
        history[relative] = (ROOT / relative).read_bytes().startswith(old)
    for relative, marker in (("compile_repair/docs/HANDOVER.md", b"## 6. "),
                              ("compile_repair/docs/DECISIONS.md", b"## 2. ")):
        old = subprocess.check_output(["git", "show", baseline["head"] + ":" + relative], cwd=str(ROOT))
        current = (ROOT / relative).read_bytes()
        history[relative] = current[current.index(marker):].startswith(old[old.index(marker):])
    helper_functions = []
    for path in (OUT.parent/"cp2_development_v1/run_replay.py", OUT/"run_replay.py"):
        helper_functions.append({n.name:ast.dump(n) for n in ast.parse(path.read_text()).body
                                 if isinstance(n, ast.FunctionDef)})
    replay_helpers = {name:helper_functions[0][name] == helper_functions[1][name]
                      for name in ("occurrence_keys", "historical_target")}
    tracked_changes = subprocess.check_output(["git", "diff", "--name-only"], cwd=str(ROOT)).decode().splitlines()
    result = dict(frozen_files=len(frozen), changed_frozen=changed,
                  historical_sources=len(historical), historical_source_changes=original_changes,
                  old_sealed_files=len(baseline["old_sealed"]), old_sealed_changes=old_sealed_changes,
                  outside_module_files=sum(not p.startswith("compile_repair/") for p in frozen),
                  old_artifact_files=sum(p.startswith("compile_repair/artifacts/") for p in frozen),
                  old_fixture_files=sum(p.startswith("compile_repair/tests/fixtures/") for p in frozen),
                  code_refs_count=len(refs), code_refs_equal=refs == baseline["code_refs"],
                  solc_files=len(solc), solc_equal=solc == baseline["solc"],
                  environment_counts={k:len(v) for k,v in baseline["environment"].items()},
                  environment_changes=env_changes,
                  environment_equal=current_environment == baseline["environment"], preserved_slither_functions=preserved,
                  production_files=len(files), implementation_sha256=implementation,
                  test_files=len(list((module / "tests").glob("test_*.py"))),
                  test_implementation_seals=len(tested),
                  implementation_matches_tests=bool(tested) and all(x == implementation for x in tested),
                  documentation_history=history, replay_helpers_unchanged=replay_helpers,
                  unexpected_tracked_changes=[p for p in tracked_changes if p not in allowed],
                  selection_environment_equal={k:os.environ.get(k) for k in baseline["selection_environment"]} == baseline["selection_environment"])
    result["passed"] = (not changed and not original_changes and not old_sealed_changes and not any(env_changes.values()) and
        not result["unexpected_tracked_changes"] and len(files) == 14 and
        all(result[k] for k in ("code_refs_equal", "solc_equal", "environment_equal", "implementation_matches_tests",
                               "selection_environment_equal")) and all(history.values()) and all(preserved.values()) and all(replay_helpers.values()))
    with (OUT / "frozen_audit.json").open("x", encoding="utf8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k != "implementation_sha256"}, indent=2), flush=True)
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    execute()
