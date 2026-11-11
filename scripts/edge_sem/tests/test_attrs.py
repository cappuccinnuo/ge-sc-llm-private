"""EP4 oracles on real frozen L1/L2 facts plus synthetic endpoint counts."""
import ast
import copy
import hashlib
from collections import Counter
from pathlib import Path
import networkx as nx
import numpy as np
import pytest
from scripts.edge_sem import attrs as a
from scripts.edge_sem.attr_sources import AttributeSource
from scripts.edge_sem.build_f4 import inspect_file
from scripts.node_sem.tests.test_facts_integration import graph_fixture, FILE
from scripts.node_sem.facts import extract_source
from scripts.node_sem.tests.test_facts_names import rename
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

FIXTURE=Path(__file__).parent/"fixtures/ep4_attributes.sol"


def bundle(source=None, body=None, pragma="^0.5.11"):
    if source is None and body is None:source=FIXTURE.read_text()
    text,graph,evidence=graph_fixture(body or "",pragma=pragma,source_override=source)
    records,_=extract_source(text,FILE,graph,evidence)
    edges,audit=inspect_file(FILE,text,graph)
    context=dict(source_text={FILE:text},sources={FILE:dict(sha256=hashlib.sha256(text.encode()).hexdigest())},
                 audit=evidence,f4_audit=dict(hard_conditions_pass=True,files=[audit]))
    vectors=a.compute_attributes(context,graph,edges,records)
    return context,graph,edges,records,vectors


@pytest.fixture(scope="module")
def data():return bundle()


def pick(data,relation,src=None,dst=None):
    _,g,edges,_,vectors=data
    return [(r,vectors[r["key"]]) for r in a.edge_rows(g,edges) if r["relation"]==relation
            and (src is None or g.nodes[r["src"]]["code"].startswith(src))
            and (dst is None or g.nodes[r["dst"]]["code"].startswith(dst))]


def test_layout_applicability_single_hot_and_explanation():
    assert len(a.EDGE_FEATURE_NAMES)==len(set(a.EDGE_FEATURE_NAMES))==74
    assert 15 not in a.CORE_CANDIDATES and a.CONTEXT==tuple(range(55,68))
    v=np.zeros(74,dtype=np.uint8);v[[3,4,9,10,18]]=1
    assert a.validate_vector(v,"DATA_DEF_USE") is v
    names=a.explain_edge(v);restored=np.array([n in names for n in a.EDGE_FEATURE_NAMES],dtype=np.uint8)
    assert np.array_equal(v,restored)
    v[16]=1
    with pytest.raises(ValueError,match="single-hot"):a.validate_vector(v,"DATA_DEF_USE")
    v=np.zeros(74,dtype=np.uint8);v[73]=1
    with pytest.raises(ValueError,match="Inapplicable"):a.validate_vector(v,"GUARDS")
    with pytest.raises(ValueError):a.validate_vector(v.astype(np.float32),"CALL_SITE")
    with pytest.raises(ValueError):a.validate_vector(v,"REV_GUARDS")


def test_known_data_multievidence_types_and_kinds(data):
    rows=pick(data,"DATA_DEF_USE",dst="(bool ok, ) = a.call(d);")
    assert rows
    assert any(v[9] and v[12] for _,v in rows) # address + bytes
    assert all(v[4] and v[18] for _,v in rows)


def test_external_call_path_decrease_and_value_call(data):
    rows=pick(data,"DATA_DEF_USE",src="uint x = p + 1;",dst="balances[msg.sender] -= x;")
    assert rows and all(v[21] for _,v in rows)
    rows=pick(data,"WRITES_STATE",src="balances[msg.sender] -= x;")
    assert rows and all(v[31] and v[36] for _,v in rows)
    rows=pick(data,"DATA_DEF_USE",dst='owner.call.value(x)("")')
    assert rows and all(v[23] and v[37] and v[39] for _,v in rows)


def test_loop_carried_increment_to_condition(data):
    rows=pick(data,"DATA_DEF_USE",src="i++;",dst="while (i < n)")
    assert rows and all(v[19] and v[20] for _,v in rows)


def test_multiplication_and_pre08_context(data):
    rows=pick(data,"DATA_DEF_USE",dst="uint c = ax * bx;")
    assert rows and all(v[24] and v[28] and v[61] for _,v in rows)
    rows=pick(data,"DATA_DEF_USE",dst="(bool success, ) = receiver.call(payload);")
    assert rows and all(v[23] and v[37] and not v[40] for _,v in rows)


