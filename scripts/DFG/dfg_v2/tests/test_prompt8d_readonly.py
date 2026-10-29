import copy
from types import SimpleNamespace
import networkx as nx
import pydot
import pytest
from scripts.DFG.dfg_v2.diagnostics8d import stratification as a
from scripts.DFG.dfg_v2.diagnostics8d import line_provenance as d
from scripts.DFG.dfg_v2.diagnostics8d import keyword_baselines as e
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.frontend import walk

@pytest.mark.parametrize("own,function,expected",[
    (True,True,a.STRATA[0]),(True,False,a.STRATA[0]),
    (False,True,a.STRATA[1]),(False,False,a.STRATA[2])])
def test_strata_disjoint_precedence(own,function,expected):
    assert a.classify(own,function)==expected

def test_synthetic_exact_identity_not_nearest_line():
    source="pragma solidity ^0.5.0;\ncontract C { function bad_re_ent() public {\nif(true) { require(true); }\n}}"
    view=ProjectionView(source,"test.sol")
    node=next(n for n in walk(view.compat_tree.root_node) if n.type=="if_statement")
    code=view.compat[node.start_byte:node.end_byte].decode()
    attrs={"node_type":"end_if","label":'"%d_ end_if"'%node.start_point[0],
           "code":pydot.quote_if_necessary(code)}
    owner,reason=a.synthetic_owner(attrs,view)
    assert owner==node
    assert a.enclosing_function(owner).child_by_field_name("name").text==b"bad_re_ent"
    bad=dict(attrs,label='"%d_ end_if"'%(node.start_point[0]+1))
    assert a.synthetic_owner(bad,view)[0] is None
    bad=dict(attrs,code='"if(false) { require(true); }"')
    assert a.synthetic_owner(bad,view)[0] is None

def test_stratum_group_counts_flips_quantiles():
    rows=[dict(target=1,original_best=1,renamed_best=0,original_probability=.9,renamed_probability=.2),
          dict(target=0,original_best=0,renamed_best=1,original_probability=.1,renamed_probability=.8)]
    result=a.group_metrics(rows)
    assert result["positive"]==result["negative"]==1
    assert result["classification_flips"]==2
    assert result["original"]["buggy_f1"]==100
    assert result["renamed"]["buggy_f1"]==0
    assert result["probability_delta_quantiles"]["p50"]==pytest.approx(0)
    assert result["positive_target_probability_delta_quantiles"]["p50"]==pytest.approx(-.7)
    assert a.group_metrics([])["probability_delta_quantiles"] is None

def test_jaccard_empty_and_ties_are_explicit():
    assert d.jaccard([],[])==1
    assert d.jaccard([1,2],[2,3])==pytest.approx(1/3)
    ranked=d.ranking({1,2},{"buggy_24.sol":{1,2},"buggy_2.sol":{1,2},"buggy_18.sol":{3}})
    assert [r["file"] for r in ranked["best"]]==["buggy_2.sol","buggy_24.sol"]
    assert ranked["buggy_24"]["jaccard"]==1

def test_positive_line_set_does_not_expand_spans():
    graph=nx.MultiDiGraph()
    graph.add_node(1,source_file="buggy_18.sol",node_info_vulnerabilities=[{"lines":[1,2,900]}],
                   node_source_code_lines=[[1,10]])
    graph.add_node(2,source_file="buggy_18.sol",node_info_vulnerabilities=None,
                   node_source_code_lines=[[30,40]])
    attached,positive=d.graph_line_sets(graph)
    assert attached["buggy_18.sol"]=={1,2,900}
    assert positive["buggy_18.sol"]=={1,10}

def test_controls_five_total_deterministic_no_focus():
    audit={"tasks":{task:{"files":[dict(file="buggy_%d.sol"%n,solidifi=True,
                                         truncation={"truncated":n==18})
                                    for n in (18,11,2,24,3)]}
                    for task in ("reentrancy_node","access_control_node")}}
    chosen=d.select_controls(audit)
    assert chosen==[("access_control_node","buggy_2.sol"),("reentrancy_node","buggy_2.sol"),
                    ("access_control_node","buggy_3.sol"),("reentrancy_node","buggy_3.sol"),
                    ("access_control_node","buggy_11.sol")]

