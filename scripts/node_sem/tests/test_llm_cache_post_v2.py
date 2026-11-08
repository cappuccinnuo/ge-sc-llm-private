import copy
import json
import pytest
from scripts.node_sem.llm_cache_v2 import generate_cached
from scripts.node_sem.llm_protocol_v2 import cache_key
from scripts.node_sem.llm_post_v2 import align, clean_response, faithfulness, gates, role_agreement, teacher_text

PARAMS = {"seed":0}
UNIT = dict(contract_header="contract a3",state_vars="uint a1;", function_with_lines="L1| a1 = a2;", target_lines=[1])
UNIT["cache_key"] = cache_key(UNIT, "asset", PARAMS)
GOOD = dict(function_intent="Update the stored value", statements=[
    dict(line=1,role="state_update",summary="Store the supplied value",reads=["a2"],writes=["a1"],external=False)])
FACT = dict(node_kind="statement",self_condition={},dfg={"status":"supported","defs":[],"uses":[{"var":"inputValue"}]},
    state={"status":"supported","reads":[],"writes":[{"var":"stored"}]},env={"keys":[]},
    external={"kinds":[]}, guard_status="none", guards=[])
ROW = dict(row_key=1,file="example.sol",node_type="expression_statement",source_sha256="s",code_sha256="c",
    target_kind="statement",relative_line=1,prompt_map={"a1":"stored","a2":"inputValue"},cache_key=UNIT["cache_key"])


class FakeBackend:
    mode = "fake"
    def __init__(self, replies):
        self.replies, self.calls = iter(replies), []
    def generate(self, prompt, schema):
        self.calls.append((prompt,schema))
        value=next(self.replies)
        if isinstance(value,Exception): raise value
        return dict(content=value,usage={"prompt_tokens":10,"completion_tokens":20})


def test_one_json_retry_and_sealed_cache(tmp_path):
    backend=FakeBackend(["bad",json.dumps(GOOD)])
    result=generate_cached(UNIT,backend,tmp_path,"asset",PARAMS)
    assert result["status"]=="ok" and len(backend.calls)==2
    assert backend.calls[1][0][-1]["content"].endswith("Return valid JSON only.")
    again=generate_cached(UNIT,backend,tmp_path,"asset",PARAMS)
    assert again["cache_hit"] and len(backend.calls)==2
    p=tmp_path/UNIT["cache_key"]/"response.json"
    p.write_text(p.read_text()+" ")
    with pytest.raises(ValueError,match="SHA"):
        generate_cached(UNIT,backend,tmp_path,"asset",PARAMS)


def test_no_third_retry_or_automatic_execution_error_retry(tmp_path):
    b=FakeBackend(["bad","bad",json.dumps(GOOD)])
    result=generate_cached(UNIT,b,tmp_path/"parse","asset",PARAMS)
    assert result["status"]=="parse_failed" and len(b.calls)==2
    crash=FakeBackend([RuntimeError("OOM")])
    with pytest.raises(RuntimeError):
        generate_cached(UNIT,crash,tmp_path/"crash","asset",PARAMS)
    assert (tmp_path/"crash"/UNIT["cache_key"]/"failure.json").exists()
    with pytest.raises(FileExistsError):
        generate_cached(UNIT,crash,tmp_path/"crash","asset",PARAMS)
    assert len(crash.calls)==1


def test_lines_roles_and_blacklist():
    obj=copy.deepcopy(GOOD)
    obj["function_intent"]="This is safe"
    obj["statements"] += [dict(obj["statements"][0],summary="duplicate"),
                         dict(obj["statements"][0],line=99)]
    obj["statements"][0].update(role="unexpected",summary="Unsafe transfer")
    fn, selected, stats=clean_response(obj,{1},"describe_v2")
    assert fn["intent"]=="" and selected[1]["summary"]==""
    assert selected[1]["role"]=="other" and stats["duplicate_line"]==1 and stats["invalid_line"]==1
    fn, selected, stats=clean_response(obj,{1},"judge_v2")
    assert fn["intent"]=="This is safe" and selected[1]["summary"]=="Unsafe transfer"


def test_faithfulness_complete_partial_opposite_and_unknown():
    statement=GOOD["statements"][0]
    assert faithfulness(statement,FACT,ROW["prompt_map"])[0]==1
    other=dict(statement,reads=["a1"])
    assert faithfulness(other,FACT,ROW["prompt_map"])[0]==pytest.approx(2/3)
    assert faithfulness(dict(other,writes=["a2"],external=True),FACT,ROW["prompt_map"])[0]==0
    unknown=copy.deepcopy(FACT);unknown["state"]["status"]="unknown"
    assert faithfulness(statement,unknown,ROW["prompt_map"])[0] is None


def test_member_root_is_allowed_but_no_substring_match():
    from scripts.node_sem.llm_post_v2 import jaccard
    assert jaccard(["msg.sender"], ["msg.value"]) == 0
    f=copy.deepcopy(FACT);f["dfg"]["uses"]=[{"var":"stored.member"}]
    assert faithfulness(dict(GOOD["statements"][0],reads=["a1"]),f,ROW["prompt_map"])[0]==1
    assert faithfulness(dict(GOOD["statements"][0],reads=["unrelated_stored"]),f,ROW["prompt_map"])[0]<1


def test_alignment_zero_presence_and_no_unknown_inflation():
    result={"parsed":GOOD,"status":"ok"}
    output,_=align([ROW],{1:FACT},UNIT,result)
    assert output[0]["present"] and teacher_text(output[0]).startswith("role: state_update")
    f=copy.deepcopy(FACT);f["dfg"]["status"]="unknown"
    unknown,_=align([ROW],{1:f},UNIT,result)
    assert not unknown[0]["present"] and teacher_text(unknown[0])==""
    agreement=role_agreement(output,{1:FACT})
    assert agreement["state_update"]["precision"]==1
    assert agreement["external_call"]["precision"] is None
    g=gates(output+unknown,[result],agreement)
    assert g["faithfulness_ge_half_fraction"]==.5 and not g["passed"]
