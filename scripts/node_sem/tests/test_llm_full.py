import copy
import json
import pytest
from scripts.node_sem.llm_full import skip_no_body, failure_fraction, result_for, body_status
from scripts.node_sem.llm_protocol_v2 import cache_key
from scripts.node_sem.llm_cache_v2 import reference

PARAMS = {"seed":0}
ASSET = "a"*64


def unit():
    u=dict(contract_header="contract a1",state_vars="",function_with_lines="L1| function a2() public {}",target_lines=[])
    u["cache_key"]=cache_key(u,ASSET,PARAMS)
    return u


class Backend:
    mode="cpu"
    def __init__(self,valid=True):self.calls=0;self.valid=valid
    def generate(self,messages,schema):
        self.calls+=1
        return dict(content=json.dumps(dict(function_intent="Return a value",statements=[])) if self.valid else "{",
                    elapsed_seconds=0,usage={})


@pytest.mark.parametrize("has,targets,expected",[(False,[],True),(True,[],False),(True,[2],False),(False,[2],False)])
def test_body_gate(has,targets,expected):
    assert skip_no_body(has,targets)==expected


def test_ast_body():
    assert not body_status("function f() external;")
    assert body_status("function f() public {}")
    assert body_status("constructor() internal {}")
    assert body_status("modifier onlyOwner() { _; }")


def test_generation_cache_and_prior_readonly(tmp_path):
    u=unit();b=Backend();m=dict(asset_sha256=ASSET,parameters=PARAMS)
    e=dict(skip=False,prior_response=None)
    one=result_for(u,e,b,tmp_path,m)
    assert one["status"]=="ok" and b.calls==1
    before={str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    e["prior_response"]=one["response"]
    two=result_for(u,e,None,tmp_path,m)
    assert two["reused"] and b.calls==1
    assert before=={str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    p=tmp_path/u["cache_key"]/"response.json";p.write_text("{}")
    with pytest.raises(ValueError):result_for(u,e,None,tmp_path,m)


def test_no_body_never_calls_backend(tmp_path):
    b=Backend()
    r=result_for(unit(),dict(skip=True),b,tmp_path,dict(asset_sha256=ASSET,parameters=PARAMS))
    assert r["status"]=="skipped_no_body" and b.calls==0 and not list(tmp_path.iterdir())


def test_empty_body_with_no_targets_still_calls(tmp_path):
    b=Backend()
    result_for(unit(),dict(skip=False,prior_response=None),b,tmp_path,dict(asset_sha256=ASSET,parameters=PARAMS))
    assert b.calls==1


def test_exact_one_json_retry_and_failure_rate(tmp_path):
    b=Backend(False)
    r=result_for(unit(),dict(skip=False,prior_response=None),b,tmp_path,dict(asset_sha256=ASSET,parameters=PARAMS))
    assert b.calls==2 and r["status"]=="parse_failed"
    assert failure_fraction([r]+[dict(status="ok")]*19)==.05
    assert failure_fraction([r]+[dict(status="ok")]*18)>.05
    assert failure_fraction([dict(status="skipped_no_body")])==0
    assert failure_fraction([r,dict(status="skipped_no_body")])==1
