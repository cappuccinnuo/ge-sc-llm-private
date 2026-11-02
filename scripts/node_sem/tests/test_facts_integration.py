"""Independent exact-HCG/L1/L2 integration oracles; parser verified, no solc run."""
import copy
import hashlib

import networkx as nx
import numpy as np
import pytest

from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.l1 import augment_l1
from scripts.DFG.dfg_v2.l2 import augment_l2
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.projection import ANCHOR, decoded
from scripts.DFG.models import Unsupported
from scripts.node_sem.facts import extract_source

FILE = "integration.sol"
ROLES = {
    "contract_declaration": "contract_declaration",
    "library_declaration": "library_declaration",
    "function_definition": "function_definition",
    "constructor_definition": "constructor_definition",
    "modifier_definition": "modifier_definition",
    "fallback_receive_definition": "fallback_receive_definition",
    "state_variable_declaration": "new_variable",
    "variable_declaration_statement": "new_variable",
    "expression_statement": "expression_statement",
    "return_statement": "return",
    "if_statement": "if", "for_statement": "for", "while_statement": "while",
    "revert_statement": "revert_statement", "emit_statement": "emit_statement",
    "continue_statement": "continue_statement", "assembly_statement": "assembly_statement",
}


def graph_fixture(body, pragma="^0.5.11", source_override=None):
    source = source_override if source_override is not None else "pragma solidity " + pragma + "; contract Subject { " + body + " }"
    view = ProjectionView(source, FILE)
    graph = nx.MultiDiGraph()
    for anchor, ident in view.compat_ids.items():
        ast = view.compat_nodes[anchor]
        if ast.type not in ROLES:
            continue
        role = ROLES[ast.type]
        nid = "n" + str(ident)
        graph.add_node(nid, node_type=role, source_file=FILE,
            code=view.compat[ast.start_byte:ast.end_byte].decode("utf8"),
            label="arbitrary-prefix-{}-{}-{}-{}".format(ident,role,ast.start_point[0]+1,ast.end_point[0]+1),
            node_source_code_lines=[ast.start_point[0]+1,ast.end_point[0]+1],
            node_info_vulnerabilities=None, method="metadata", type_label=0,
            token=np.zeros(512,dtype=np.float32))
    # Deliberately misleading model edges. Semantic order must ignore them.
    identities = list(graph)
    for a,b in zip(identities[1:],identities):
        graph.add_edge(a,b,edge_type="next_line")
    one,l1=augment_l1(graph,{FILE:source})
    two,l2=augment_l2(one,{FILE:source})
    evidence={"source_hashes":{FILE:hashlib.sha256(source.encode()).hexdigest()},
        "layers":{"L1":l1,"L2":l2,"L3":{"files":{},"evidence":[],"labels_used_for_analysis":False,"source_hashes":{FILE:hashlib.sha256(source.encode()).hexdigest()}}}}
    return source,two,evidence


def run(body):
    source,graph,evidence=graph_fixture(body)
    before=graph_fingerprint(graph)
    records,audit=extract_source(source,FILE,graph=graph,evidence=evidence,references=[])
    assert graph_fingerprint(graph)==before
    return source,graph,evidence,records,audit


def row(graph,records,code):
    keys=[nid for nid,data in graph.nodes(data=True) if data["code"]==code]
    assert len(keys)==1, keys
    return records[keys[0]]


def test_state_order_oracles_both_directions_and_call_value():
    source,g,e,records,audit=run("""mapping(address=>uint) balances; address payable owner; uint reward;
        function withdraw(uint amount) public { msg.sender.call.value(amount)(""); balances[msg.sender] -= amount; }
        function deposit(uint amount) public { balances[msg.sender] = amount; owner.transfer(amount); }
        function pay() public { owner.transfer(reward); reward = msg.value; }
    """)
    write=row(g,records,"balances[msg.sender] -= amount;")
    call=row(g,records,'msg.sender.call.value(amount)("");')
    assert write["state"]["writes"]==[{"var":"balances","shape":"mapping","auth":False}]
    assert "-" in write["arith"]["ops"] and write["arith"]["on_state"]
    assert write["order"]["status"]=="supported"
    assert write["order"]["reachable_from_ext_call"]
    assert write["order"]["dominated_by_ext_call"]
    assert call["order"]["call_then_write"]
    earlier=row(g,records,"balances[msg.sender] = amount;")
    assert earlier["order"]["write_then_call"]
    assert not earlier["order"]["reachable_from_ext_call"]
    transfer=row(g,records,"owner.transfer(reward);")
    assert transfer["external"]["value_class"]=="state"
    assert transfer["order"]["call_then_write"]
    reward=row(g,records,"reward = msg.value;")
    assert "msg.value" in reward["env"]["keys"]
    assert "state" in reward["env"]["uses"]
    assert all(info["status"]=="supported" for info in audit["cfg"].values())


