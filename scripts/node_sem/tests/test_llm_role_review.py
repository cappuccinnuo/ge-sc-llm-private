import copy
from scripts.node_sem.llm_role_review import own_sender_condition, corrected_agreement
from scripts.node_sem.tests.test_llm_cache_post import FACT


def f(kind="condition", operands=("msg.sender","state"), pairs=("env_state",)):
    out=copy.deepcopy(FACT)
    out.update(node_kind=kind,self_condition=dict(operand_classes=list(operands),eq_pairs=list(pairs)))
    return out


def test_current_require_needs_no_prior_guard():
    assert f()["guards"]==[]
    assert own_sender_condition(f()) is True


def test_protected_write_is_not_itself_an_authorization_check():
    obj=f("statement")
    obj["guards"]=[dict(is_sender_guard=True)]
    assert own_sender_condition(obj) is False


def test_opaque_sender_predicate_is_unknown_not_false():
    assert own_sender_condition(f(operands=("msg.sender",),pairs=())) is None
    assert own_sender_condition(f(operands=("state","param"),pairs=("state_param",))) is False


def test_correction_excludes_unknown_and_preserves_other_roles():
    rows=[dict(row_key=i,role="access_check",flags=[]) for i in range(3)]
    facts={0:f(),1:f("statement"),2:f(operands=("msg.sender",),pairs=())}
    result=corrected_agreement(rows,facts)
    assert result["access_check"]["claimed_verifiable"]==2
    assert result["access_check"]["precision"]==.5
    assert result["access_check"]["claimed_unknown"]==1
    assert result["state_update"]["precision"] is None
