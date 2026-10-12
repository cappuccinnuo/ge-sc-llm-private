import json
import pytest
from scripts.DFG.configuration import prepare_graph
from scripts.DFG.models import DDGConfig
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.tests.test_projection import assets,SOURCE
from scripts.DFG import cli
from scripts.labeling_v2.safe_graph import write_graph,read_graph

def test_off_is_exact_identity_on_only_adds_edges():
    g,_=assets()
    off,a=prepare_graph(g,config=DDGConfig(False))
    on,b=prepare_graph(g,{"a.sol":SOURCE},DDGConfig(True))
    assert fingerprint(off)==fingerprint(g)
    assert a["config"]["use_ddg"] is False
    assert b["invariants"]["ddg_edges"]>0
    with pytest.raises(ValueError):prepare_graph(on,config=DDGConfig(False))

def test_cli_roundtrip_and_no_overwrite(tmp_path,monkeypatch):
    monkeypatch.setattr(cli,"DDG_ROOT",tmp_path)
    g,_=assets();path=tmp_path/"base.gpickle";write_graph(g,path)
    sources=tmp_path/"sources";sources.mkdir()
    (sources/"a.sol").write_text(SOURCE)
    out=tmp_path/"on"
    a=cli.main(["--graph",str(path),"--source_dir",str(sources),
                "--output",str(out),"--use_ddg"])
    assert a["config"]["use_ddg"] and a["invariants"]["ddg_edges"]>0
    assert json.loads((out/"audit.json").read_text())["inputs"]["graph_sha256"]
    assert list(read_graph(out/"hcg.gpickle"))==list(g)
    with pytest.raises(FileExistsError):
        cli.main(["--graph",str(path),"--output",str(out)])

def test_cli_off_needs_no_source_or_parser(tmp_path,monkeypatch):
    monkeypatch.setattr(cli,"DDG_ROOT",tmp_path)
    monkeypatch.setattr(cli,"library_path",lambda: (_ for _ in ()).throw(AssertionError()))
    g,_=assets();path=tmp_path/"base.gpickle";write_graph(g,path)
    out=tmp_path/"off"
    a=cli.main(["--graph",str(path),"--output",str(out),"--no_ddg"])
    assert not a["config"]["use_ddg"]
    assert fingerprint(read_graph(out/"hcg.gpickle"))==fingerprint(g)

def test_stale_source_manifest_rejected_before_output(tmp_path,monkeypatch):
    monkeypatch.setattr(cli,"DDG_ROOT",tmp_path)
    g,_=assets();path=tmp_path/"base.gpickle";write_graph(g,path)
    (tmp_path/"a.sol").write_text(SOURCE)
    manifest=tmp_path/"sources.json"
    manifest.write_text(json.dumps({"a.sol":{"path":"a.sol","sha256":"wrong"}}))
    out=tmp_path/"bad"
    with pytest.raises(ValueError,match="checksum"):
        cli.main(["--graph",str(path),"--output",str(out),"--use_ddg",
                  "--source_manifest",str(manifest)])
    assert not out.exists()

def test_cli_output_cannot_leave_ddg_directory(tmp_path,monkeypatch):
    monkeypatch.setattr(cli,"DDG_ROOT",tmp_path/"safe")
    with pytest.raises(ValueError,match="below scripts/DFG"):
        cli.output_directory(tmp_path/"outside")

def test_positive_integer_resource_bound():
    for value in (0,-1,1.5,True):
        with pytest.raises(ValueError): DDGConfig(max_iterations=value)
