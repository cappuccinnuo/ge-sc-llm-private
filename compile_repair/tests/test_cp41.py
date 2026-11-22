"""CP4.1 witnesses for CLI types, source bytes and graph comparison."""
import copy
import json
from pathlib import Path

import pytest

from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.evaluation.benchmark import SourceLayout, normalized_node_ir, score_graphs
from compile_repair.evaluation.report import parseable_version_blockers, primary_causes
from compile_repair.toolchain.solc import classify_diagnostic, parse_diagnostics

FIXTURES = Path(__file__).parent / "fixtures/cp4_1"
CASES = json.loads((FIXTURES / "diagnostics.json").read_bytes())
EXPECTED = json.loads((FIXTURES / "expected_categories.json").read_bytes())


@pytest.mark.parametrize("case", CASES, ids=[str(c["id"]) for c in CASES])
@pytest.mark.parametrize("legacy", [True, False])
def test_old_cli_template_in_both_formats(case, legacy):
    msg = case["template"]
    stderr = ("Probe.sol:1:1: Error: " + msg if legacy else "Error: " + msg + "\n --> Probe.sol:1:1:")
    raw = parse_diagnostics(stderr)
    assert len(raw) == 1 and raw[0]["kind"] == "Error"
    assert raw[0]["location_format"] == ("legacy" if legacy else "modern")
    result = classify_diagnostic(raw[0], b"contract Witness {}")
    assert result["category"] == EXPECTED[str(case["id"])]


def test_unbalanced_syntax_still_depends_on_source_and_library_name_is_typed():
    d = {"kind": "Error", "message": "Function, variable, struct or modifier declaration expected."}
    assert classify_diagnostic(d, b"contract A {")["category"] == "unbalanced_structure"
    assert classify_diagnostic(d, b"contract A {}")["category"] == "parser_error_other"
    assert classify_diagnostic(dict(d, message="Library name expected."))["category"] == "type_error_other"


def test_version_noise_stays_visible_for_each_candidate():
    record = {"status": "unrepaired", "attempts": [
        {"version": v, "solc": {"returncode": 1}} for v in ("0.4.24","0.6.12")]}
    failures = [{"stage": "solc","version": v,"category": label}
                for v,label in (("0.4.24","version_mismatch"),("0.6.12","abi_coder_required"))]
    primary = primary_causes(record, failures)
    assert primary["categories"] == ["abi_coder_required"]
    assert primary["by_version"]["0.4.24"] == ["version_mismatch"]
    assert parseable_version_blockers(primary["by_version"]) == ["abi_coder_required"]
    assert primary_causes({"status":"unrepaired","attempts":record["attempts"][:1]}, failures[:1])["categories"] == ["version_dependent"]


def test_offsets_only_inside_solidity_text_literals():
    sol = (b'import "./Dependency.sol"; pragma experimental "ABIEncoderV2"; '
           b'contract C { /* "comment" */ function f() public { assembly ("memory-safe") { let x := "yul" } '
           b'bytes memory h = hex"ab"; string memory t = "message"; } }')
    assert list(SourceLayout(sol).string_contents()) == [sol.index(b"message")]


def ir(data, include_type=True):
    refs = ["TMP(bytes) = SOLIDITY_CALL type()(Child)"] if include_type else []
    return refs + ["v(bytes) := "+data.hex()+"(bytes)"]


def trailer(cbor):
    return cbor+len(cbor).to_bytes(2,"big")


def test_verified_metadata_only_and_real_code_changes_survive():
    first = bytes.fromhex("6001") + trailer(b"\xa1\x64ipfs\x58\x22" + bytes(range(34)))
    second = bytes.fromhex("6002") + trailer(b"\xa1\x64solc\x43\x00\x06\x0c")
    assert normalized_node_ir(ir(first)) == (ir(bytes.fromhex("6001")), True)
    assert normalized_node_ir(ir(second)) == (ir(bytes.fromhex("6002")), True)
    assert normalized_node_ir(ir(first,False)) == (ir(first,False), False)
    for bad in (b"\x01\x02", b"\xa1\x64fake\x41A", b"\xa1\x64ipfs\x41A", b"\xa1\x64solc\x43abcX",
                b"\xa2\x64solc\x43abc\x64solc\x43def"):
        ops = ir(b"\x60"+trailer(bad))
        assert normalized_node_ir(ops) == (ops,False)


def test_file_renames_cover_cfg_calls_and_keep_inputs_intact():
    old, new = "vendor/library/C.sol", "node_modules/library/C.sol"
    k = ["C","f()","EXPRESSION",0,1]
    def graph(name):
        ref = {"filename":name,"key5":k}
        return {"nodes":[dict(ref,length=1,node_type="EXPRESSION",ir=[])],
                "cfg_edges":[{"source":ref,"target":ref,"kind":"next"}],
                "calls":[{"node":ref,"kind":"internal","callee":{"filename":name,"contract":"C","function":"f()"}}]}
    before, after = graph(old), graph(new)
    snapshot = copy.deepcopy(after)
    src = {old:b"a"}
    score = score_graphs(before,after,src,src,{new:b"a"},{},{},0,True,file_renames={old:new})
    assert score["exact"] and score["cfg_edges"]["matched"] == score["calls"]["matched"] == 1
    assert snapshot == after
    with pytest.raises(ValueError):
        score_graphs(before,after,{old:b"a","b":b"b"},src,{new:b"a"},{},{},0,True,file_renames={old:new,"b":new})