def test_conditional_call_reaches_join_but_does_not_dominate():
    _,g,_,records,_=run("""address payable owner; uint value;
        function f(uint p) public { if (p>0) { owner.transfer(p); } value = p; }
    """)
    record=row(g,records,"value = p;")
    assert record["order"]["status"]=="supported"
    assert record["order"]["reachable_from_ext_call"]
    assert not record["order"]["dominated_by_ext_call"]
    assert record["guard_status"]=="none"


def test_loop_external_call_uses_semantic_cfg_and_ast_loop():
    _,g,_,records,_=run("""address payable owner; uint value;
        function f(uint p) public { for (uint i=0;i<p;i++) { owner.transfer(i); value = i; } }
    """)
    call=row(g,records,"owner.transfer(i);")
    assert call["order"]["ext_call_in_loop"]
    assert call["loop"]["bound"]=="param_local"
    assert call["order"]["call_then_write"]
    assert row(g,records,"value = i;")["order"]["reachable_from_ext_call"]


def test_l1_arithmetic_result_to_guard_uses_symbol_identity():
    _,g,e,records,audit=run("""mapping(address=>uint) balances;
        function f(uint cnt,uint p) public { uint amount = cnt * p; require(p > 0 && balances[msg.sender] >= amount); }
    """)
    arithmetic=row(g,records,"uint amount = cnt * p;")
    guard=row(g,records,"require(p > 0 && balances[msg.sender] >= amount);")
    assert arithmetic["dfg"]["status"]=="supported"
    assert any(x["var"]=="amount" for x in arithmetic["dfg"]["defs"])
    assert any(x["var"]=="amount" for x in guard["dfg"]["uses"])
    assert any(x["sink"]=="guard" for x in arithmetic["dfg"]["to"])
    assert "guard" in arithmetic["arith"]["sinks"]
    assert audit["symbol_exact_lookups"]>0


def test_state_authorization_and_declaration_function_contract_summaries():
    source,g,_,records,_=run("""address owner; mapping(address=>uint) public balances;
        modifier gate() { require(msg.sender == owner); _; }
        function setOwner(address p) public { owner = p; }
        function protected(address p) public gate { owner = p; balances[p] = 1; }
        function add(address p,uint n) public { balances[p] = n; }
        function balance(address p) public view returns(uint) { return balances[p]; }
    """)
    owner=row(g,records,"address owner;")["state_decl"]
    assert owner["auth"] and owner["unguarded_writer"]
    assert owner["write_functions"]=="many"
    assert owner["unguarded_write_functions"]==1
    balance=row(g,records,"mapping(address=>uint) public balances;")["state_decl"]
    assert balance["shape"]=="mapping" and balance["public"]
    assert balance["write_functions"]=="many" and balance["read_functions"]=="one"
    protected=row(g,records,"function protected(address p) public gate { owner = p; balances[p] = 1; }")
    assert protected["fn_summary"]["sender_guard"] and protected["fn_summary"]["auth_write"]
    setter=row(g,records,"function setOwner(address p) public { owner = p; }")
    assert not setter["fn_summary"]["sender_guard"] and setter["fn_summary"]["auth_write"]
    contract=next(v for v in records.values() if v["node_kind"]=="contract")
    assert contract["contract_summary"]["auth_state"] and contract["contract_summary"]["auth_state_count"]==1