def test_checked_send_bit(data):
    rows=pick(data,"DATA_DEF_USE",dst="if (!target.send(amount))")
    assert rows and all(v[23] and v[37] and v[40] for _,v in rows)


def test_guard_mapping_and_modifier_groups(data):
    _,g,_,_,_=data
    rows=pick(data,"GUARDS",src="require(msg.sender == owner);")
    assert rows and all(v[49] for _,v in rows)
    mods=pick(data,"MOD_APPLY",src="function dual(")
    assert len(mods)==2
    for r,v in mods:
        if "modifier gate()" in g.nodes[r["dst"]]["code"]:
            assert v[47] and v[49] and not v[50]
        else:assert v[47] and v[50] and not v[49]
    locked=pick(data,"MOD_APPLY",src="function lockedCall(")
    assert len(locked)==1 and not locked[0][1][43:55].any() and not locked[0][1][72]
    # Modifiers still carry attributes when the function has no body/GUARDS.
    empty=pick(data,"MOD_APPLY",src="function noBody(")
    assert len(empty)==2 and all(v[47] for _,v in empty)


def test_arithmetic_guard_operands_exact_frozen_union(data):
    rows=pick(data,"GUARDS",src="require(a + b >= a);")
    assert rows
    for r,v in rows:
        want={a.GUARD_OPERANDS[c] for e in r["data"]["evidence"] for c in e["operand_classes"] if c in a.GUARD_OPERANDS}
        assert set(np.flatnonzero(v[49:55])+49)==want and not v[49]


def test_callee_state_write_and_library(data):
    rows=pick(data,"CALL_SITE",dst="function helper(")
    assert rows and all(v[41] and not v[73] for _,v in rows)
    rows=pick(data,"CALL_SITE",dst="function twice(")
    assert rows and all(v[73] for _,v in rows)


def test_unknown_status_and_guard_targets(data):
    context,g,edges,facts,_=data
    rows=pick(data,"DATA_DEF_USE",dst="uint c = ax * bx;")
    target=rows[0][0]["dst"]
    facts=copy.deepcopy(facts);facts[target]["dfg"]["status"]="unknown"
    context=copy.deepcopy(context)
    t=next(t for t in context["f4_audit"]["files"][0]["guards"]["targets"] if t["node"]==target)
    t["guard_status"]="unknown"
    vectors=a.compute_attributes(context,g,edges,facts)
    for r,_ in rows:
        v=vectors[r["key"]]
        assert v[69] and v[72] and not v[3:20].any() and not v[22:30].any()


def endpoint_fixture(mode):
    g=nx.MultiDiGraph()
    for i in range(75):
        g.add_node("s"+str(i),source_file="f.sol",node_type="expression_statement")
        g.add_node("t"+str(i),source_file="f.sol",node_type="expression_statement")
    for i in range(75):
        for j in (i,(i+1)%75):g.add_edge("s"+str(i),"t"+str(j),edge_type="next_line")
    rows=a.edge_rows(g,[]);attrs={}
    for r in rows:
        v=np.zeros(74,dtype=np.uint8)
        s=int(r["src"][1:]);t=int(r["dst"][1:])
        if mode=="endpoint":v[0]=t<40
        elif mode=="mixed":v[0]=s==t
        elif mode=="sparse":v[0]=s==t and s<31
        else:v[0]=s==t and s<3
        attrs[r["key"]]=v
    return a.endpoint_test(attrs,[],g)


@pytest.mark.parametrize("mode,expected",[("endpoint","endpoint"),("mixed","core"),("sparse","core"),("few","undetermined")])
def test_endpoint_rules(mode,expected):
    result=endpoint_fixture(mode)[0]
    assert result["verdict"]==expected
    if mode=="sparse":assert result["source"]==[31,0,0.0]


def test_task_common_selection_and_unknowns():
    x=endpoint_fixture("mixed");y=copy.deepcopy(x)
    y[0].update(verdict="endpoint")
    y[68]["positives"]=1
    out=a.select_groups({"a":x,"b":y})
    assert 0 in out["context_indices"] and 0 not in out["core_indices"]
    assert 68 in out["context_indices"] and 15 not in out["core_indices"]
    assert 73 in out["all_zero_candidates"]


def test_no_unrelated_outgoing_sink_is_borrowed(data):
    rows=pick(data,"WRITES_STATE")
    assert rows and all(not v[22:30].any() and not v[37:41].any() for _,v in rows)


