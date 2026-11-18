"""CP3 closed-project boundaries, common pipeline and approved file identities."""
import hashlib
import io
import json
from pathlib import Path
import pytest
from compile_repair.core.model import CompilationUnit
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.project import (resolve_project, materialize_project,
    import_directives, source_unit_name, parse_remapping, verify_project, compile_project,
    project_command, slither_arguments, ProjectIndex)
from compile_repair.toolchain.slither import run_slither
from compile_repair.tests.test_production import production_required, trusted_compilers

F=Path(__file__).parent/"fixtures"

def test_all_import_forms_and_comments():
    raw=(b'// import "fake.sol";\nimport "./A.sol"; import * as X from "./B.sol";'
         b'import {C as D, E} from "./C.sol"; import "./D.sol" as D;'
         b'contract C { string s="import \\"fake.sol\\";"; }')
    rows=list(import_directives(raw))
    assert [r["path"] for r in rows]==["./A.sol","./B.sol","./C.sol","./D.sol"]
    assert all(r["supported_literal"] for r in rows)
    for r in rows: assert raw[r["start"]:r["end"]].startswith(b"import")

@pytest.mark.parametrize("parent,imported,remaps,expected",[
 ("a/b/C.sol","../D.sol",(),"a/D.sol"),
 ("a/b/C.sol","pkg//D.sol",(),"pkg//D.sol"),
 ("a/C.sol","./D.sol",("a/=one/","a/C.sol:a/=two/"),"two/D.sol"),
 ("a/C.sol","pkg/n/X.sol",("pkg/=a/","pkg/n/=b/"),"b/X.sol"),
 ("a/C.sol","pkg/X.sol",("pkg/=a/","a/=b/"),"a/X.sol"),
 ("a/C.sol","pkg/X.sol",("pkg/=a","pkg/=b"),"bX.sol")])
def test_documented_vfs_and_remapping_rules(parent,imported,remaps,expected):
    assert source_unit_name(parent,imported,remaps)==expected

@pytest.mark.parametrize("bad",["", "=target", "--optimize=x", "pkg/", "x=bad\n"])
def test_reject_option_like_or_malformed_remap(bad):
    with pytest.raises(ValueError): parse_remapping(bad)

def test_closure_cycles_missing_candidates_and_read_only(tmp_path):
    (tmp_path/"A.sol").write_text('import "./B.sol"; import "./missing/C.sol"; import "@pkg/x/Q.sol"; contract A {}')
    (tmp_path/"B.sol").write_text('import "./A.sol"; contract B {}')
    (tmp_path/"C.sol").write_text("contract C {}")
    before={p:p.read_bytes() for p in tmp_path.iterdir()}
    p=resolve_project(tmp_path,"A.sol")
    assert len(p.files)==2
    assert [x["category"] for x in p.issues]==["missing_relative_file","unresolved_package_import"]
    assert p.issues[0]["candidate_kind"]=="unique"
    assert p.issues[1]["package"]=="@pkg/x"
    assert all(f.read_bytes()==raw for f,raw in before.items())
    (tmp_path/"other").mkdir(); (tmp_path/"other/C.sol").write_text("contract X {}")
    p=resolve_project(tmp_path,"A.sol")
    assert p.issues[0]["candidate_kind"]=="multiple"

def test_utf8_filenames_and_symlink_escape(tmp_path):
    (tmp_path/"A.sol").write_text('import "./例.sol"; contract A {}')
    (tmp_path/"例.sol").write_text("contract B {}")
    project=resolve_project(tmp_path,"A.sol")
    assert len(project.files)==2 and not project.issues
    (tmp_path/"Escape.sol").symlink_to(tmp_path/"例.sol")
    (tmp_path/"A.sol").write_text('import "./Escape.sol"; contract A {}')
    project=resolve_project(tmp_path,"A.sol")
    assert project.issues[0]["reason"]=="symlink_import_not_followed"

def test_outside_root_is_issue_not_a_read(tmp_path):
    child=tmp_path/"project";child.mkdir()
    (tmp_path/"outside.sol").write_text("contract Secret {}")
    (child/"A.sol").write_text('import "../outside.sol"; contract A {}')
    p=resolve_project(child,"A.sol")
    assert len(p.files)==1 and p.issues[0]["reason"]=="import_outside_project"

def test_missing_closure_never_runs_compiler(tmp_path):
    root=tmp_path/"p";root.mkdir()
    (root/"A.sol").write_text('import "./missing.sol"; contract A {}')
    project=resolve_project(root,"A.sol")
    unit=CompilationUnit("test",project.files)
    def forbidden(*args,**kwargs): raise AssertionError("unresolved source reached compiler")
    store=ArtifactStore(tmp_path/"run")
    record=repair_unit(unit,{},store,io.StringIO(),project=project,project_compile_fn=forbidden)
    assert record.reason=="unresolved_imports" and record.attempts[0]["stage"]=="project_assembly"

def test_all_closure_integrity_checked(tmp_path):
    root=tmp_path/"p";root.mkdir()
    (root/"A.sol").write_text('import "./B.sol"; contract A {}')
    (root/"B.sol").write_text("contract B {}")
    p=resolve_project(root,"A.sol")
    store=ArtifactStore(tmp_path/"out"); copied=materialize_project(p,store,"tree")
    assert copied.files[1].sha256==p.files[1].sha256
    (root/"B.sol").write_text("contract Modified {}")
    with pytest.raises(ValueError,match="Project source changed"): verify_project(p)
    verify_project(copied)