@pytest.mark.parametrize("category,code,function,expected",[
    ("access_control",'"require(tx.origin == owner);"',None,1),
    ("access_control",'"require(tx . origin == owner);"',None,1),
    ("access_control",'"require(msg.sender == owner);"',"function f(){ require(tx.origin==owner); }",1),
    ("access_control",'"string x=\\\"tx.origin\\\";"',None,0),
    ("access_control",'"// tx.origin\\nrequire(true);"',None,0),
    ("access_control",'"txorigin_id = 1;"',None,0),
    ("reentrancy",'"addr.call.value(amount)(\\\"\\\");"',None,1),
    ("reentrancy",'"addr . send (amount);"',None,1),
    ("reentrancy",'"addr.transfer(amount);"',None,1),
    ("reentrancy",'"string x=\\\".send(\\\";"',None,0),
    ("reentrancy",'"require(ok);"',"function f(){addr.transfer(1);}",1),
    ("reentrancy",'"addr.delegatecall(data);"',None,0)])
def test_keyword_views_no_strings_comments(category,code,function,expected):
    assert e.keyword_prediction(category,code,function)["node_or_function"]==expected

def test_keyword_c2_masks_without_label_flips():
    rows=[dict(file="buggy_2.sol",original_graph_node_id=1,solidifi=True,
               prediction=dict(node_text=1,function_text=1,node_or_function=1)),
          dict(file="other.sol",original_graph_node_id=2,solidifi=False,
               prediction=dict(node_text=0,function_text=0,node_or_function=0))]
    views={("buggy_2.sol",1):dict(orig=0,C1=1,C2=1,C2_include=False),
           ("other.sol",2):dict(orig=0,C1=0,C2=0,C2_include=True)}
    result=e.summarize(rows,views)
    assert len(result)==18
    c1=next(r for r in result if r["view"]=="C1" and r["stratum"]=="SolidiFI")
    c2=next(r for r in result if r["view"]=="C2" and r["stratum"]=="SolidiFI")
    assert c1["tp"]==1 and c2["n"]==0


def test_synthetic_else_if_uses_original_root_start_and_exact_child_code():
    source="pragma solidity ^0.5.0;\ncontract C{function f() public {\nif(true){}\nelse if(false){require(true);}\n}}"
    view=ProjectionView(source,"t.sol")
    nodes=[n for n in walk(view.compat_tree.root_node) if n.type=="if_statement"]
    root,child=nodes
    attrs={"node_type":"end_if","label":'"%d_ end_if"'%root.start_point[0],
           "code":pydot.quote_if_necessary(view.compat[child.start_byte:child.end_byte].decode())}
    assert a.synthetic_owner(attrs,view)[0]==child
    assert a.enclosing_function(child)==a.enclosing_function(root)

def test_scope_inventory_uses_ast_identity_for_identical_text_not_string_markers(tmp_path):
    from scripts.DFG.dfg_v2.diagnostics8c import scoring
    source = """pragma solidity ^0.5.0;
contract C {
 function bad_re_ent() public { require(true); }
 function safe() public { require(true); string memory s = "txorigin"; }
}"""
    path=tmp_path/"buggy_2.sol";path.write_text(source)
    view=ProjectionView(source,"buggy_2.sol")
    graph=nx.MultiDiGraph()
    allowed={"function_definition":"function_definition",
             "expression_statement":"expression_statement",
             "variable_declaration_statement":"new_variable"}
    selected=[]
    for key,node in view.compat_nodes.items():
        if node.type in allowed:
            graph_id=len(selected);selected.append(node)
            kind=allowed[node.type]
            code=view.compat[node.start_byte:node.end_byte].decode()
            label="%d-%s-%d-%d"%(view.compat_ids[key],kind,node.start_point[0]+1,node.end_point[0]+1)
            graph.add_node(graph_id,source_file="buggy_2.sol",node_type=kind,code=pydot.quote_if_necessary(code),
                           label=pydot.quote_if_necessary(label))
    rows=a.scope_inventory(graph,{"buggy_2.sol":scoring.ref(path)})
    require_rows=[row for row in rows if a.code_equal(
        graph.nodes[row["original_graph_node_id"]]["code"],"require(true);")]
    # The two same-code require statements must remain distinct identities.
    assert len(require_rows)==2
    assert {row["stratum"] for row in require_rows}=={a.STRATA[1],a.STRATA[2]}
    functions=[row for row in rows if row["node_type"]=="function_definition"]
    bad=next(row for row in functions if row["function_name"]=="bad_re_ent")
    safe=next(row for row in functions if row["function_name"]=="safe")
    assert bad["own_text_renamed"] and bad["stratum"]==a.STRATA[0]
    assert not safe["own_text_renamed"]
    assert all(row["scope_verified"] for row in rows)
