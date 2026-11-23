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


_MIGRATION_PATH = "vendor/math/C.sol"
_PACKAGE_PATH = "node_modules/math/C.sol"
_COUNTER_SOURCE = b"contract C { uint[] values; function f(uint a) public {} }"


def _counter_graph(path, names):
    a, ref, b, call_result = names
    def node(offset, ir):
        key = ["C", "f(uint256)", "EXPRESSION", offset, 1]
        return dict(filename=path, key5=key, node_type="EXPRESSION", length=1, ir=ir)
    first = node(0, [a + "(uint256) = a + 1", ref + "(uint256) -> values[" + a + "]",
                     b + "(uint256) = a + 2"])
    last = node(2, [call_result + "(None) = SOLIDITY_CALL require(bool)(" + a + ")", "RETURN " + ref])
    site = dict(filename=path, key5=last["key5"])
    edge = dict(source=dict(filename=path, key5=first["key5"]), target=site, kind="next")
    call = dict(node=site, operation="SolidityCall", kind="SolidityCall", ir_index=0, callee={"text":last["ir"][0]})
    declaration = dict(filename=path, contract="C", function="f(uint256)", declaration_kind="function")
    return {"schema":"compile-repair-project-graph-v1", "declarations":[declaration],
            "nodes":[first,last], "cfg_edges":[edge], "calls":[call]}


def _migration_pair():
    return (_counter_graph(_MIGRATION_PATH, ("TMP_1", "REF_2", "TMP_3", "TMP_4")),
            _counter_graph(_PACKAGE_PATH, ("TMP_73", "REF_12", "TMP_31", "TMP_9")))


def _migration_score(old, new, source=_COUNTER_SOURCE):
    files = {_MIGRATION_PATH:source}
    return score_graphs(old, new, files, files, {_PACKAGE_PATH:source}, {}, {}, 0, True,
                        file_renames={_MIGRATION_PATH:_PACKAGE_PATH})


def test_migration_counter_bijection_keeps_both_scores_and_graphs():
    old, new = _migration_pair()
    snapshot = copy.deepcopy((old, new))
    score = _migration_score(old, new, _COUNTER_SOURCE+b" /* TMP_73 */")
    assert score["exact"] and score["kept"]["equal"] == 2 and score["calls"]["matched"] == 1
    assert not score["raw_migration_score"]["exact"]
    assert score["raw_migration_score"]["kept"]["equal"] == 0
    proof = score["migration_counters"]
    assert proof["status"] == "verified" and proof["counter_count"] == 4
    assert proof["renamed"] == {"TMP_1":"TMP_73", "REF_2":"REF_12", "TMP_3":"TMP_31", "TMP_4":"TMP_9"}
    assert snapshot == (old, new)
    same_location = _counter_graph(_MIGRATION_PATH, ("TMP_73","REF_12","TMP_31","TMP_9"))
    src = {_MIGRATION_PATH:_COUNTER_SOURCE}
    plain = score_graphs(old, same_location, src, src, src, {}, {}, 0, True)
    assert not plain["exact"] and "raw_migration_score" not in plain


@pytest.mark.parametrize("difference", [
    "collision", "different_use", "operation", "type", "source_operand", "family",
    "missing_definition", "edge", "duplicate_edge", "call_target", "call_index",
    "old_counter_in_new_callee", "extra_node", "declaration", "metadata"])