def test_fast_name_invariance_and_original_graph_unchanged(data):
    context,g,edges,facts,old=data
    before=graph_fingerprint(g)
    changed,_=rename(context["source_text"][FILE])
    _,h,new_edges,_,new=bundle(source=changed)
    left=a.edge_rows(g,edges);right=a.edge_rows(h,new_edges)
    assert [(r["src"],r["dst"],r["relation"],r["k"]) for r in left]==[(r["src"],r["dst"],r["relation"],r["k"]) for r in right]
    assert all(np.array_equal(old[x["key"]],new[y["key"]]) for x,y in zip(left,right))
    assert graph_fingerprint(g)==before


def test_labels_and_predictions_cannot_change_attributes(data):
    context,g,edges,facts,vectors=data
    changed=copy.deepcopy(g)
    for _,node in changed.nodes(data=True):
        node.update(type_label=17,node_info_vulnerabilities=[{"lines":[42]}],method="anything",prediction=1)
    after=a.compute_attributes(context,changed,edges,facts)
    assert all(np.array_equal(vectors[k],after[k]) for k in vectors)


def test_code_text_access_is_only_reserved_environment_key():
    source=Path(a.__file__).read_text()
    # One AST-indexed graph code access; all ordinary syntax comes via source AST.
    tree=ast.parse(source)
    accesses=[n for n in ast.walk(tree) if isinstance(n,ast.Subscript)
              and ((isinstance(n.slice,ast.Index) and isinstance(n.slice.value,ast.Str) and n.slice.value.s=="code")
                   or isinstance(n.slice,ast.Str) and n.slice.s=="code")]
    assert len(accesses)==1

def test_parameter_entry_sink_is_frozen_and_explicit():
    data=bundle(body="function f(uint a,uint b) public { uint c=a*b; }")
    context,g,edges,facts,_=data
    vectors,diag=a._compute_attributes(context,g,edges,facts)
    rows=pick(data,"DATA_DEF_USE",dst="uint c=a*b;")
    assert rows and all(v[24] and v[28] for _,v in rows)
    keys={r["key"] for r,_ in rows}
    assert keys <= {r["edge_key"] for r in diag["sinks"] if r["source"]=="frozen_sink_sealed_symbol" and r["parameter_entry"]}

def test_control_branch_and_dominance():
    data=bundle(body="address payable owner; uint value; function f(uint p) public { uint x=p; if (p>0) { owner.transfer(p); } else { value=x; } value=p; }")
    context,g,edges,facts,_=data
    def nid(text):return next(n for n,d in g.nodes(data=True) if d["code"].startswith(text))
    branch,yes,no=nid("if (p>0)"),nid("owner.transfer(p);"),nid("value=x;")
    before=nid("uint x=p;")
    g.add_edge(branch,yes,edge_type="pos_next")
    g.add_edge(branch,no,edge_type="neg_next")
    g.add_edge(before,branch,edge_type="next_line")
    vectors=a.compute_attributes(context,g,edges,facts)
    rows=a.edge_rows(g,edges)
    pos=next(vectors[r["key"]] for r in rows if r["src"]==branch and r["dst"]==yes and r["relation"]=="pos_next")
    neg=next(vectors[r["key"]] for r in rows if r["src"]==branch and r["dst"]==no and r["relation"]=="neg_next")
    straight=next(vectors[r["key"]] for r in rows if r["src"]==before and r["dst"]==branch and r["relation"]=="next_line")
    assert pos[0] and pos[2] and not pos[1]
    assert neg[0] and not neg[2] and not neg[1]
    assert straight[0] and straight[1] and not straight[68]


def test_unknown_summary_fields_are_not_confirmed_false(data):
    context,g,edges,facts,_=data
    r,_=pick(data,"CALL_SITE",dst="function helper(")[0]
    changed=copy.deepcopy(facts);summary=changed[r["dst"]]["fn_summary"]
    summary.update(state_write=True,status="unknown",unknown_fields=["state_write"])
    vectors,diag=a._compute_attributes(context,g,edges,changed)
    assert not vectors[r["key"]][41]
    reason=next(x for x in diag["edges"] if x["edge_key"]==r["key"])
    assert "41" in reason["unknown_fields"]


def test_multigraph_ordinal_uses_sorted_nx_keys():
    g=nx.MultiDiGraph()
    for n in (1,2):g.add_node(n,source_file="f.sol")
    g.add_edge(1,2,key=9,edge_type="next_line")
    g.add_edge(1,2,key=3,edge_type="next_line")
    g.add_edge(1,2,key=0,edge_type="pos_next")
    rows=a.edge_rows(g,[])
    assert [(r["relation"],r["nx_key"],r["k"]) for r in rows]==[
        ("next_line",3,0),("next_line",9,1),("pos_next",0,0)]


