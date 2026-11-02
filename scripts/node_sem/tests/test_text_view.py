"""Exact strings, producer perturbations and graph-subset contracts for NS-P2."""
import copy
import hashlib
import json
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import anonymize
from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import node_code_view
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
from scripts.DFG.projection import ANCHOR, decoded
from scripts.DFG.models import Unsupported
from scripts.node_sem.text_view import build_text_view, write_views, sha_text
from scripts.node_sem.carrier import _aligned, MODALITY_VERSION
from scripts.node_sem.tests.carrier_fixtures import make_spelling_fixture
from scripts.node_sem.tests.test_carrier import _generic

SOURCE = """pragma solidity ^0.5.11;
interface I { function ping(uint z) external returns(uint); }
library L { function twice(uint z) internal returns(uint) { return z + z; } }
contract Base { uint inherited; }
contract Sample is Base {
    struct Record { uint amount; address who; }
    uint state;
    modifier allowed(uint n) { require(n > 0); _; }
    constructor(uint n) public { state = n; }
    function run(uint n) public view allowed(n) returns (uint) {
        uint x = n;
        if (n > 0) { x += 1; } else if (n == 0) { x = 2; }
        for (uint i = 0; i < n; i++) { if (i == 2) continue; x += i; }
        while (x < n) { x++; }
        return x;
    }
}
"""
ROLES = {
    "contract_declaration": "contract_declaration",
    "library_declaration": "library_declaration",
    "interface_declaration": "interface_declaration",
    "function_definition": "function_definition",
    "modifier_definition": "modifier_definition",
    "constructor_definition": "constructor_definition",
    "struct_declaration": "struct_declaration",
    "variable_declaration": "new_variable",
    "variable_declaration_statement": "new_variable",
    "expression_statement": "expression_statement",
    "return_statement": "return",
    "if_statement": "if", "for_statement": "for", "while_statement": "while",
    "continue_statement": "continue_statement",
}


def fixture_context(tmp_path, source=SOURCE):
    file = "example.sol"
    path = tmp_path / file
    path.write_text(source)
    view = ProjectionView(source, file)
    graph = nx.MultiDiGraph()
    for key, ident in view.compat_ids.items():
        ast = view.compat_nodes[key]
        if ast.type not in ROLES:
            continue
        typ = ROLES[ast.type]
        # variable_declaration can be contained in a declaration statement;
        # each exact AST ID has at most one graph node in this fixture.
        code = view.compat[ast.start_byte:ast.end_byte].decode()
        graph.add_node(str(ident), node_type=typ, source_file=file, code=code,
                       label="prefix-{}-{}-{}-{}".format(ident, typ, ast.start_point[0]+1, ast.end_point[0]+1),
                       node_source_code_lines=[ast.start_point[0]+1, ast.end_point[0]+1],
                       node_info_vulnerabilities=None, method="ignored", type_label=0,
                       token=np.zeros(512, dtype=np.float32))
    for role, ast_type in (("end_if", "if_statement"), ("end_loop", "for_statement")):
        ast = next(n for n in view.compat_nodes.values() if n.type == ast_type)
        graph.add_node(role, node_type=role, source_file=file, label="synthetic",
                       code=view.compat[ast.start_byte:ast.end_byte].decode(),
                       node_source_code_lines=[ast.start_point[0]], token=np.zeros(512, dtype=np.float32))
    result = anonymize(source)
    assert result["status"] == "renamed"
    codes, _ = node_code_view(graph, file, source, result)
    rows = [dict(original_graph_node_id=n, code_sha256=sha_text(a["code"]),
                 rewritten_code_sha256=sha_text(codes[n])) for n, a in graph.nodes(data=True)]
    enhanced = copy.deepcopy(graph)
    enhanced.add_node("aux", node_type="env_source", source_file=file,
                      code="msg.sender", token=np.zeros(512, dtype=np.float32))
    return dict(task_id="fictional_node", graphs={"F0": graph, "F3": enhanced},
                order=list(graph), sources={file: ref(path)}, source_text={file: source},
                naming={file: result}, feature_rows=rows, provenance={})


def test_exact_ast_texts_and_all_node_types(tmp_path):
    context = fixture_context(tmp_path)
    rows = build_text_view(context["task_id"], "original", context)
    texts = {r["text"] for r in rows}
    assert "function run(uint n) public view allowed(n) returns (uint)" in texts
    assert "modifier allowed(uint n)" in texts
    assert "constructor(uint n) public" in texts
    assert "contract Sample is Base" in texts
    assert "struct Record { uint amount; address who; }" in texts
    assert "if ( n > 0 )" in texts and "if ( n == 0 )" in texts
    assert "for (uint i = 0; i < n; i++)" in texts
    assert "while ( x < n )" in texts
    assert "return x;" in texts and "continue;" in texts
    assert "<END_IF>" in texts and "<END_LOOP>" in texts
    assert "msg.sender" in texts
    expected = set(ROLES.values()) | {"end_if", "end_loop", "env_source"}
    assert {r["node_type"] for r in rows} == expected
    assert not any(r["cut_mode"] == "fallback" for r in rows)
    assert rows[-1]["row_key"] == "env:example.sol:msg.sender"
    assert all("example.sol" not in r["text"] and "@L" not in r["text"] for r in rows)


