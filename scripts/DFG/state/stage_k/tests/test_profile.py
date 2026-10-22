"""Static parser/semantic fixtures; no solc compilation is claimed."""
import pytest
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_f.frontend import StageFSourceView
from scripts.DFG.state.stage_f.versioning import available
from scripts.DFG.state.stage_j.analyzer import analyze_view
from scripts.DFG.state.stage_j.configuration import DDGConfig
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from scripts.DFG.state.stage_k.pipeline import prepare_graph
from scripts.DFG.state.stage_j import pipeline as old
from scripts.DFG.state.stage_j.tests.test_pipeline import graph,typed
from scripts.DFG.graph_audit import fingerprint

SRC="pragma solidity >=0.5.9;contract C{uint s;function f() public returns(uint){require(s>0);if(s==0){revert();}s=1;return s;}}"

def test_before_rejected_after_supported_without_compilation():
    before=StageFSourceView(SRC,"p.sol");after=SupportedSourceView(SRC,"p.sol")
    assert not available(before,"require") and available(after,"require")
    assert analyze_view(before)[0][0].ir is None
    result=analyze_view(after)[0][0]
    assert result.ir is not None and len(result.facts)==1
    assert after.sha256==before.sha256 and after.raw==before.raw
    assert after.version_evidence["exact_compiler"] is None
    assert after.version_evidence["domain_restricted"]
    assert after.version_interval==((0,5,9),(0,9,0))

@pytest.mark.parametrize("pragma",["^0.5.9","0.5.17",">=0.5.9 <0.6.0"])
def test_closed_intervals_unchanged(pragma):
    source=SRC.replace(">=0.5.9",pragma)
    a,b=StageFSourceView(source,"p.sol"),SupportedSourceView(source,"p.sol")
    assert a.version_interval==b.version_interval
    assert not b.version_evidence["domain_restricted"]
    assert analyze_view(a)[0][0].facts==analyze_view(b)[0][0].facts

@pytest.mark.parametrize("pragma",[">=0.4.0",">=0.9.0","^0.3.0"])
def test_scope_boundary_and_future_only_still_fallback(pragma):
    with pytest.raises(Unsupported):
        SupportedSourceView(SRC.replace(">=0.5.9",pragma),"p.sol")

def test_missing_evidence_not_invented():
    with pytest.raises(Unsupported):
        SupportedSourceView(SRC.replace("pragma solidity >=0.5.9;",""),"p.sol")

def test_unsupported_old_builtin_not_reenabled():
    v=SupportedSourceView(SRC,"p.sol")
    assert not available(v,"suicide")
    oldv=SupportedSourceView(SRC.replace(">=0.5.9","^0.4.0"),"p.sol")
    assert not available(oldv,"require")

def test_profile_does_not_bypass_user_function_binding():
    source="pragma solidity >=0.5.9;contract C{uint s;function revert() internal{}function f() public returns(uint){s=1;revert();s=2;return s;}}"
    view=SupportedSourceView(source,"p.sol")
    results,records=analyze_view(view)
    fn=next(x for x in results if x.function==records[1]["function"])
    # User call remains an ordinary call/HAVOC, not a builtin terminator.
    assert fn.ir is not None and fn.facts
    from scripts.DFG.call_binding import NON_BUILTIN
    assert any(e["call_name"]=="revert" and e["classification"]==NON_BUILTIN
               for e in fn.binding_evidence["calls"])
    assert any(f.definition.kind=="WRITE" and f.use.kind=="READ" for f in fn.facts)

def test_pipeline_preserves_graph_and_freezes_original_frontend():
    g=graph(SRC);fp=fingerprint(g)
    a,aa=old.prepare_graph(g,{"p.sol":SRC})
    b,bb=prepare_graph(g,{"p.sol":SRC})
    assert fingerprint(g)==fp
    assert typed(a)<=typed(b)
    assert bb["files"]["p.sol"]["version_evidence"]["domain_restricted"]
    assert "STATE_DEF_USE" in bb["relation_counts"]
    assert old.prepare_graph.__globals__["StageFSourceView"] is StageFSourceView
    off,audit=prepare_graph(g,config=DDGConfig(use_ddg=False))
    assert fingerprint(off)==fp
