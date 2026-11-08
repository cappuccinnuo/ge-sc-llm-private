import copy
import pytest
from scripts.node_sem.llm_post_v2 import path,normalize,faithfulness,role_agreement,gates,teacher_text
from scripts.node_sem.tests.test_llm_cache_post import FACT,GOOD
from scripts.node_sem.tests.test_llm_role_review import f

@pytest.mark.parametrize("expr,root,reads",[
 ("balances[msg.sender]","balances",{"msg.sender"}),
 ("x[y[i]].field","x",{"y","i"}),
 ("a.b.c","a",set()),
 ("msg.sender","msg.sender",set()),
 ("msg.value","msg.value",set()),
 ("address(this).balance","this.balance",set()),
 ("now","block.timestamp",set()),
 ("a[0]","a",set()),
 ('a["literal"]',"a",set()),
 ("a[x.field + msg.value]","a",{"x","msg.value"}),
 ("a[f(x)]","a",{"x"}),
 ("gasleft()","gasleft",set()),
 ("block.blockhash(n)","blockhash",{"n"}),
 ("a[broken","a[broken",set()),
 ("call(x)","call(x)",set())
])
def test_paths(expr,root,reads):
 assert path(expr)==(root,reads)

def test_both_sides_and_index_reads():
 facts=copy.deepcopy(FACT)
 facts.update(node_kind="statement",self_condition={})
 facts["dfg"]["uses"]=[]
 facts["state"]["writes"]=[{"var":"balances[msg.sender]"}]
 facts["env"]["keys"]=["msg.sender"]
 stmt=dict(GOOD["statements"][0],reads=["msg.sender"],writes=["a1[msg.sender]"])
 assert faithfulness(stmt,facts,{"a1":"balances"})[0]==1
 stmt["reads"]=["msg.value"]
 assert faithfulness(stmt,facts,{"a1":"balances"})[0]<1
 assert normalize(["msg.sender"],[])[0] != normalize(["msg.value"],[])[0]

def test_boolean_primary_and_role_union_secondary():
 rows=[dict(row_key=0,role="value_transfer",predicted_external=True,flags=[]),
       dict(row_key=1,role="computation",predicted_external=True,flags=[]),
       dict(row_key=2,role="external_call",predicted_external=False,flags=[])]
 facts={i:f("statement") for i in range(3)}
 for x in facts.values():x["external"]["kinds"]=["transfer"]
 a=role_agreement(rows,facts)
 assert a["external_call"]["correct"]==2 and a["external_call"]["recall"]==pytest.approx(2/3)
 assert a["external_role"]["correct"]==2
 rows[0]["predicted_external"]=False
 assert role_agreement(rows,facts)["external_call"]["correct"]==1
 assert role_agreement(rows,facts)["external_role"]["correct"]==2

def test_own_condition_disjunction_not_surrounding_guard():
 rows=[dict(row_key=i,role="access_check",flags=[]) for i in range(3)]
 facts={0:f(),1:f("statement"),2:f(operands=("msg.sender",),pairs=())}
 facts[1]["guards"]=[dict(is_sender_guard=True,disjunctive=True)]
 # An accepted disjunction is represented by the sealed env_state eq_pair.
 a=role_agreement(rows,facts)["access_check"]
 assert a["correct"]==1 and a["claimed_verifiable"]==2 and a["claimed_unknown"]==1

def test_unknown_absence_and_local_assignment_not_state_write():
 facts=f("statement")
 facts["state"]["writes"]=[]
 row=dict(row_key=0,role="state_update",flags=[],faithfulness=None,target_kind="statement")
 a=role_agreement([row],{0:facts})
 assert a["state_update"]["precision"]==0
 facts["state"]["status"]="unknown"
 assert faithfulness(GOOD["statements"][0],facts,{})==(None,None)
 assert role_agreement([row],{0:facts})["state_update"]["precision"] is None
 assert not gates([row],[{"status":"ok"}],a)["passed"]

def test_judge_text_includes_note_without_describe_pollution():
 row=dict(present=True,target_kind="statement",role="computation",summary="Calculate",intent="Compute",security_note="Unchecked result")
 assert ". note: Unchecked result." in teacher_text(row,"judge_v2")
 assert "note:" not in teacher_text(row,"describe_v2")
