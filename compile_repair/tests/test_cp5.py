"""Deterministic project assembly and offline dependency repair."""
import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from compile_repair.core.model import CompilationUnit
from compile_repair.core.provenance import verify_provenance
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.rules.dependencies import (
    OfflineIndex, build_index, dependency_choices, manifest_identities, relative_repairs,
    release_in_range)
from compile_repair.tests.test_production import production_required, trusted_compilers
from compile_repair.toolchain.project import ProjectIndex, assembly_remappings, resolve_project, unpack_sources

VERSION = "0.8.38"
PRE = b"pragma solidity 0.8.38;\n"
LIB = PRE + b"library MathLib { function value() internal pure returns(uint) { return 7; } }"
CLIENT = PRE + b'import {MathLib} from "math-kit/util/Math.sol";\ncontract Client { function f() external pure returns(uint) { return MathLib.value(); } }'


def put(root, name, data):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


@pytest.fixture
def package_index(tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as stream:
        for name, raw in [("util/Math.sol", LIB), ("package.json", b"{}")]:
            member = tarfile.TarInfo("package/" + name)
            member.size = len(raw)
            stream.addfile(member, io.BytesIO(raw))
    archive = buffer.getvalue()
    package = put(tmp_path, "archive.tgz", archive)
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode("ascii")
    release = dict(package="math-kit", version="1.0.1", expected_integrity=integrity, verified=True,
                   packed_bytes=len(archive), registry_unpacked_bytes=len(LIB)+2,
                   path=str(package), sha256=hashlib.sha256(archive).hexdigest(), url="local-fixture")
    catalog = dict(releases=[release], per_release_unpacked_limit_bytes=4096, total_unpacked_limit_bytes=4096)
    path = put(tmp_path, "catalog.json", json.dumps(catalog).encode())
    seal = build_index(path, tmp_path/"index", hashlib.sha256(path.read_bytes()).hexdigest())
    assert seal["solidity_files"] == 1 and not list((tmp_path/"index").rglob("package.json"))
    return OfflineIndex(tmp_path/"index")


def test_offline_index_rechecks_content(tmp_path, package_index):
    assert package_index.content("math-kit", "1.0.1", "util/Math.sol") == LIB
    put(package_index.root, "files/math-kit@1.0.1/util/Math.sol", LIB+b" ")
    with pytest.raises(ValueError, match="SHA256"):
        package_index.content("math-kit", "1.0.1", "util/Math.sol")


@pytest.mark.parametrize("spec,yes,no", [
    ("^0.2.1", "0.2.9", "0.3.0"), ("~1.4", "1.4.9", "1.5.0"),
    ("1.2 - 2.3", "2.3.19", "2.4.0"), (">=1.2 <2 || 3.x", "3.1.9", "2.0.0"),
])
def test_semver_prerelease_free_interval(spec, yes, no):
    assert release_in_range(yes, spec)
    assert not release_in_range(no, spec)


def test_owner_lock_alias_and_scope(tmp_path):
    put(tmp_path, "package.json", b'{"dependencies":{"original":"^3"}}')
    put(tmp_path, "a/package.json", b'{"devDependencies":{"original":"npm:math-kit@~1.0"}}')
    put(tmp_path, "package-lock.json", b'{"packages":{"a/node_modules/original":{"name":"math-kit","version":"1.0.1"}}}')
    local = manifest_identities(tmp_path, "a/src/C.sol", "original")
    assert (local["tier"], local["package"], local["spec"]) == ("T1", "math-kit", "1.0.1")
    other = manifest_identities(tmp_path, "b/src/C.sol", "original")
    assert (other["tier"], other["package"], other["spec"]) == ("T2", "original", "^3")


@pytest.mark.parametrize("sources", [
    {"/bad.sol": {"content": ""}}, {"../bad.sol": {"content": ""}},
    {"a/../C": {"content": ""}, "C": {"content": ""}},
    {"A": {"content": ""}, "A/B": {"content": ""}}, {"A": {"urls": ["https://example.invalid"]}},
    {"A": {"content": "", "keccak256": "0x"+"00"*32}},
])
def test_wrapper_refuses_invalid_sources(tmp_path, sources):
    raw = json.dumps(dict(language="Solidity", sources=sources)).encode()
    with pytest.raises(ValueError):
        unpack_sources(raw, ArtifactStore(tmp_path/"out"), "sources")
    assert not (tmp_path/"out/sources").exists()


def test_step2_unique_and_ambiguous_directory(tmp_path):
    put(tmp_path, "src/Main.sol", CLIENT)
    put(tmp_path, "one/util/Math.sol", LIB)
    idx = ProjectIndex(tmp_path)
    p = resolve_project(tmp_path, "src/Main.sol", index=idx)
    assert assembly_remappings(p, idx)[0] == ("math-kit/=one/",)
    put(tmp_path, "two/util/Math.sol", LIB)
    idx = ProjectIndex(tmp_path)
    assert assembly_remappings(p, idx)[0] == ()
    put(tmp_path, "remappings.txt", b"math-kit/=one/\n")
    assert assembly_remappings(p, idx)[0] == ("math-kit/=one/",)


def test_step4_unique_declared_name_and_ties(tmp_path):
    raw = CLIENT.replace(b"math-kit/util/Math.sol", b"../old/Math.sol")
    put(tmp_path, "src/Main.sol", raw)
    put(tmp_path, "vendor/Math.sol", LIB)
    put(tmp_path, "other/Math.sol", PRE+b"contract Different {}")
    idx = ProjectIndex(tmp_path)
    p = resolve_project(tmp_path, "src/Main.sol", index=idx)
    changed, edits, _ = relative_repairs(p, idx, [VERSION])
    assert changed == {"src/Main.sol": raw.replace(b"../old/Math.sol", b"../vendor/Math.sol")}
    patch, = edits["src/Main.sol"]
    assert raw[patch.start:patch.end] == b"../old/Math.sol"
    put(tmp_path, "also/Math.sol", LIB)
    assert not relative_repairs(p, ProjectIndex(tmp_path), [VERSION])[0]


@pytest.mark.parametrize("case", ["named_symbol", "pragma", "pinned"])
def test_step3_rejects_incompatible_release(tmp_path, package_index, case):
    root = tmp_path/"project"
    raw = CLIENT
    if case == "named_symbol":
        raw = raw.replace(b"MathLib}", b"Wrong}")
    elif case == "pragma":
        raw = raw.replace(b"0.8.38", b"0.7.6")
    else:
        put(root, "package-lock.json", b'{"packages":{"node_modules/math-kit":{"version":"2.0.0"}}}')
    put(root, "Main.sol", raw)
    idx = ProjectIndex(root)
    p = resolve_project(root, "Main.sol", index=idx)
    assert not list(dependency_choices(p, idx, package_index, ["0.7.6", VERSION], {}, "latest", []))


@pytest.mark.parametrize("step", [2, 3, 4])
def test_pipeline_solc_d3_and_provenance(tmp_path, package_index, step):
    production_required()
    root = tmp_path/"inputs"
    raw = CLIENT
    if step == 2:
        put(root, "vendor/util/Math.sol", LIB)
    if step == 4:
        raw = raw.replace(b"math-kit/util/Math.sol", b"../moved/Math.sol")
        put(root, "vendor/Math.sol", LIB)
    src = put(root, "src/Main.sol", raw)
    idx = ProjectIndex(root)
    project = resolve_project(root, src, index=idx)
    store = ArtifactStore(tmp_path/"results")
    result = repair_unit(CompilationUnit("probe", project.files), {VERSION: trusted_compilers()[VERSION]},
                         store, io.StringIO(), project=project, project_index=idx, offline_index=package_index)
    assert result.status == "success" and result.selected_version == VERSION
    steps = json.loads((store.path/"units/probe/repair_steps.json").read_bytes())
    assert [s["step"] for s in steps if s.get("accepted")] == [step]
    graph = json.loads((store.path/"units/probe/graph.json").read_bytes())
    assert len({n["filename"] for n in graph["nodes"]}) == 2
    assert src.read_bytes() == raw
    if step == 3:
        added = next((p, m) for p, m in result.provenance.items() if m.level == "additive")
        assert verify_provenance(b"", Path(added[0]).read_bytes(), added[1])
        assert any(n["provenance"] == "added" for n in graph["nodes"])


@pytest.mark.parametrize("policy,known,expected", [
    ("latest", None, "2.0.0"), ("oldest", None, "1.0.1"),
    ("closest", None, "1.0.1"), ("closest", "0.8.38", "2.0.0")])
def test_release_selection_uses_actual_compiled_series(tmp_path, policy, known, expected):
    from compile_repair.rules.dependencies import _indexed_source
    production_required()
    raws = {"1.0.1": LIB.replace(b"0.8.38", b"0.7.6"), "2.0.0": LIB}
    class Releases:
        packages = {"math-kit": {v: dict(files={"util/Math.sol": _indexed_source(b)},
                    integrity="handwritten-fixture", archive_sha256=hashlib.sha256(b).hexdigest())
                    for v, b in raws.items()}}
        def content(self, name, version, path):
            assert name == "math-kit" and path == "util/Math.sol"
            return raws[version]
    root = tmp_path/"input"
    source = put(root, "Main.sol", CLIENT.replace(b"0.8.38", b">=0.7.6 <0.9.0"))
    project = resolve_project(root, source)
    env = trusted_compilers()
    store = ArtifactStore(tmp_path/"store")
    unit = CompilationUnit("selection", project.files, known)
    result = repair_unit(unit, {v:env[v] for v in ("0.7.6", "0.8.38")}, store, io.StringIO(),
                         project=project, offline_index=Releases(), dependency_policy=policy)
    assert result.status == "success"
    steps = json.loads((store.path/"units/selection/repair_steps.json").read_bytes())
    accepted, = [s for s in steps if s.get("accepted")]
    assert accepted["d3_verified"] and accepted["releases"]["math-kit"]["inferred"]
    assert accepted["releases"]["math-kit"]["version"] == expected
