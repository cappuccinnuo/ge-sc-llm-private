"""Event-order specifications are static candidates, not solc/human-certified."""
import copy
import pytest
from dataclasses import asdict,replace
from scripts.DFG.state.stage_f.analyzer import analyze_source
from scripts.DFG.state.stage_f.relations import order_relations,read_call_write,validate_witness
from scripts.DFG.state.stage_f.projection import projected_file,materialize,assert_preserved
from scripts.DFG.state.tests.test_projection import fixture
from scripts.DFG.graph_audit import fingerprint
def source(body,decl="uint s;uint t;",args="address payable to"):
 return "pragma solidity 0.5.17;contract C{"+decl+"function f("+args+") public returns(uint){"+body+"}}"
def run(body,decl="uint s;uint t;",args="address payable to"):
 v,rs=analyze_source(source(body,decl,args));assert rs[0].status=="supported_subset",rs[0].diagnostics
 return v,rs[0]
def same(r):return [p for p in read_call_write(r) if p["pattern"]=="READ_CALL_WRITE_SAME_LOCATION"]
def test_read_call_write_positive_and_opaque_state():
 _,r=run("uint a=s;to.transfer(a);s=0;return a;")
 assert len(same(r))==1 and not r.facts
 for p in read_call_write(r):assert validate_witness(r.ir,p["cfg_witness"])
 assert any(p["origin"].startswith("ENTRY_UNKNOWN") for p in r.unknown_reads)
def test_write_call_read_is_not_same_pattern_or_defuse():
 _,r=run("s=1;to.transfer(1);return s;")
 assert not same(r) and not r.facts and any(x["origin"].startswith("HAVOC") for x in r.unknown_reads)
def test_different_roots_not_same_location():
 _,r=run("uint a=s;to.transfer(a);t=0;return a;")
 ps=read_call_write(r);assert not same(r) and any(x["pattern"]=="READ_CALL_WRITE_DIFFERENT_LOCATION" for x in ps)
def test_mapping_may_alias_not_exact():
 _,r=run("uint a=m[k];to.transfer(a);m[j]=0;return a;","mapping(uint=>uint) m;","address payable to,uint k,uint j")
 assert not same(r) and any(x["pattern"]=="READ_CALL_WRITE_MAY_ALIAS" for x in read_call_write(r))
def test_terminal_branch_cannot_reach_other_branch_write():
 _,r=run("uint a=s;if(c){to.transfer(a);return a;}else{s=0;}return a;",args="address payable to,bool c")
 assert not same(r)
 orders,_=order_relations(r);assert not any(o.relation=="EXTERNAL_CALL_BEFORE_STATE_WRITE" for o in orders)
def test_call_config_is_not_invocation():
 # Parser robustness: standalone configured function value, no compilation claim.
 _,r=run("uint a=s;to.call.value(a);s=0;return a;")
 assert not same(r)
 assert any(e.kind=="CALL_CONFIGURATION" for es in r.ir.events.values() for e in es)
def test_state_read_as_call_argument_same_statement():
 _,r=run("to.transfer(s);s=0;return 0;");assert len(same(r))==1
 p=same(r)[0];events={e.id:e for es in r.ir.events.values() for e in es}
 assert events[p["read"]].anchor==events[p["call"]].anchor
def test_unknown_user_call_pattern_is_not_external():
 v,rs=analyze_source("pragma solidity 0.5.17;contract C{uint s;function g() internal{}function f() public returns(uint){uint a=s;g();s=0;return a;}}")
 r=rs[-1];assert not same(r)
 assert any(p["pattern"]=="READ_OPAQUE_CALL_UNRESOLVED" for p in read_call_write(r))
def test_no_call_normal_state_op_only_defuse_and_access():
 _,r=run("s=1;return s;")
 assert len(r.facts)==1 and not read_call_write(r)
 assert any(o.relation=="STATE_ACCESS_ORDER" for o in order_relations(r)[0])
def test_intervening_write_stops_old_read_pattern():
 _,r=run("uint a=s;s=2;to.transfer(a);s=0;return a;");assert not same(r)
def test_compound_update_read_write_order():
 _,r=run("to.transfer(s);s-=1;return 0;")
 assert len(same(r))==1
 es=[e for b in r.reachable for e in r.ir.events[b]]
 assert sum(e.detail=="READ_MODIFY_WRITE" for e in es)==2
def test_revert_stops_order():
 _,r=run("uint a=s;to.transfer(a);revert();s=0;return a;")
 assert not same(r)
def test_forged_witness_rejected():
 _,r=run("s=1;t=2;return s;");orders,_=order_relations(r);o=orders[0]
 with pytest.raises(ValueError):validate_witness(r.ir,(o.definition.id,o.use.id))
def test_project_same_statement_loss_no_nearest_node_guess():
 src=source("to.transfer(s);s=0;return 0;");g,_=fixture(src)
 v,rs=analyze_source(src,file="p.sol");ev,a=projected_file(g,v,rs);out,inv=materialize(g,ev)
 assert inv["base_preserved"] and any(e["relation"]=="EXTERNAL_CALL_BEFORE_STATE_WRITE" for e in ev)
 assert all(e["source_node"]!=e["target_node"] for e in ev)
 assert same(rs[0]) # READ and CALL share a node but ternary event order remains sidecar
 off,_=materialize(g,ev,enabled=False);assert fingerprint(off)==fingerprint(g)
def test_no_label_information_used_and_old_parallel_edges_kept():
 src=source("s=1;to.transfer(s);s=0;return s;");g,_=fixture(src);v,rs=analyze_source(src,file="p.sol")
 ev,a=projected_file(g,v,rs);out,_=materialize(g,ev)
 altered=copy.deepcopy(g)
 for n in altered:altered.nodes[n]["node_info_vulnerabilities"]=[{"category":"arbitrary","lines":[999]}]
 ev2,_=projected_file(altered,v,rs);assert ev==ev2
 out2,_=materialize(altered,ev2);assert_preserved(altered,out2)
 assert any(d["edge_type"]=="STATE_DEF_USE" for _,_,d in out.edges(data=True))
def test_missing_write_anchor_kills_without_guessing_projection():
 src=source("s=1;s=2;return s;");g,_=fixture(src)
 missing=[n for n,d in g.nodes(data=True) if d.get("code")=="s=2;"];assert len(missing)==1;g.remove_node(missing[0])
 v,rs=analyze_source(src,file="p.sol");ev,a=projected_file(g,v,rs)
 assert len(rs[0].facts)==1 and v.raw[rs[0].facts[0].definition.anchor.start:rs[0].facts[0].definition.anchor.end]==b"s=2;"
 assert a["missing_anchors"] and not any(e["relation"]=="STATE_DEF_USE" for e in ev)