@pytest.mark.parametrize("perturbation",["labels","label_prefix"])
def test_direct_producer_ignores_targets_and_saved_label_prefix(perturbation):
    source,g,e,records,_=run("address owner; uint value; function f(uint p) public { require(msg.sender == owner); value = p; }")
    changed=copy.deepcopy(g)
    for _,attrs in changed.nodes(data=True):
        if perturbation=="labels":
            attrs.update(node_info_vulnerabilities=[{"lines":[999]}],type_label=99,method="label-string-should-not-enter-facts",node_source_code_lines=[999999])
        else:
            match=ANCHOR.search(decoded(attrs["label"]))
            attrs["label"]="replaced-all-prefixes-"+match.group(0)
    actual,_=extract_source(source,FILE,graph=changed,evidence=e,references=[])
    assert actual==records


@pytest.mark.parametrize("perturbation",["anchor","code"])
def test_direct_producer_rejects_stale_ast_anchor_or_code(perturbation):
    source,g,e,_,_=run("uint value; function f(uint p) public { uint n=p; value=n; }")
    changed=copy.deepcopy(g)
    nid=next(n for n,d in changed.nodes(data=True) if d["code"]=="uint n=p;")
    changed.nodes[nid]["label" if perturbation=="anchor" else "code"]="incorrect"
    with pytest.raises((ValueError,Unsupported)):
        extract_source(source,FILE,graph=changed,evidence=e,references=[])


@pytest.mark.parametrize("perturbation",["index","endpoint","state_identity","symbol"])
def test_sealed_evidence_mismatch_is_rejected(perturbation):
    source,g,e,_,_=run("uint value; function f(uint p) public { uint n=p; value=n; }")
    graph,evidence=copy.deepcopy(g),copy.deepcopy(e)
    if perturbation=="index":
        attrs=next(d for _,_,d in graph.edges(data=True) if d["edge_type"]=="DATA_DEF_USE")
        attrs["ddg_fact_indices"]=[999999]
    elif perturbation=="endpoint":
        proof=next(x for x in evidence["layers"]["L1"]["evidence"] if not x["self_fact"])
        proof["target"]="absent"
    elif perturbation=="state_identity":
        proof=next(x for x in evidence["layers"]["L2"]["evidence"] if x["status"]=="projected")
        proof["state"]["start"]+=1
    else:
        proof=next(x for x in evidence["layers"]["L1"]["evidence"] if not x["self_fact"])
        proof["symbol"]="absent-symbol"
    with pytest.raises(ValueError):
        extract_source(source,FILE,graph=graph,evidence=evidence,references=[])


def test_unsupported_function_cfg_does_not_publish_false_order():
    _,g,_,records,_=run("uint value; function f(uint p) public { assembly { let q := 1 } value = p; }")
    out=row(g,records,"value = p;")
    assert out["order"]["status"]=="unknown"
    assert out["dfg"]["status"]=="unknown"
    assert out["unresolved"]["semantic_cfg_unsupported"]==1


def test_shadowed_state_name_does_not_inherit_auth_or_state_access():
    _,g,_,records,_=run("address owner; modifier gate() { require(msg.sender == owner); _; } function f(address owner) public { require(msg.sender == owner); owner = msg.sender; }")
    out=row(g,records,"owner = msg.sender;")
    assert out["guards"][0]["eq_pairs"]==["env_param"]
    assert out["state"]["writes"]==[] and out["state"]["reads"]==[]
    assert out["dfg"]["status"]=="supported"
    parameter_uses=[item for record in records.values() for item in record["dfg"].get("uses",[]) if item["var"]=="owner"]
    assert parameter_uses and all(item["kind"]=="parameter" for item in parameter_uses)

@pytest.mark.parametrize("layer",[None,"L1","L2","L3"])
def test_source_hash_disagreement_in_evidence_is_rejected(layer):
    source,g,e,_,_=run("uint value; function f(uint p) public { uint n=p; value=n; }")
    evidence=copy.deepcopy(e)
    target=evidence if layer is None else evidence["layers"][layer]
    target["source_hashes"][FILE]="0"*64
    with pytest.raises(ValueError,match="[Ss]ource|[Hh]ash|SHA"):
        extract_source(source,FILE,graph=g,evidence=evidence,references=[])

