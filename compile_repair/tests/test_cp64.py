"""CP6.4: D26 versioned import prefixes, step 9 (codegen-only) and step 10 (Slither compatibility)."""
import io
import json

import pytest

from compile_repair.core.model import CompilationUnit
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.rules.dependencies import dependency_choices
from compile_repair.tests.test_cp5 import CLIENT, VERSION, package_index, put  # noqa: F401  (fixture)
from compile_repair.tests.test_production import production_required, trusted_compilers
from compile_repair.toolchain.project import ProjectIndex, resolve_project


def _project(tmp_path, prefix, manifest=None):
    root = tmp_path / "project"
    put(root, "Main.sol", CLIENT.replace(b"math-kit/util/Math.sol", prefix + b"/util/Math.sol"))
    if manifest:
        put(root, "package.json", manifest)
    index = ProjectIndex(root)
    return resolve_project(root, "Main.sol", index=index), index


def test_versioned_prefix_names_the_exact_release(tmp_path, package_index):
    project, index = _project(tmp_path, b"math-kit-1.0.1")
    evidence = []
    choices = list(dependency_choices(project, index, package_index, [VERSION], {}, "oldest", evidence))
    assert len(choices) == 1
    candidate, added, chosen = choices[0]
    assert chosen["math-kit"]["version"] == "1.0.1" and chosen["math-kit"]["tier"] == "T1"
    assert not chosen["math-kit"]["inferred"]
    identity, = chosen["math-kit"]["identities"]
    assert identity["evidence"] == "D26_versioned_prefix" and identity["requested"] == "math-kit-1.0.1"
    assert "math-kit-1.0.1/=.compile_repair/deps/math-kit@1.0.1/" in candidate.remappings


@pytest.mark.parametrize("prefix,manifest", [
    (b"math-kit-9.9.9", None),  # the named release is not indexed
    (b"math-kit-1.0.1", b'{"dependencies":{"math-kit-1.0.1":"^2"}}'),  # a manifest names the prefix itself
])
def test_versioned_prefix_needs_an_indexed_release_and_no_other_evidence(tmp_path, package_index, prefix, manifest):
    project, index = _project(tmp_path, prefix, manifest)
    assert not list(dependency_choices(project, index, package_index, [VERSION], {}, "oldest", []))


def test_pipeline_repairs_a_versioned_prefix(tmp_path, package_index):
    production_required()
    project, index = _project(tmp_path, b"math-kit-1.0.1")
    store = ArtifactStore(tmp_path / "run")
    record = repair_unit(CompilationUnit("prefix", project.files), {VERSION: trusted_compilers()[VERSION]},
                         store, io.StringIO(), project=project, project_index=index, offline_index=package_index)
    assert record.status == "success"
    steps = json.loads((store.path / "units/prefix/repair_steps.json").read_bytes())
    accepted = [s for s in steps if s.get("accepted")]
    assert [s["step"] for s in accepted] == [3]


# ---- Step 9: failures that only code generation reports ------------------------------------

import hashlib  # noqa: E402
import sys  # noqa: E402

from compile_repair.core.model import Compilation, Compiler, SourceFile  # noqa: E402
from compile_repair.rules.environment import codegen_only_retry  # noqa: E402
from compile_repair.rules.normalize import import_alias_rewrites  # noqa: E402
from compile_repair.toolchain import slither as slither_module  # noqa: E402
from compile_repair.toolchain.solc import compile_ast_only, compile_file  # noqa: E402
from compile_repair.toolchain.slither import run_slither  # noqa: E402

DEEP = (b"pragma solidity >=0.5.0;\ncontract Deep {\n  function f(uint a1, uint a2, uint a3, uint a4, uint a5, uint a6,"
        b" uint a7, uint a8, uint a9) public pure returns (uint) {\n    uint b1 = a1 + a2; uint b2 = a3 + a4;"
        b" uint b3 = a5 + a6; uint b4 = a7 + a8; uint b5 = a9 + b1;\n    uint b6 = b2 + b3; uint b7 = b4 + b5;"
        b" uint b8 = b6 + b7; uint b9 = b8 + a1;\n    return a1 + a2 + a3 + a4 + a5 + a6 + a7 + a8 + a9 + b1 + b2"
        b" + b3 + b4 + b5 + b6 + b7 + b8 + b9;\n  }\n}\n")
PLAIN = (b"pragma solidity >=0.5.2;\ncontract T {\n  uint s;\n  event E(uint v);\n  function f(uint x) public returns (uint) {\n"
         b"    s += x;\n    emit E(s);\n    if (x > 2) { return g(x); }\n    return x;\n  }\n"
         b"  function g(uint y) internal pure returns (uint) { return y * 2; }\n}\n")
STACK = "CompilerError: Stack too deep, try removing local variables.\n --> A.sol:3:5:\n"


def _compilation(version, stderr, rc=1):
    return Compilation("/x/A.sol", "x", Compiler(version, "/absent", "x"), [], "/x", rc, stderr.splitlines()[0],
                       stderr, "", 0.0, False)


@pytest.mark.parametrize("version,stderr,expected", [
    ("0.7.6", STACK, True),
    ("0.5.1", STACK, False),  # standard JSON still generates code below 0.5.2
    ("0.7.6", STACK + "TypeError: Type uint256 is not implicitly convertible.\n --> A.sol:4:1:\n", False),
    ("0.7.6", "TypeError: Type uint256 is not implicitly convertible.\n --> A.sol:4:1:\n", False),
])
def test_codegen_only_retry(version, stderr, expected):
    assert (codegen_only_retry(_compilation(version, stderr)) is not None) == expected


