"""Enforce PROMPTS 3.10, including relative imports and the module budget."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "__init__.py", "cli.py", "pipeline.py",
    "core/__init__.py", "core/model.py", "core/provenance.py", "core/store.py",
    "toolchain/__init__.py", "toolchain/solc.py", "toolchain/slither.py", "toolchain/project.py",
    "rules/__init__.py", "rules/environment.py", "rules/dependencies.py", "rules/normalize.py", "rules/stubs.py",
    "rag/__init__.py", "rag/knowledge.py", "rag/retrieve.py",
    "agents/__init__.py", "agents/llm.py", "agents/prompt.py", "agents/patch.py", "agents/stage1.py", "agents/stage2.py",
    "evaluation/__init__.py", "evaluation/survey.py", "evaluation/benchmark.py", "evaluation/report.py"}
DEPENDENCIES = {
    "core": {"core"}, "toolchain": {"core", "toolchain"},
    "rules": {"core", "toolchain", "rules"}, "rag": {"core", "toolchain", "rag"},
    "agents": {"core", "toolchain", "rag", "agents"},
    "pipeline": {"core", "toolchain", "rules", "rag", "agents", "pipeline"},
    "evaluation": {"core", "toolchain", "rules", "rag", "agents", "pipeline", "evaluation"},
    "cli": {"pipeline", "evaluation"}, "__init__": set()}


def internal_dependencies(tree, relative):
    package = ["compile_repair"] + list(relative.parts[:-1])
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            prefix = (package[:len(package) - node.level + 1] if node.level else [])
            base = ".".join(prefix + ([node.module] if node.module else []))
            names = [base] + [base + "." + a.name for a in node.names]
        else:
            continue
        for name in names:
            parts = name.split(".")
            if len(parts) > 1 and parts[0] == "compile_repair":
                found.add(parts[1])
    return found


def test_layering():
    paths = [p for p in ROOT.rglob("*.py") if not {"tests", "artifacts"} & set(p.relative_to(ROOT).parts)]
    assert len(paths) <= 30
    for path in paths:
        relative = path.relative_to(ROOT)
        assert relative.as_posix() in ALLOWED
        source = path.read_text(encoding="utf8")
        tree = ast.parse(source)
        layer = relative.parts[0] if len(relative.parts) > 1 else relative.stem
        deps = internal_dependencies(tree, relative)
        assert deps <= DEPENDENCIES[layer], (relative, deps)
        assert layer == "pipeline" or not {"rules", "agents"} <= deps
        if relative.as_posix() != "cli.py":
            assert not any(isinstance(n, ast.Compare) and any(
                isinstance(v, ast.Name) and v.id == "__name__" for v in ast.walk(n)) for n in ast.walk(tree))
        assert not any(isinstance(n, ast.Call) and (
            isinstance(n.func, ast.Name) and n.func.id == "__import__" or
            isinstance(n.func, ast.Attribute) and n.func.attr == "import_module") for n in ast.walk(tree))


def test_import_resolution():
    assert internal_dependencies(ast.parse("from ..rules import environment"), Path("core/model.py")) == {"rules"}
    assert internal_dependencies(ast.parse("from compile_repair import agents"), Path("pipeline.py")) == {"agents"}