def test_unknown_modifier_does_not_certify_unguarded_writer():
    _,g,_,records,_=run("address owner; modifier gate() { require(msg.sender == owner); _; } function f(address p) public absent { owner=p; }")
    writer=row(g,records,"owner=p;")
    assert writer["guard_status"]=="unknown"
    declaration=row(g,records,"address owner;")["state_decl"]
    assert declaration["status"]=="unknown"
    assert declaration["auth"]
    assert not declaration["unguarded_writer"]
    assert declaration["unguarded_write_functions"]==0

def test_missing_projection_reports_unknown_summary_without_line_guess():
    source,g,e,_,_=run("uint value; function f(uint p) public { value=p; }")
    graph=copy.deepcopy(g)
    nid=next(n for n,d in graph.nodes(data=True) if d["code"]=="value=p;")
    graph.remove_node(nid)
    records,audit=extract_source(source,FILE,graph=graph,evidence=e,references=[])
    assert nid not in records
    assert audit["projection_missing"]>=1
    assert row(graph,records,"uint value;")["state_decl"]["status"]=="unknown"
    assert row(graph,records,"function f(uint p) public { value=p; }")["fn_summary"]["status"]=="unknown"

def test_shared_base_auth_declaration_union_preserves_scoped_function_contract_facts():
    source = """pragma solidity ^0.5.11;
contract Base {
    address internal owner;
    function baseSet(address p) public { owner = p; }
}
contract Derived is Base {
    function derivedSet(address p) public { require(msg.sender == owner); owner = p; }
}
contract Unrelated {
    address public owner;
    function unrelatedSet(address p) public { owner = p; }
}
"""
    source,graph,evidence=graph_fixture("",source_override=source)
    before=graph_fingerprint(graph)
    records,_=extract_source(source,FILE,graph=graph,evidence=evidence,references=[])
    assert graph_fingerprint(graph)==before

    # Only the exact inherited declaration identity is shared. Equal spelling
    # in another contract is deliberately not an authorization relationship.
    base_decl=row(graph,records,"address internal owner;")["state_decl"]
    unrelated_decl=row(graph,records,"address public owner;")["state_decl"]
    assert base_decl["auth"] is True
    assert unrelated_decl["auth"] is False
    assert base_decl["write_functions"]=="many"
    assert unrelated_decl["write_functions"]=="one"

    base_fn=row(graph,records,"function baseSet(address p) public { owner = p; }")
    derived_fn=row(graph,records,"function derivedSet(address p) public { require(msg.sender == owner); owner = p; }")
    unrelated_fn=row(graph,records,"function unrelatedSet(address p) public { owner = p; }")
    assert base_fn["fn_summary"]["auth_write"] is False
    assert base_fn["fn_summary"]["sender_guard"] is False
    assert derived_fn["fn_summary"]["auth_write"] is True
    assert derived_fn["fn_summary"]["sender_guard"] is True
    assert unrelated_fn["fn_summary"]["auth_write"] is False
    assert unrelated_fn["fn_summary"]["sender_guard"] is False

    summaries={data["code"].split()[1]:records[nid]["contract_summary"]
               for nid,data in graph.nodes(data=True)
               if data["node_type"]=="contract_declaration"}
    assert summaries["Base"]["auth_state"] is False
    assert summaries["Base"]["auth_state_count"]==0
    assert summaries["Derived"]["auth_state"] is True
    assert summaries["Derived"]["auth_state_count"]==1
    assert summaries["Unrelated"]["auth_state"] is False
    assert summaries["Unrelated"]["auth_state_count"]==0

    # The write records themselves retain the owning contract scope.
    writes=[record["state"]["writes"] for nid,record in records.items()
            if graph.nodes[nid]["code"]=="owner = p;"]
    assert len(writes)==3
    assert [entry[0]["auth"] for entry in writes]==[False,True,False]

