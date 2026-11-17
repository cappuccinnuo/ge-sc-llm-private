"""CP2.3 integrity audit: permitted functions, old evidence, environments and docs."""
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.DFG.dfg_v2.experiment.run import _code_refs


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute():
    baseline = json.loads((OUT / "baseline.json").read_text())
    code_allowed = {"compile_repair/rules/environment.py", "compile_repair/pipeline.py"}
    allowed = code_allowed | set(baseline["docs"])
    frozen = {p:h for p,h in baseline["tracked"].items() if p not in allowed}
    changed = [p for p,h in frozen.items() if not (ROOT/p).is_file() or sha(ROOT/p) != h]
    sealed_changes = [p for p,h in baseline["old_sealed"].items() if sha(ROOT/p) != h]
    source_changes = [p for p,h in baseline["historical_sources"].items() if sha(Path(p)) != h]
    environment = {}
    for name in baseline["environment"]:
        base = Path("/home/zhao/miniconda3/envs") / name
        paths = set(base.glob("lib/python*/site-packages/*.dist-info/METADATA"))
        paths.update(base.glob("conda-meta/*.json"))
        paths.add(base / "conda-meta/history")
        environment[name] = {str(p):sha(p) for p in paths if p.is_file()}
    solc = {str(p):sha(p) for p in (Path.home()/".solc-select").rglob("*") if p.is_file()}
    module = ROOT / "compile_repair"
    files = list(module.glob("*.py")) + [p for folder in module.iterdir()
        if folder.is_dir() and folder.name not in ("tests", "docs", "artifacts") for p in folder.rglob("*.py")]
    implementation = {str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}
    changes = sorted(p for p,h in implementation.items() if baseline["implementation_sha256"].get(p) != h)
    functions = {}
    additions = {}
    allowed_functions = {
        "compile_repair/rules/environment.py": {"pragma_interval", "pragma_patches", "infer_interval"},
        "compile_repair/pipeline.py": {"repair_unit"},
    }
    for relative, permitted in allowed_functions.items():
        old = subprocess.check_output(["git", "show", baseline["head"] + ":" + relative], cwd=str(ROOT)).decode()
        before = {n.name:ast.dump(n) for n in ast.parse(old).body if isinstance(n, ast.FunctionDef)}
        after = {n.name:ast.dump(n) for n in ast.parse((ROOT/relative).read_text()).body if isinstance(n, ast.FunctionDef)}
        functions[relative] = {name:before[name] == after.get(name) for name in before if name not in permitted}
        additions[relative] = sorted(set(after) - set(before))
        assert set(n for n in before if before[n] != after.get(n)) == permitted
    assert additions["compile_repair/rules/environment.py"] == ["_expression_interval", "_pragma_spans"]
    assert additions["compile_repair/pipeline.py"] == []
    evidence = json.loads(gzip.decompress((OUT/"test_evidence_production.json.gz").read_bytes()))
    tested = [json.loads(raw)["implementation_sha256"] for p,raw in evidence.items() if p.endswith("/seal.json")]
    run_seal = json.loads((OUT.parent/"cr_store_mando_v5/seal.json").read_text())
    history = {}
    for relative in ("compile_repair/CP2_REPORT.md", "compile_repair/PROGRESS.md", "compile_repair/docs/CHANGE_LOG.md"):
        old = subprocess.check_output(["git","show",baseline["head"]+":"+relative], cwd=str(ROOT))
        history[relative] = (ROOT/relative).read_bytes().startswith(old)
    for relative, marker in (("compile_repair/docs/HANDOVER.md", b"## 6. "),
                             ("compile_repair/docs/DECISIONS.md", b"## 2. ")):
        old = subprocess.check_output(["git","show",baseline["head"]+":"+relative], cwd=str(ROOT))
        raw = (ROOT/relative).read_bytes()
        history[relative] = raw[raw.index(marker):].startswith(old[old.index(marker):])
    diff = subprocess.check_output(["git","diff","--name-only"], cwd=str(ROOT)).decode().splitlines()
    result = dict(frozen_files=len(frozen), changed_frozen=changed,
        outside_module_files=sum(not p.startswith("compile_repair/") for p in frozen),
        old_artifact_files=sum(p.startswith("compile_repair/artifacts/") for p in frozen),
        old_fixture_files=sum(p.startswith("compile_repair/tests/fixtures/") for p in frozen),
        old_sealed_files=len(baseline["old_sealed"]), old_sealed_changes=sealed_changes,
        historical_sources=len(baseline["historical_sources"]), historical_source_changes=source_changes,
        code_refs_count=len(baseline["code_refs"]), code_refs_equal=_code_refs() == baseline["code_refs"],
        solc_files=len(solc), solc_equal=solc == baseline["solc"],
        environment_counts={k:len(v) for k,v in environment.items()}, environment_equal=environment == baseline["environment"],
        production_files=len(files), changed_production=changes, preserved_functions=functions,
        added_functions=additions, implementation_sha256=implementation, implementation_matches_tests=(
            bool(tested) and all(item == implementation for item in tested)),
        test_implementation_seals=len(tested), implementation_matches_regression=run_seal["implementation_sha256"] == implementation,
        documentation_history=history, unexpected_tracked_changes=[p for p in diff if p not in allowed],
        selection_environment_equal={k:os.environ.get(k) for k in baseline["selection_environment"]} == baseline["selection_environment"])
    result["passed"] = (not changed and not sealed_changes and not source_changes and
        not result["unexpected_tracked_changes"] and len(files)==14 and set(changes)==code_allowed and
        all(all(v.values()) for v in functions.values()) and all(history.values()) and
        all(result[k] for k in ("code_refs_equal", "solc_equal", "environment_equal", "implementation_matches_tests",
                               "implementation_matches_regression", "selection_environment_equal")))
    with (OUT/"frozen_audit.json").open("x", encoding="utf8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({k:v for k,v in result.items() if k != "implementation_sha256"}, indent=2), flush=True)
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    execute()