def test_migration_rejects_non_counter_graph_changes(difference):
    old, new = _migration_pair()
    first, last = new["nodes"]
    call = new["calls"][0]
    if difference == "collision":
        first["ir"][2] = first["ir"][2].replace("TMP_31", "TMP_73")
    elif difference == "different_use":
        last["ir"][0] = last["ir"][0].replace("TMP_73", "TMP_31")
        call["callee"]["text"] = last["ir"][0]
    elif difference == "operation":
        first["ir"][0] = first["ir"][0].replace(" + ", " - ")
    elif difference == "type":
        first["ir"][0] = first["ir"][0].replace("uint256", "int256")
    elif difference == "source_operand":
        first["ir"][2] = first["ir"][2].replace("a + 2", "b + 2")
    elif difference == "family":
        first["ir"][1] = first["ir"][1].replace("REF_12", "TMP_12")
        last["ir"][1] = "RETURN TMP_12"
    elif difference == "missing_definition":
        old["nodes"][0]["ir"][2] = "RETURN TMP_3"
        first["ir"][2] = "RETURN TMP_31"
    elif difference == "edge":
        new["cfg_edges"][0]["kind"] = "false"
    elif difference == "duplicate_edge":
        new["cfg_edges"].append(new["cfg_edges"][0])
    elif difference == "call_target":
        call["callee"] = {"filename":_PACKAGE_PATH, "contract":"Other", "function":"f()"}
    elif difference == "call_index":
        call["ir_index"] = 1
    elif difference == "old_counter_in_new_callee":
        call["callee"]["text"] = call["callee"]["text"].replace("TMP_73", "TMP_1")
    elif difference == "extra_node":
        extra = copy.deepcopy(last)
        extra["key5"][3] += 1
        new["nodes"].append(extra)
    elif difference == "declaration":
        new["declarations"][0]["function"] = "unexpected()"
    else:
        first["declaration_kind"] = "modifier"
    score = _migration_score(old, new)
    assert not score["exact"] and score["migration_counters"]["status"] == "rejected"


@pytest.mark.parametrize("user_spelling", [
    b"uint TMP_1;", b'string x = "REF_12";', br'string x = "\x54MP_73";',
    br'string x = unicode"\u0054MP_73";', b'bytes x = hex"544d505f33";',
    b'string x = "TM" /* split */ "P_9";', b'string x = unicode"R" unicode"EF_2";',
    br'string x = "\q";'])
def test_source_identifiers_and_decoded_literals_prevent_renaming(user_spelling):
    old, new = _migration_pair()
    score = _migration_score(old, new, _COUNTER_SOURCE + user_spelling)
    assert not score["exact"] and score["migration_counters"]["status"] == "rejected"


def test_migration_checks_edges_between_recovered_nodes_even_when_raw_passes():
    raw = _COUNTER_SOURCE
    old = _counter_graph(_MIGRATION_PATH, ("TMP_1","REF_2","TMP_3","TMP_4"))
    new = _counter_graph(_PACKAGE_PATH, ("TMP_1","REF_2","TMP_3","TMP_4"))
    new["cfg_edges"].clear()
    _, deletion = apply_patches(raw, [Patch(0, len(raw), raw, b"", "remove")])
    _, inverse = apply_patches(b"", [Patch(0, 0, b"", raw, "restore")])
    score = score_graphs(old, new, {_MIGRATION_PATH:raw}, {}, {_PACKAGE_PATH:raw},
                         {_MIGRATION_PATH:deletion}, {_MIGRATION_PATH:inverse}, 0, True,
                         file_renames={_MIGRATION_PATH:_PACKAGE_PATH})
    assert score["raw_migration_score"]["exact"] and score["kept"]["units"] == 0
    assert not score["exact"] and score["migration_counters"]["status"] == "rejected"


def _tuple_pair():
    old, new = _migration_pair()
    for graph, name in ((old,"TUPLE_0"),(new,"TUPLE_1")):
        ops = graph["nodes"][0]["ir"]
        ops.extend([name+"(bool,bytes) = INTERNAL_CALL, C.pair()()",
                    "ok(bool) = UNPACK "+name+" index: 0",
                    "data(bytes) = UNPACK "+name+" index: 1"])
    return old, new


def test_verified_tuple_result_name_preserves_arity_and_unpack_uses():
    old, new = _tuple_pair()
    score = _migration_score(old, new)
    assert score["exact"] and not score["raw_migration_score"]["exact"]
    assert score["migration_counters"]["renamed"]["TUPLE_0"] == "TUPLE_1"


@pytest.mark.parametrize("difference", ["swapped_index","type_order","arity","undeclared_use","cross_family",
                                         "identifier","hex_literal","split_literal"])
