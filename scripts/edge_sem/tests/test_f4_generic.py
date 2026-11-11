"""EP4 task-generic production boundary and immutable rebuild tests."""
import ast
import copy
import json
from pathlib import Path
import pytest
from scripts.edge_sem.io import ROOT
from scripts.edge_sem.build_f4 import load_edges, inspect_file
from scripts.edge_sem.guard_edges import task_guard_audit
from scripts.edge_sem.recon.ep4_rebuild import compare_edge_files
from scripts.edge_sem.tests.test_build_f4_calls import synthetic


@pytest.mark.parametrize("name", ["build_f4.py", "guard_edges.py"])
def test_production_has_no_recon_import(name):
    tree=ast.parse((ROOT/"scripts/edge_sem"/name).read_text())
    for n in ast.walk(tree):
        if isinstance(n,ast.ImportFrom):
            assert "recon" not in (n.module or "").split(".")
        if isinstance(n,ast.Import):
            assert all("recon" not in a.name.split(".") for a in n.names)


@pytest.mark.parametrize("version", ["edgesem-f4-ep2-v1","edgesem-f4-ep3-v1"])
def test_loader_rejects_historical_versions_before_current_source_check(tmp_path, version):
    p=tmp_path/"manifest.json"
    p.write_text(json.dumps({"version":version}))
    with pytest.raises(ValueError,match="manifest version"):
        load_edges(p)


def test_rebuild_byte_comparison_rejects_changed_line(tmp_path):
    a,b=tmp_path/"old",tmp_path/"new"
    a.write_bytes(b'{"src":1,"dst":2}\n')
    b.write_bytes(a.read_bytes())
    assert compare_edge_files(a,b)["byte_identical"]
    b.write_bytes(b'{"src":1,"dst":3}\n')
    with pytest.raises(ValueError,match="byte-for-byte"):compare_edge_files(a,b)


def test_guard_statistics_do_not_require_historical_census():
    source,graph=synthetic()
    edges,audit=inspect_file("ep2.sol",source,graph)
    output=task_guard_audit(graph,[audit],edges)
    assert output["reproduction_pass"] is None
    assert output["per_file_reproduction"]==[]
    assert output["nonmodifier_mapping_pass"]
    assert output["counts"]["edges"]==sum(r["relation"]=="GUARDS" for r in edges)
