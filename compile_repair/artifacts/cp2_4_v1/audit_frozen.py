"""CP2.4 integrity audit: preserve old results, environments and non-target code."""
import ast
import difflib
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.DFG.dfg_v2.experiment.run import _code_refs

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for raw in iter(lambda: stream.read(1048576), b""):
            h.update(raw)
    return h.hexdigest()

def write(name, value):
    with (OUT / name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")

def execute():
    baseline = json.loads((OUT / "baseline.json").read_text())
    target = "compile_repair/rules/environment.py"
    allowed = {target, "compile_repair/tests/test_pragma_bytes.py"} | set(baseline["docs"])
    protected = {p:h for p,h in baseline["tracked"].items() if p not in allowed}
    changed = [p for p,h in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p) != h]
    sealed_changes = [p for p,h in baseline["old_sealed"].items() if sha(ROOT/p) != h]
    environments = {}
    for name in baseline["environment"]:
        base = Path("/home/zhao/miniconda3/envs") / name
        paths = set(base.glob("lib/python*/site-packages/*.dist-info/METADATA"))
        paths.update(base.glob("conda-meta/*.json"))
        paths.add(base / "conda-meta/history")
        environments[name] = {str(p):sha(p) for p in paths if p.is_file()}
    solc = {str(p):sha(p) for p in (Path.home()/".solc-select").rglob("*") if p.is_file()}
    module = ROOT / "compile_repair"
    files = list(module.glob("*.py")) + [p for folder in module.iterdir()
        if folder.is_dir() and folder.name not in ("tests", "docs", "artifacts")
        for p in folder.rglob("*.py")]
    implementation = {str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}
    changes = sorted(p for p,h in implementation.items() if baseline["implementation_sha256"].get(p) != h)
    old = subprocess.check_output(["git", "show", baseline["head"] + ":" + target], cwd=str(ROOT)).decode()
    new = (ROOT/target).read_text()
    before = {n.name:n for n in ast.parse(old).body if isinstance(n, ast.FunctionDef)}
    after = {n.name:n for n in ast.parse(new).body if isinstance(n, ast.FunctionDef)}
    changed_functions = [name for name in before if ast.dump(before[name]) != ast.dump(after[name])]
    assert set(changed_functions) == {"_pragma_spans", "pragma_interval"}
    assert set(before) == set(after)
    # Function-level line accounting includes docstrings. Surrounding code is unchanged.
    diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(), n=0))
    added = sum(l.startswith("+") and not l.startswith("+++") for l in diff)
    removed = sum(l.startswith("-") and not l.startswith("---") for l in diff)
    summary = {"file": target, "added": added, "removed": removed,
               "changed_functions": changed_functions, "unchanged_functions": sorted(set(before)-set(changed_functions)),
               "production_file_count": len(implementation)}
    write("code_change_summary.json", summary)
    history = {}
    for path in baseline["docs"]:
        old_bytes = subprocess.check_output(["git", "show", baseline["head"] + ":" + path], cwd=str(ROOT))
        current = (ROOT/path).read_bytes()
        if path.endswith("HANDOVER.md"):
            marker = b"## 6. "
            history[path] = current[current.index(marker):].startswith(old_bytes[old_bytes.index(marker):])
        else:
            history[path] = current.startswith(old_bytes)
    changed_tracked = subprocess.check_output(["git","diff","--name-only"],cwd=str(ROOT)).decode().splitlines()
    acceptance = json.loads((OUT/"cli_acceptance.json").read_text())
    result = {"protected_tracked": len(protected), "protected_tracked_changes": changed,
        "outside_module_files": sum(not p.startswith("compile_repair/") for p in protected),
        "old_artifact_files": sum(p.startswith("compile_repair/artifacts/") for p in protected),
        "old_sealed_files": len(baseline["old_sealed"]), "old_sealed_changes": sealed_changes,
        "environment_equal": environments == baseline["environment"],
        "environment_counts": {name:len(records) for name,records in environments.items()},
        "solc_equal": solc == baseline["solc"], "solc_files": len(solc),
        "code_refs_equal": _code_refs() == baseline["code_refs"], "code_refs_count": len(baseline["code_refs"]),
        "implementation_sha256": implementation, "production_file_count": len(implementation),
        "changed_production": changes, "functions": summary,
        "cli_test_implementation_matches": acceptance["implementation_sha256"] == implementation,
        "documentation_history_preserved": history,
        "unexpected_tracked_changes": [p for p in changed_tracked if p not in allowed],
        "selection_environment_equal": {k:os.environ.get(k) for k in baseline["selection_environment"]} == baseline["selection_environment"]}
    result["passed"] = (not changed and not sealed_changes and not result["unexpected_tracked_changes"] and
        changes == [target] and len(implementation) == 14 and all(history.values()) and
        all(result[key] for key in ("environment_equal", "solc_equal", "code_refs_equal",
                                   "cli_test_implementation_matches", "selection_environment_equal")))
    write("frozen_audit.json", result)
    print(json.dumps({k:v for k,v in result.items() if k != "implementation_sha256"}, indent=2), flush=True)
    if not result["passed"]:
        raise SystemExit(2)

if __name__ == "__main__":
    execute()