def test_tuple_renaming_refuses_a_different_result_or_a_source_name(difference):
    old, new = _tuple_pair()
    source = _COUNTER_SOURCE
    ops = new["nodes"][0]["ir"]
    if difference == "swapped_index":
        ops[-2] = ops[-2].replace("index: 0","index: 1")
    elif difference == "type_order":
        ops[-3] = ops[-3].replace("bool,bytes","bytes,bool")
    elif difference == "arity":
        ops[-3] = ops[-3].replace("bool,bytes","bool")
    elif difference == "undeclared_use":
        ops[-1] = ops[-1].replace("TUPLE_1","TUPLE_7")
    elif difference == "cross_family":
        ops[-3:] = [op.replace("TUPLE_1","TMP_12") for op in ops[-3:]]
    elif difference == "identifier":
        source += b"uint TUPLE_0;"
    elif difference == "hex_literal":
        source += b'bytes x = hex"5455504c455f31";'
    else:
        source += br'string x = "\u0054U" "PLE_1";'
    score = _migration_score(old, new, source)
    assert not score["exact"] and score["migration_counters"]["status"] == "rejected"


_SWITCH_TEXT = b"switch x case 0 { x := 1 } default { x := 2 }"
_SWITCH_SOURCE = b"contract C { function f(uint x) public { assembly { " + _SWITCH_TEXT + b" } } }"
_SWITCH_START = _SWITCH_SOURCE.index(_SWITCH_TEXT)


