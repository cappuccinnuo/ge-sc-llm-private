"""Additional acceptance boundary and environment separation checks."""
import ast
import copy
from pathlib import Path

import pytest

from scripts.node_sem.p2_acceptance import original_invariants, perturbations
from scripts.node_sem.text_view import build_text_view
from scripts.node_sem.tests.test_text_view import fixture_context


def test_nine_fields_and_original_edges_invariant(tmp_path):
    ctx=fixture_context(tmp_path)
    nodes=list(ctx["graphs"]["F0"])
    for graph in ctx["graphs"].values():
        graph.add_edge(nodes[0],nodes[1],key="test",edge_type="next")
    result=original_invariants(ctx)
    assert len(result["field_comparisons"])==9
    assert result["auxiliary_nodes"]==1 and result["base_edges_preserved"]
    broken=copy.deepcopy(ctx)
    broken["graphs"]["F3"].nodes[nodes[0]]["type_label"]=88
    with pytest.raises(AssertionError):original_invariants(broken)
    broken=copy.deepcopy(ctx)
    broken["graphs"]["F3"].remove_edge(nodes[0],nodes[1],"test")
    with pytest.raises(AssertionError):original_invariants(broken)


def test_real_acceptance_uses_direct_producer_not_carrier(tmp_path):
    ctx=fixture_context(tmp_path)
    baselines={v:build_text_view(ctx["task_id"],v,ctx) for v in ("original","anonymous")}
    results=perturbations(ctx,baselines)
    assert len(results)==6
    assert all(r.get("rejected") or r.get("rows_identical") for r in results.values())


def test_mando_production_modules_never_import_offline():
    root=Path(__file__).resolve().parents[1]
    for path in root.glob("*.py"):
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                assert all("offline" not in a.name.split(".") for a in node.names),path
            elif isinstance(node,ast.ImportFrom):
                assert "offline" not in (node.module or "").split("."),path


def test_text_producer_has_no_forbidden_attribute_reads():
    path=Path(__file__).resolve().parents[1]/"text_view.py"
    tree=ast.parse(path.read_text())
    forbidden={"label","type_label","method","node_info_vulnerabilities"}
    for node in ast.walk(tree):
        if isinstance(node,ast.Subscript):
            item=node.slice.value if isinstance(node.slice,ast.Index) else node.slice
            if isinstance(item,ast.Str):assert item.s not in forbidden
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="get":
            if node.args and isinstance(node.args[0],ast.Str):
                assert node.args[0].s not in forbidden