def test_struct_copy_respects_measured_versions_and_effective_codegen():
    from compile_repair.evaluation.benchmark import _STRUCT_COPY_REJECTED, mutation_sites
    from compile_repair.toolchain.solc import version_tuple
    assert len(_STRUCT_COPY_REJECTED) == 92
    assert max(_STRUCT_COPY_REJECTED, key=version_tuple) == "0.8.38"
    def sites(pragma, versions, settings):
        raw = ("pragma solidity " + pragma + "; contract RC { }").encode()
        base = dict(version="0.8.38", settings=settings, project_root=None)
        return mutation_sites(base, {"":raw}, {"":SourceLayout(raw)}, [], versions)
    now = ["0.8.38"]
    assert "unimplemented_feature" in sites(">=0.8.0", now, [])
    assert "unimplemented_feature" not in sites(">=0.8.0", now, ["--via-ir","--optimize"])
    assert "unimplemented_feature" not in sites(">=0.8.0", now+["0.8.39"], [])
    assert "unimplemented_feature" in sites("0.8.38", now+["0.8.39"], [])
    msg = "Copying of type struct P.S memory[] memory to storage is not supported in legacy (only supported by the IR pipeline)."
    assert classify_diagnostic(dict(kind="Error",message=msg))["category"] == "unimplemented_feature"


def test_all_package_importers_are_patched_and_internal_relative_imports_preserved(tmp_path):
    from compile_repair.evaluation.benchmark import _package_site, _sample_edits
    from compile_repair.toolchain.project import resolve_project
    root = tmp_path.resolve()
    pkg = "vendor/@openzeppelin/contracts/"
    sources = {
        "App.sol":('import "./Helper.sol"; import "./'+pkg+'A.sol"; contract App {}').encode(),
        "Helper.sol":('import {A as First} from "./'+pkg+'A.sol"; import "./'+pkg+'B.sol"; contract Helper {}').encode(),
        pkg+"A.sol":b'import "./B.sol"; contract A {}',
        pkg+"B.sol":b"contract B {}"}
    for name,raw in sources.items():
        target=root/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw)
    project=resolve_project(root,"App.sol")
    base=dict(project_root=str(root), remappings=[])
    plan=_package_site(base,sources,project.imports)
    assert plan["package"]=="@openzeppelin/contracts" and len(plan["import_edits"])==3
    site=("App.sol",0,0,plan,"package_dependency","project_assembly")
    damaged,edits=_sample_edits(base,sources,site,"unresolved_package_import")
    assert set(damaged)=={"App.sol","Helper.sol"} and len(edits)==5
    assert b'import "@openzeppelin/contracts/A.sol"' in damaged["App.sol"]
    assert b'from "@openzeppelin/contracts/A.sol"' in damaged["Helper.sol"]
    assert plan["file_renames"][pkg+"B.sol"]=="node_modules/@openzeppelin/contracts/B.sol"
    assert sources[pkg+"A.sol"].startswith(b'import "./B.sol"')


def test_short_vendor_name_requires_package_identity(tmp_path):
    from compile_repair.evaluation.benchmark import _package_layout
    root=tmp_path.resolve()
    name="lib/openzeppelin/contracts/math/Math.sol"
    assert _package_layout(root,name) is None
    declared=root/"lib/openzeppelin/contracts/package.json"
    declared.parent.mkdir(parents=True)
    declared.write_text('{"name":"@openzeppelin/contracts"}')
    prefix,package,proof=_package_layout(root,name)
    assert (prefix,package)==("lib/openzeppelin/contracts","@openzeppelin/contracts") and "sha256" in proof


def test_entry_inside_package_keeps_only_relocatable_dependencies(tmp_path):
    from compile_repair.evaluation.benchmark import _package_site, _sample_edits
    from compile_repair.toolchain.project import resolve_project

    root = tmp_path.resolve()
    prefix = "vendor/@openzeppelin/contracts/"
    entry, dependency = prefix + "Main.sol", prefix + "Math.sol"
    raw = {entry: b'import "./Math.sol"; contract Main {}', dependency: b"library Math {}"}
    (root / entry).parent.mkdir(parents=True)
    for name, data in raw.items():
        (root / name).write_bytes(data)
    base = dict(project_root=str(root), remappings=[])
    imports = resolve_project(root, entry).imports
    plan = _package_site(base, raw, imports)
    assert plan["file_renames"] == {dependency: "node_modules/@openzeppelin/contracts/Math.sol"}
    site = (entry, 0, 0, plan, "package_dependency", "project_assembly")
    damaged, edits = _sample_edits(base, raw, site, "unresolved_package_import")
    assert damaged == {entry: b'import "@openzeppelin/contracts/Math.sol"; contract Main {}'}
    assert len(edits) == 2

    raw[dependency] = b'import "./Main.sol"; library Math {}'
    (root / dependency).write_bytes(raw[dependency])
    assert _package_site(base, raw, resolve_project(root, entry).imports) is None