def test_ast_only_skips_code_generation(tmp_path):
    production_required()
    path = put(tmp_path, "A.sol", DEEP)
    compiler = trusted_compilers()["0.8.38"]
    assert compile_file(path, compiler).returncode != 0
    compiled = compile_ast_only(path, compiler)
    assert compiled.returncode == 0 and compiled.output == "ast_only"
    result = run_slither(compiled, profile="production")
    assert result["d3"] and result["d3_c"]


@pytest.mark.parametrize("version", ["0.5.17", "0.6.12", "0.7.6", "0.8.38"])
def test_ast_only_graph_equals_the_normal_graph(tmp_path, version):
    """Slither builds its IR from the AST, so code generation must not change the graph."""
    production_required()
    path = put(tmp_path, "A.sol", PLAIN)
    compiler = trusted_compilers()[version]
    normal = run_slither(compile_file(path, compiler), profile="production")
    ast_only = run_slither(compile_ast_only(path, compiler), profile="production")
    assert normal["d3"] and ast_only["d3"]
    assert normal["graph"] == ast_only["graph"] and normal["nodes"] == ast_only["nodes"]


def test_pipeline_uses_ast_only_after_a_codegen_failure(tmp_path):
    production_required()
    path = put(tmp_path, "A.sol", DEEP)
    unit = CompilationUnit("deep", (SourceFile(str(path), hashlib.sha256(DEEP).hexdigest(), DEEP),))
    record = repair_unit(unit, {v: trusted_compilers()[v] for v in ("0.5.1", "0.7.6")},
                         ArtifactStore(tmp_path / "run"), io.StringIO())
    assert record.status == "success" and record.selected_version == "0.7.6"
    assert "ast_only_compilation" in record.flags
    assert [(a["version"], a["output"]) for a in record.attempts] == [
        ("0.5.1", "combined_json"), ("0.7.6", "combined_json"), ("0.7.6", "ast_only")]


# ---- Step 10: Slither-compatible rewrites -----------------------------------------------

ALIAS_LIB = b"pragma solidity ^0.5.0;\nlibrary Lib { function v() internal pure returns (uint) { return 7; } }\n"
ALIAS_USER = (b'pragma solidity ^0.5.0;\nimport {Lib as L} from "./Lib.sol";\n'
              b"contract C { function f() public pure returns (uint) { return L.v(); } }\n")
FAILURE = ["Cannot resolve local alias for import directive due to malformed AST. Please upgrade to solc 0.6.0 or higher."]


def _rewrite(raw):
    from compile_repair.core.provenance import apply_patches
    patches, evidence = import_alias_rewrites(raw, FAILURE)
    return (apply_patches(raw, tuple(sorted(patches, key=lambda p: -p.start)))[0] if patches else None), evidence


def test_import_alias_is_replaced_by_the_original_name():
    out, evidence = _rewrite(ALIAS_USER)
    assert out == ALIAS_USER.replace(b"{Lib as L}", b"{Lib}").replace(b"return L.v()", b"return Lib.v()")
    assert evidence == [dict(original="Lib", alias="L", uses=1)]
    assert import_alias_rewrites(ALIAS_USER, ["other failure"]) == ([], [])


@pytest.mark.parametrize("raw,reason", [
    (ALIAS_USER.replace(b"return L.v()", b"return L.v() + Lib.v()"), "original_name_used_elsewhere"),
    (ALIAS_USER.replace(b"return L.v()", b"return this.L()"), "alias_not_a_plain_use"),
    (ALIAS_USER.replace(b"return L.v()", b"uint L = 1; return L"), "alias_not_a_plain_use"),
])
def test_alias_rewrite_needs_an_unambiguous_rename(raw, reason):
    out, evidence = _rewrite(raw)
    assert out is None and evidence[0]["reason"] == reason


def test_pipeline_rewrites_an_import_alias_for_slither(tmp_path):
    production_required()
    root = tmp_path / "src"
    put(root, "Lib.sol", ALIAS_LIB)
    put(root, "C.sol", ALIAS_USER)
    index = ProjectIndex(root)
    project = resolve_project(root, "C.sol", index=index)
    store = ArtifactStore(tmp_path / "run")
    record = repair_unit(CompilationUnit("alias", project.files), {"0.5.17": trusted_compilers()["0.5.17"]},
                         store, io.StringIO(), project=project, project_index=index)
    environment = json.loads((store.path / "units/alias/environment_result.json").read_bytes())
    assert environment["reason"] == "slither_side_failure"
    assert record.status == "success"
    steps = json.loads((store.path / "units/alias/repair_steps.json").read_bytes())
    assert [s["step"] for s in steps if s.get("accepted")] == [10]
    assert {c.step for p in record.provenance.values() for c in p.changes} == {"slither_compat"}


# ---- Step 10: Slither recursion depth -------------------------------------------------------

def test_recursion_error_is_repeated_once_with_a_deep_stack(monkeypatch):
    calls, limits = [], []

    def fake(compilation, profile, cp0_projection, project):
        calls.append(profile)
        limits.append(sys.getrecursionlimit())
        return {"exception_type": "RecursionError"} if len(calls) == 1 else {"d3": True}
    before = sys.getrecursionlimit()
    monkeypatch.setattr(slither_module, "_run_slither", fake)
    result = slither_module.run_slither(None, profile="production")
    assert result["d3"] and result["deep_recursion_retry"]["first_exception"] == "RecursionError"
    assert limits == [before, slither_module._DEEP_RECURSION_LIMIT] and sys.getrecursionlimit() == before
    calls.clear()
    monkeypatch.setattr(slither_module, "_run_slither", lambda *a: {"exception_type": "RecursionError"})
    assert "deep_recursion_retry" in slither_module.run_slither(None, profile="production")
    assert slither_module.run_slither(None, profile="regression_6c") == {"exception_type": "RecursionError"}
