from scripts.DFG.ddg_builder import DDGBuilder
from scripts.DFG.frontend import text

def build(body,version="^0.5.17"):
    s="pragma solidity "+version+"; contract C {function f(uint x,bool flag) public returns(uint) {"+body+"}}"
    r=DDGBuilder().analyze_source(s,"a.sol")
    assert r.stats["functions_supported"]==1,r.diagnostics
    return r

def pairs(result,name):
    def code(span):return result.view.raw[span.start:span.end].decode()
    return {(code(f.definition.anchor),code(f.use.anchor)) for f in result.facts
            if f.symbol.endswith(":"+name)}

def test_sequential_kill_exact_edges():
    r=build("x=1; x=2; return x;")
    assert pairs(r,"x")=={("x=2;","return x;")}

def test_if_merge_keeps_both_definitions():
    r=build("x=1; if(flag){x=2;} return x;")
    assert pairs(r,"x")=={("x=1;","return x;"),("x=2;","return x;")}

def test_returned_branch_does_not_reach_return_after_if():
    r=build("x=1; if(flag){x=2; return x;} x=3; return x;")
    uses=[f for f in r.facts if f.symbol.endswith(":x")]
    last=max(f.use.anchor.start for f in uses)
    assert {r.view.raw[f.definition.anchor.start:f.definition.anchor.end] for f in uses
            if f.use.anchor.start==last}=={b"x=3;"}

def test_unknown_rhs_still_kills_old_scalar_definition():
    r=build("x=1; x=unknownState; return x;")
    assert pairs(r,"x")=={("x=unknownState;","return x;")}

def test_forward_dedup_and_self_facts():
    r=build("x=x+1; return x;")
    anchors={a for f in r.facts for a in (f.definition.anchor,f.use.anchor)}
    mapping={a:i for i,a in enumerate(sorted(anchors))}
    edges,evidence,stats=DDGBuilder().projected_edges(r.facts+r.facts,mapping)
    assert all(d["edge_type"]=="DATA_DEF_USE" and s!=t for s,t,d in edges)
    assert len({(s,t) for s,t,d in edges})==len(edges)
    assert stats["duplicate_projected_pairs"]>0

def test_legacy_default_before_declaration():
    r=build("x=a; uint a=3; return x;","^0.4.25")
    use=[f for f in r.facts if f.symbol.endswith(":a")][0]
    assert use.definition.anchor.role=="function_definition"

def test_loop_carried_defs_and_break():
    r=build("x=1; while(flag){x=x+1; if(x>10)break;} return x;")
    assert ("x=x+1;","x=x+1;") in pairs(r,"x")
    assert ("x=1;","return x;") in pairs(r,"x")

def test_unsupported_and_budget_keep_diagnostics():
    src="pragma solidity ^0.5.17; contract C {function f(uint[] memory x) public {}}"
    r=DDGBuilder().analyze_source(src,"x.sol")
    assert not r.facts and r.stats["functions_total"]==1
    assert r.diagnostics[0]["kind"]=="function_fallback"
    r=DDGBuilder(1).analyze_source("pragma solidity ^0.5.17; contract C {function f(uint x) public returns(uint){x++;return x;}}","x.sol")
    assert not r.facts and "converge" in r.diagnostics[-1]["reason"]