def test_shared_base_declaration_completeness_includes_derived_projection_gaps():
    source = """pragma solidity ^0.5.11;
contract Base { uint internal count; }
contract Derived is Base {
    function set(uint p) public { count = p; }
}
contract Unrelated {
    uint public count;
    function setOther(uint p) public { count = p + 1; }
}
"""
    source,graph,evidence=graph_fixture("",source_override=source)
    omitted=next(n for n,d in graph.nodes(data=True) if d["code"]=="count = p;")
    graph.remove_node(omitted)
    before=graph_fingerprint(graph)
    records,audit=extract_source(source,FILE,graph=graph,evidence=evidence,references=[])
    assert graph_fingerprint(graph)==before and omitted not in records
    assert audit["projection_missing"]>=1
    shared=row(graph,records,"uint internal count;")["state_decl"]
    unrelated=row(graph,records,"uint public count;")["state_decl"]
    assert shared["status"]=="unknown"
    assert shared["write_functions"]=="zero"
    assert unrelated["status"]=="supported"
    assert unrelated["write_functions"]=="one"


@pytest.mark.parametrize("mutation",["count++;","count--;","delete count;"])
def test_unprojected_update_or_delete_invalidates_call_write_order(mutation):
    body="address payable recipient; uint count; function f() public { recipient.transfer(1); "+mutation+" }"
    source,graph,evidence=graph_fixture(body)
    before_records,_=extract_source(source,FILE,graph=graph,evidence=evidence,references=[])
    before_call=row(graph,before_records,"recipient.transfer(1);")
    assert before_call["order"]["status"]=="supported"
    assert before_call["order"]["call_then_write"]
    omitted=next(n for n,d in graph.nodes(data=True) if d["code"]==mutation)
    graph.remove_node(omitted)
    before=graph_fingerprint(graph)
    records,audit=extract_source(source,FILE,graph=graph,evidence=evidence,references=[])
    assert graph_fingerprint(graph)==before and omitted not in records
    assert audit["projection_missing"]>=1
    call=row(graph,records,"recipient.transfer(1);")
    assert call["order"]["status"]=="unknown"
    assert row(graph,records,"uint count;")["state_decl"]["status"]=="unknown"


def test_unresolved_storage_alias_invalidates_order_without_graph_deletion():
    # Parser-only robustness fixture. Equal-spelling storage aliases in nested
    # scopes exceed frozen L2 binding support; an absent projected write is not
    # proof that this external call has no subsequent state write.
    body = "uint[] values; function f() public { msg.sender.call(\"\"); uint[] storage r = values; { uint[] storage r = values; } r[0] = 1; }"
    source, graph, evidence = graph_fixture(body)
    before = graph_fingerprint(graph)
    records, audit = extract_source(source, FILE, graph=graph, evidence=evidence, references=[])
    assert graph_fingerprint(graph) == before
    assert audit["projection_missing"] == 0
    assert any(record["unresolved"].get("state_alias_unresolved") for record in records.values())
    call = row(graph, records, 'msg.sender.call("");')
    assert call["order"]["status"] == "unknown"
    assert call["unresolved"]["incomplete_state_write_order"] == 1
    assignment = row(graph, records, "r[0] = 1;")
    assert assignment["state"]["status"] == "unknown"
    assert assignment["state"]["writes"] == []
    assert assignment["order"]["status"] == "unknown"
    assert assignment["unresolved"]["incomplete_state_write_order"] == 1


def test_builtin_read_binding_diagnostic_alone_keeps_complete_order_supported():
    # L2 may report require as an unresolved state-name read. It does not
    # conceal a write and must not invalidate otherwise complete write order.
    body = "uint value; function f(uint p) public { require(p > 0); msg.sender.call(\"\"); value = p; }"
    source, graph, evidence = graph_fixture(body)
    before = graph_fingerprint(graph)
    records, audit = extract_source(source, FILE, graph=graph, evidence=evidence, references=[])
    assert graph_fingerprint(graph) == before
    assert audit["projection_missing"] == 0
    require = row(graph, records, "require(p > 0);")
    assert require["unresolved"]["state_state_name_missing"] == 1
    assert not any(record["unresolved"].get("state_alias_unresolved") for record in records.values())
    call = row(graph, records, 'msg.sender.call("");')
    assert call["order"]["status"] == "supported"
    assert call["order"]["call_then_write"] is True
    assert "incomplete_state_write_order" not in call["unresolved"]
    assignment = row(graph, records, "value = p;")
    assert assignment["order"]["status"] == "supported"
    assert assignment["state"]["writes"]