def test_bad_f4_guard_anchor_and_source_sha_rejected(data):
    context,g,edges,facts,_=data
    bad=copy.deepcopy(context)
    bad["f4_audit"]["files"][0]["guards"]["targets"][0]["anchor"][0]+=1
    with pytest.raises(ValueError,match="Guard target"):a.compute_attributes(bad,g,edges,facts)
    bad=copy.deepcopy(context);bad["sources"][FILE]["sha256"]="0"*64
    with pytest.raises(ValueError,match="source identity"):a.compute_attributes(bad,g,edges,facts)


def test_environment_reserved_keys_and_structure_all_zero(data):
    from scripts.node_sem.facts_schema import new_facts
    from scripts.node_sem.carrier import row_key
    context,g,edges,facts,_=data
    g=copy.deepcopy(g);facts=copy.deepcopy(facts)
    target=next(n for n,d in g.nodes(data=True) if d["code"]=="value = c;")
    mappings={"msg.sender":64,"tx.origin":64,"msg.value":65,"block.number":66,
              "block.timestamp":66,"blockhash":67,"gasleft":None}
    for index,(env,bit) in enumerate(mappings.items()):
        node="env"+str(index)
        g.add_node(node,source_file=FILE,node_type="env_source",code=env)
        g.add_edge(node,target,edge_type="ENV_FLOW")
        fact=new_facts("env");fact["env"]["keys"]=[env]
        facts[row_key(node,g.nodes[node])]=fact
    fn=next(n for n,d in g.nodes(data=True) if d["node_type"]=="function_definition")
    g.add_edge(fn,target,edge_type="recursive_method_call")
    vectors=a.compute_attributes(context,g,edges,facts)
    rows=a.edge_rows(g,edges)
    for index,(env,bit) in enumerate(mappings.items()):
        v=next(vectors[r["key"]] for r in rows if r["src"]=="env"+str(index))
        assert set(np.flatnonzero(v[64:68])+64)==(set() if bit is None else {bit})
    assert all(not vectors[r["key"]].any() for r in rows if r["relation"]=="recursive_method_call")


def test_zero_candidates_retained_without_disabling_future_support():
    x=endpoint_fixture("mixed")
    out=a.select_groups({"a":x,"b":copy.deepcopy(x)})
    assert all(u in out["core_indices"] for u in range(68,73))
    assert all(out["decisions"][u]=="no_local_support" for u in out["all_zero_candidates"])
    assert 15 not in out["core_indices"] and 15 not in out["context_indices"]
    assert out["per_task_verdicts"]["a"][0]==x[0]["verdict"]


def test_raw_for_update_uses_exact_sealed_symbol_when_dfg_inapplicable():
    source="pragma solidity ^0.5.11; contract C { function f(uint n) public pure returns(uint) { uint x = 0; for (uint i = 0; i < n; i++) { x += i; } return x; } }"
    # The generic frozen fixture omits raw update-expression graph nodes.
    # Add that original-HCG node role in this local fixture before L1 projection.
    from scripts.DFG.dfg_v2.projection_view import ProjectionView
    from scripts.DFG.dfg_v2.l1 import augment_l1
    from scripts.DFG.dfg_v2.l2 import augment_l2
    from scripts.node_sem.tests.test_facts_integration import ROLES
    view=ProjectionView(source,FILE);graph=nx.MultiDiGraph()
    for anchor,ident in view.compat_ids.items():
        node=view.compat_nodes[anchor]
        role="expression_statement" if node.type in ("update_expression","unary_expression") else ROLES.get(node.type)
        if role is None:continue
        graph.add_node("n"+str(ident),node_type=role,source_file=FILE,
            code=view.compat[node.start_byte:node.end_byte].decode("utf8"),
            label="fixture-{}-{}-{}-{}".format(ident,role,node.start_point[0]+1,node.end_point[0]+1),
            node_source_code_lines=[node.start_point[0]+1,node.end_point[0]+1],
            node_info_vulnerabilities=None,type_label=0,method="fixture",token=np.zeros(512,dtype=np.float32))
    one,l1=augment_l1(graph,{FILE:source});graph,l2=augment_l2(one,{FILE:source})
    sha=hashlib.sha256(source.encode()).hexdigest()
    evidence=dict(source_hashes={FILE:sha},layers=dict(L1=l1,L2=l2,
        L3=dict(files={},evidence=[],labels_used_for_analysis=False,source_hashes={FILE:sha})))
    facts,_=extract_source(source,FILE,graph,evidence)
    edges,audit=inspect_file(FILE,source,graph)
    context=dict(source_text={FILE:source},sources={FILE:dict(sha256=sha)},
                 audit=evidence,f4_audit=dict(hard_conditions_pass=True,files=[audit]))
    vectors=a.compute_attributes(context,graph,edges,facts)
    data=(context,graph,edges,facts,vectors)
    rows=pick(data,"DATA_DEF_USE",dst="i++")
    assert rows and all(not facts[r["dst"]]["dfg"] for r,_ in rows)
    assert all(v[3] for _,v in rows)
    result,diagnostics=a._compute_attributes(context,graph,edges,facts)
    keyed={r["edge_key"]:r for r in diagnostics["edges"]}
    assert all("target_dfg_inapplicable_var_kind_from_sealed_symbol" in keyed[r["key"]]["source_gaps"] for r,_ in rows)
    assert all(np.array_equal(vectors[k],result[k]) for k in vectors)