@pytest.mark.parametrize("version",["0.4.12","0.4.24","0.5.17","0.8.38"])
def test_production_project_same_parameters_and_full_d3(tmp_path,version):
    production_required()
    original=resolve_project(F/"cp3_project","Main.sol",["@vendor/=vendor/"])
    store=ArtifactStore(tmp_path/"project")
    copy=materialize_project(original,store,"copy")
    compiler=trusted_compilers()[version]
    compiled=compile_project(copy,compiler)
    assert compiled.returncode==0
    target,kwargs=slither_arguments(copy,compiler)
    assert target==copy.entry and kwargs["solc_working_dir"]==compiled.cwd
    assert list(compiled.command)==project_command(copy,compiler)
    analysis=run_slither(compiled,profile="production",project=copy)
    assert analysis["d3"] and analysis["d3_a"] and analysis["d3_b"]
    assert analysis["graph"]["schema"]=="compile-repair-project-graph-v1"
    assert set(n["filename"] for n in analysis["nodes"])=={"Main.sol","sub/Base.sol","vendor/Numbers.sol"}
    assert analysis["command"]["solc_remaps"]==["@vendor/=vendor/"]
    verify_project(original)

def test_approved_project_file_identity_preserves_duplicate_key5(tmp_path):
    production_required()
    project=resolve_project(F/"cp3_alias","Main.sol")
    unit=CompilationUnit("alias",project.files,known_version="0.8.38")
    store=ArtifactStore(tmp_path/"alias")
    with store.journal("invocations.jsonl") as journal:
        record=repair_unit(unit,trusted_compilers(),store,journal,project=project)
    assert record.status=="success"
    graph=json.loads((store.path/"units/alias/graph.json").read_text())
    assert len(graph["nodes"])==4
    keys=[json.dumps(n["key5"]) for n in graph["nodes"]]
    assert len(set(keys))==2
    ids={(n["filename"],json.dumps(n["key5"])) for n in graph["nodes"]}
    assert len(ids)==4
    for edge in graph["cfg_edges"]:
        for side in ("source","target"):
            assert (edge[side]["filename"],json.dumps(edge[side]["key5"])) in ids
    assert set(record.provenance)=={f.path for f in project.files}
    assert all(n["provenance"]=="original" for n in graph["nodes"])

def test_directory_cli_expands_entries_with_same_remapping(tmp_path):
    production_required()
    from compile_repair.cli import main
    import shutil
    root=tmp_path/"project"
    shutil.copytree(str(F/"cp3_project"),str(root))
    before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob("*.sol")}
    out=tmp_path/"out"
    assert main(["repair",str(root),"--known-version","0.4.12",
                 "--remapping","@vendor/=vendor/","--output",str(out)])==0
    records=[json.loads(x) for x in (out/"manifest.jsonl").read_text().splitlines()]
    assert len(records)==3 and all(r["status"]=="success" for r in records)
    assert sorted(len(r["inputs"]) for r in records)==[1,1,3]
    assert all(p.read_bytes()==before[str(p.relative_to(root))] for p in root.rglob("*.sol"))

def test_closure_version_conflict_stops_before_any_tool(tmp_path):
    root=tmp_path/"project";root.mkdir()
    (root/"A.sol").write_text('pragma solidity ^0.4.12; import "./B.sol"; contract A {}')
    (root/"B.sol").write_text('pragma solidity ^0.5.0; contract B {}')
    project=resolve_project(root,"A.sol")
    def forbidden(*args,**kwargs):raise AssertionError("Empty interval reached compiler")
    store=ArtifactStore(tmp_path/"out")
    record=repair_unit(CompilationUnit("conflict",project.files),{},store,io.StringIO(),
                       project=project,project_compile_fn=forbidden)
    assert record.flags==["unsupported_version_constraints"]
    assert "across compilation unit" in record.attempts[0]["error_first_line"]

def test_project_calls_keep_callee_file_namespace(tmp_path):
    production_required()
    root=tmp_path/"project";root.mkdir()
    for name in ["A.sol","B.sol"]:(root/name).write_bytes((F/"cp3_alias"/name).read_bytes())
    (root/"Main.sol").write_text('pragma solidity ^0.8.0;\n'
        'import {C as A} from "./A.sol"; import {C as B} from "./B.sol";\n'
        'contract Main { function useBoth(A a, B b) public view returns(uint) { return a.f()+b.f(); } }')
    project=resolve_project(root,"Main.sol")
    store=ArtifactStore(tmp_path/"out")
    with store.journal("invocations.jsonl") as journal:
        record=repair_unit(CompilationUnit("calls",project.files,"0.8.38"),
                           trusted_compilers(),store,journal,project=project)
    assert record.status=="success"
    graph=json.loads((store.path/"units/calls/graph.json").read_text())
    calls=[r for r in graph["calls"] if r["kind"]=="high-level"]
    assert len(calls)==2
    assert {r["callee"]["filename"] for r in calls}=={"A.sol","B.sol"}
    assert all(r["node"]["filename"]=="Main.sol" for r in calls)