@pytest.mark.parametrize("view", ["original", "anonymous"])
@pytest.mark.parametrize("change", ["forbidden", "prefix", "anchor", "source", "order"])
def test_direct_producer_perturbations(tmp_path, view, change):
    ctx = fixture_context(tmp_path)
    baseline = build_text_view(ctx["task_id"], view, ctx)
    graph = copy.deepcopy(ctx["graphs"]["F3"])
    ordinary = next(n for n,a in graph.nodes(data=True) if a["node_type"] == "function_definition")
    if change == "forbidden":
        for _, attrs in graph.nodes(data=True):
            attrs.update(node_info_vulnerabilities=[{"lines":[999]}], method="unsafe-target", type_label=99)
    elif change == "prefix":
        for _, attrs in graph.nodes(data=True):
            match = ANCHOR.search(decoded(attrs.get("label", "")))
            if match:
                attrs["label"] = "adversarial text and line 9999-" + match.group(0)
    elif change == "anchor":
        graph.nodes[ordinary]["label"] = "broken anchor"
    elif change == "source":
        graph.nodes[ordinary]["code"] = "mismatched source"
    elif change == "order":
        reordered = nx.MultiDiGraph()
        reordered.add_nodes_from(reversed(list(graph.nodes(data=True))))
        graph = reordered
    if change in ("anchor", "source", "order"):
        with pytest.raises((ValueError, Unsupported)):
            build_text_view(ctx["task_id"], view, ctx, graph)
    else:
        before = graph_fingerprint(graph)
        assert build_text_view(ctx["task_id"], view, ctx, graph) == baseline
        assert graph_fingerprint(graph) == before


def test_views_inverse_rename_and_exclusive_write(tmp_path):
    ctx = fixture_context(tmp_path)
    output = tmp_path / "text"
    refs = write_views(ctx["task_id"], output, ctx)
    manifests = {v: json.loads(Path(r["path"]).read_text()) for v,r in refs.items()}
    for record in manifests.values():
        assert record["inverse_rename_exact"] and record["cut_modes_equal"]
        assert set(record["profiles"]) == {"F0", "F3"}
    with pytest.raises(FileExistsError):
        write_views(ctx["task_id"], output, ctx)


def test_missing_slice_field_falls_back_without_reclassifying_bad_anchor(tmp_path):
    from scripts.node_sem.text_view import cut_span
    ctx = fixture_context(tmp_path)
    view = ProjectionView(SOURCE, "example.sol")
    ast = next(n for n in view.compat_nodes.values() if n.type=="return_statement")
    # Own-function boundary probe, no frozen monkeypatch.
    result = cut_span(ast, view, "if")
    assert result[-2:] == ("fallback", "missing_condition")


def test_f3_modality_superset_keeps_original_order_and_selects_aux_by_key(tmp_path):
    fixture = make_spelling_fixture(tmp_path, True)
    _, view, _, _, _ = _generic(fixture, tmp_path)
    full = fixture["graph"]
    base = copy.deepcopy(full)
    base.remove_nodes_from([n for n,a in base.nodes(data=True) if a["node_type"]=="env_source"])
    view["profiles"]["F0"] = {"graph_fingerprint":graph_fingerprint(base)}
    # F3 graph fixture interleaves env nodes; manifest canonically appends them.
    orig = [r for r in view["rows"] if r["node_type"]!="env_source"]
    aux = sorted((r for r in view["rows"] if r["node_type"]=="env_source"), key=lambda r:r["row_key"])
    view["rows"] = orig + aux
    selected = _aligned(view, full, fixture["task_id"], "anonymous", 3)
    assert [r["row_key"] for r in selected] == [
        "env:{}:{}".format(a["source_file"],a["code"]) if a["node_type"]=="env_source" else n
        for n,a in full.nodes(data=True)]
    assert _aligned(view, base, fixture["task_id"], "anonymous", 3) == orig
    bad=copy.deepcopy(view);bad["rows"].append(dict(orig[0],row_key="extra-original"))
    with pytest.raises(ValueError): _aligned(bad,base,fixture["task_id"],"anonymous",3)
    bad=copy.deepcopy(view);bad["rows"][0],bad["rows"][1]=bad["rows"][1],bad["rows"][0]
    with pytest.raises(ValueError): _aligned(bad,base,fixture["task_id"],"anonymous",3)
    bad=copy.deepcopy(view);bad["rows"][-1]["row_key"]="env:train.sol:not-an-env"
    with pytest.raises(ValueError): _aligned(bad,base,fixture["task_id"],"anonymous",3)
    bad=copy.deepcopy(view);bad["rows"].pop(0)
    with pytest.raises(ValueError): _aligned(bad,base,fixture["task_id"],"anonymous",3)