def test_nonempty_dfg_mismatch_remains_rejected(data):
    context,graph,edges,facts,_=data
    changed=copy.deepcopy(facts)
    target=pick(data,"DATA_DEF_USE",dst="uint c = ax * bx;")[0][0]["dst"]
    assert changed[target]["dfg"]["uses"]
    changed[target]["dfg"]["uses"]=[]
    with pytest.raises(ValueError,match="Frozen dfg uses disagree"):
        a.compute_attributes(context,graph,edges,changed)


@pytest.mark.parametrize("body,src,dst,expected", [
    ("function f(uint a,uint n) public { uint x; uint y; uint i=0; while(i<n) { x=a; y=x; i++; } }", "x=a;", "y=x;", 0),
    ("function f(uint n) public returns(uint) { uint s=0; uint i=0; while(i<n) { i++; } return s; }", "uint s=0;", "return s;", 0),
    ("function f(uint x,uint n) public returns(uint) { uint s=0; uint i=0; while(i<n) { s+=x; i++; } return s; }", "s+=x;", "return s;", 0),
    ("function f(uint n) public { uint x=0; uint y; uint i=0; while(i<n) { y=x; x=y+1; i++; } }", "x=y+1;", "y=x;", 1),
])
def test_r12_loop_carried_oracles(body,src,dst,expected):
    data=bundle(body=body)
    rows=pick(data,"DATA_DEF_USE",src=src,dst=dst)
    assert rows and all(int(v[20])==expected for _,v in rows)


def test_carried_multiblock_forward_veto_and_self_exception():
    from scripts.edge_sem.attr_sources import carried
    graph=nx.DiGraph([(0,1),(1,2),(2,3),(3,1),(1,4),(3,4)])
    def result(mapping):
        return dict(graph=graph,back=[(3,1)],blocks=mapping)
    assert carried(result({"d":{3},"u":{2}}),"d","u")
    assert not carried(result({"d":{2,3},"u":{2}}),"d","u")
    assert not carried(result({"d":{3},"u":{2,4}}),"d","u")
    assert not carried(result({"d":{2},"u":{2}}),"d","u")
    assert carried(result({"d":{2}}),"d","d")
    assert not carried(result({"d":{0}}),"d","d")


@pytest.mark.parametrize("rel",["READS_STATE","WRITES_STATE","ENV_FLOW"])
def test_sink_features_inapplicable_to_other_data_edges(rel):
    assert not (set(range(22,30))|set(range(37,41))) & a.allowed_indices(rel)

def test_parameter_value_call_and_require_sink():
    data=bundle(body="function w(uint amount) public { msg.sender.call.value(amount)(); require(amount > 0); }")
    calls=pick(data,"DATA_DEF_USE",dst="msg.sender.call.value(amount)();")
    guards=pick(data,"DATA_DEF_USE",dst="require(amount > 0);")
    assert calls and all(v[23] and v[37] and v[39] for _,v in calls)
    assert guards and all(v[22] for _,v in guards)


def test_recorded_sink_gate_rejects_tampering(data):
    ctx,g,edges,facts,_=data
    row,_=pick(data,"DATA_DEF_USE",src="uint x = p + 1;",dst="balances[msg.sender] -= x;")[0]
    changed=copy.deepcopy(facts)
    entries=[r for r in changed[row["src"]]["dfg"]["to"] if r["node"]==row["dst"]]
    assert entries
    a.compute_attributes(ctx,g,edges,changed)
    entries[0]["sink"]="deliberately_invalid"
    with pytest.raises(ValueError,match="Recorded/frozen sink mismatch"):
        a.compute_attributes(ctx,g,edges,changed)
