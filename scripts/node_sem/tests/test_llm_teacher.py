import pytest
from scripts.node_sem.llm_teacher import present_row,teacher_text


def row(score=.75,**kwargs):
    r=dict(row_key=1,target_kind="statement",present=score is not None and score>=.5,
        faithfulness=score,flags=[],summary="Read the stored value",intent="Return the value",role="state_read")
    r.update(kwargs);return r


@pytest.mark.parametrize("score,present,unverified",[(1,True,False),(.5,True,False),(.49,False,False),(None,True,True)])
def test_presence(score,present,unverified):
    old=row(score);new=present_row(old)
    assert new["present"] is present and new["unverified"] is unverified
    assert old["present"] is (score is not None and score>=.5)


@pytest.mark.parametrize("flag",["summary_blacklist","intent_blacklist","parse_failed","missing","skipped_no_body"])
def test_bad_descriptions_absent(flag):
    r=present_row(row(None,flags=[flag]))
    assert not r["present"] and teacher_text(r)==""


def test_teacher_no_role_and_intent_only():
    r=present_row(row())
    a=teacher_text(r);r["role"]="external_call"
    assert teacher_text(r)==a=="Read the stored value. function: Return the value"
    assert teacher_text(present_row(row(target_kind="function")))== "function: Return the value"
    assert not present_row(row(target_kind="function",intent=""))["present"]
    assert not present_row(row(target_kind="excluded"))["present"]