def _switch_test_inputs(difference=None):
    import hashlib
    import json
    digest = lambda value: hashlib.sha256(value).hexdigest()
    source = _SWITCH_SOURCE
    names = ["switch_expr_{}_{}_{}__f_asm_0".format(_SWITCH_START,len(_SWITCH_TEXT),i) for i in (0,1)]
    if difference == "source_name":
        source += b" uint " + names[0].split("__")[0].encode() + b";"
    if difference == "literal":
        source += b' string s = "\\x73witch_" "' + names[1][7:].encode() + b'";'
    pair = _migration_pair()
    witnesses = {}
    for i,(side,filename,name,g) in enumerate(zip(("truth","repaired"),(_MIGRATION_PATH,_PACKAGE_PATH),names,pair)):
        if i and difference == "renamed_suffix":
            name += "_2"
        positions = {0:_SWITCH_START+7,2:_SWITCH_START+13}
        for node in g["nodes"]:
            node["key5"][3] = positions[node["key5"][3]]
        g["nodes"][0]["ir"].append(name+"(uint256) := x(uint256)")
        g["nodes"][1]["ir"].append("CONDITION "+name+" == 0")
        if i and difference == "changed_operand":
            g["nodes"][1]["ir"][-1] = g["nodes"][1]["ir"][-1].replace("== 0","== 1")
        if difference == "no_definition":
            g["nodes"][0]["ir"].pop()
        graph_digest = digest((json.dumps(g,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
        listed = [filename,"extra.sol"] if not i else ["extra.sol",filename]
        tree = {"nodeType":"YulSwitch","src":"{}:{}:{}".format(_SWITCH_START,len(_SWITCH_TEXT),i)}
        if i and difference == "wrong_file_id":
            tree["src"] = tree["src"][:-1]+"0"
        if i and difference == "wrong_span":
            tree["src"] = tree["src"].replace(":"+str(len(_SWITCH_TEXT))+":",":3:")
        if i and difference == "not_a_switch":
            tree["nodeType"] = "YulIf"
        trees = {filename:{"nodes":[tree]},"extra.sol":{"nodes":[]}}
        data = dict(sourceList=listed,sources={k:{"AST":v} for k,v in trees.items()})
        serialized = json.dumps(data).encode()
        files = {filename:source,"extra.sol":b""}
        project = dict(root="/unit",files=[dict(path="/unit/"+k,sha256=digest(v)) for k,v in files.items()],
                       source_units=[[k,k] for k in listed])
        records = [dict(path="/unit/"+k,ast_sha256=digest(json.dumps(v,sort_keys=True).encode())) for k,v in trees.items()]
        solc = dict(returncode=0,stdout_sha256=digest(serialized),cwd="/unit",settings=[],
                    compiler=dict(sha256="a"*64,version="0.8.2"))
        slither = dict(d3=True,graph_sha256=graph_digest,compiler_sha256="a"*64,project=project,
                       contract_coverage=dict(asts=records))
        if i and difference == "bad_graph":
            slither["graph_sha256"] = "0"*64
        if i and difference == "bad_stdout":
            solc["stdout_sha256"] = "0"*64
        if i and difference == "bad_ast":
            records[0]["ast_sha256"] = "0"*64
        if i and difference == "bad_closure":
            project["files"][0]["sha256"] = "0"*64
        if i and difference == "settings":
            solc["settings"] = ["--optimize"]
        witnesses[side] = dict(combined_json=serialized,result=dict(attempts=[dict(solc=solc,slither=slither)]))
    return pair, source, witnesses


def _switch_test_score(pair, source, witnesses):
    before = {_MIGRATION_PATH:source,"extra.sol":b""}
    after = {_PACKAGE_PATH:source,"extra.sol":b""}
    return score_graphs(pair[0],pair[1],before,before,after,{},{},0,True,
                        file_renames={_MIGRATION_PATH:_PACKAGE_PATH},migration_compilations=witnesses)


def test_switch_file_index_requires_both_recorded_compilations():
    pair, source, witnesses = _switch_test_inputs()
    raw = _switch_test_score(pair,source,None)
    assert not raw["exact"]
    score = _switch_test_score(pair,source,witnesses)
    assert score["exact"] and score["raw_migration_score"] == raw["raw_migration_score"]
    [site] = score["migration_counters"]["yul_switches"]
    assert site["src_before"].endswith(":0") and site["src_after"].endswith(":1")
    assert site["file"] == _MIGRATION_PATH and site["repaired_file"] == _PACKAGE_PATH


@pytest.mark.parametrize("difference",["settings","bad_graph","bad_stdout","bad_ast","bad_closure","wrong_file_id",
                                       "wrong_span","not_a_switch","renamed_suffix","source_name","literal",
                                       "changed_operand","no_definition"])
def test_switch_file_index_keeps_other_facts_strict(difference):
    pair, source, witnesses = _switch_test_inputs(difference)
    score = _switch_test_score(pair,source,witnesses)
    assert not score["exact"] and score["migration_counters"]["status"] == "rejected"


def test_checked_score_request_reads_both_compiler_witnesses(tmp_path):
    import hashlib
    import json
    from compile_repair.evaluation.benchmark import score_request
    pair, source, witnesses = _switch_test_inputs()
    def file_ref(name, value):
        raw = value if isinstance(value,bytes) else json.dumps(value).encode()
        file = tmp_path/name
        file.write_bytes(raw)
        return dict(path=str(file),sha256=hashlib.sha256(raw).hexdigest())
    refs = {side:{key:file_ref(side+key,data) for key,data in value.items()} for side,value in witnesses.items()}
    files = []
    for i,(name,code) in enumerate(((_MIGRATION_PATH,source),("extra.sol",b""))):
        ref = file_ref(str(i),code)
        files.append(dict(name=name,original=ref,damaged=ref,repaired=ref))
    request = dict(files=files,truth_graph=file_ref("truth",pair[0]),repaired_graph=file_ref("candidate",pair[1]),
                   solc_returncode=0,d3=True,file_renames={_MIGRATION_PATH:_PACKAGE_PATH},migration_compilations=refs)
    path = tmp_path/"request.json"
    path.write_text(json.dumps(request))
    assert score_request(path,tmp_path/"score")["summary"]["exact"]


@pytest.mark.parametrize("other_spaces,same", [("  ",True),(" ",False),("\t",False)])
def test_typed_array_definition_spacing_is_recognized_but_still_compared(other_spaces, same):
    old, new = _migration_pair()
    for graph, name, spaces in ((old,"TMP_102","  "),(new,"TMP_319",other_spaces)):
        graph["nodes"][0]["ir"].append(name+"(uint256[])"+spaces+"= new uint256[](2)")
        graph["nodes"][1]["ir"].append("RETURN "+name)
    score = _migration_score(old,new)
    assert score["exact"] is same
    if same:
        assert score["migration_counters"]["renamed"]["TMP_102"] == "TMP_319"
    else:
        assert score["migration_counters"]["status"] == "rejected"
