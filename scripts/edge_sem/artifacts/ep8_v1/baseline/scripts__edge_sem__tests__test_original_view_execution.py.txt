"""EP7 original-primary revision: exact indexed views and no mixed bindings."""
import copy
import json
from pathlib import Path
import pytest
from scripts.edge_sem import feature_views as fv
from scripts.edge_sem import protocol_p2 as p2
from scripts.edge_sem.io import read,ref


def put(path,value):
    path.write_text(json.dumps(value),encoding="utf8")
    return ref(path)


def fixture_views(tmp_path):
    views={}
    for mode in ("original","anonymous"):
        data=tmp_path/(mode+".npz");data.write_bytes(mode.encode("ascii"))
        view=put(tmp_path/(mode+".json"),dict(view=mode,task_id="task",data=ref(data)))
        views[mode]=view
    prepared=put(tmp_path/"source.json",dict(tasks={"task":{"feature_view":views}}))
    source=dict(source_preparation=prepared,
        tasks={"task":dict(feature_view=views["anonymous"],feature_npz=read(Path(views["anonymous"]["path"]))["data"])})
    return source,views


@pytest.mark.parametrize("mode",["original","anonymous"])
def test_selects_exact_sealed_source_index(tmp_path,mode):
    source,views=fixture_views(tmp_path)
    v,d=fv.source_feature(source,"task",mode)
    assert v==views[mode] and d==read(Path(v["path"]))["data"]
    job=dict(task_id="task",token_view=mode,feature_view=v,feature_npz=d)
    assert fv.validate_view(job,dict(token_view=mode,node_features=fv.FEATURE_POLICIES[mode]))==mode


def test_old_implicit_anonymous_policy_is_unchanged(tmp_path):
    source,views=fixture_views(tmp_path)
    v,d=fv.source_feature(source,"task","anonymous")
    job=dict(task_id="task",feature_view=v,feature_npz=d)
    assert fv.validate_view(job,dict(node_features="N-anon-s S0"))=="anonymous"


@pytest.mark.parametrize("field",["view","npz","plan","task"])
def test_mixed_views_data_and_identity_rejected(tmp_path,field):
    source,views=fixture_views(tmp_path)
    v,d=fv.source_feature(source,"task","original")
    job=dict(task_id="task",token_view="original",feature_view=v,feature_npz=d)
    plan=dict(token_view="original",node_features="N-original S0")
    if field=="view":job["feature_view"]=views["anonymous"]
    elif field=="npz":job["feature_npz"]=read(Path(views["anonymous"]["path"]))["data"]
    elif field=="plan":plan=dict(token_view="anonymous",node_features="N-anon-s S0")
    else:job["task_id"]="different"
    with pytest.raises(ValueError):fv.validate_view(job,plan)


def test_original_source_tampering_rejected(tmp_path):
    source,views=fixture_views(tmp_path)
    Path(views["original"]["path"]).write_text("{}",encoding="utf8")
    with pytest.raises(ValueError):fv.source_feature(source,"task","original")


def test_decision_cannot_authorize_wrong_primary(tmp_path):
    path=tmp_path/"decisions.json"
    value=dict(date="2026-11-11",user_request="synthetic only",
        decisions={k:dict(status="confirmed",value=v) for k,v in p2.decisions_for_view("original").items()})
    put(path,value);put(path.with_suffix(".seal.json"),dict(decisions=ref(path)))
    p2.require_decisions(path,"original")
    with pytest.raises(ValueError):p2.require_decisions(path,"anonymous")
    assert p2.decisions_for_view("original")["D2"]==p2.DECISIONS["D2"]
    assert p2.decisions_for_view("original")["D3"]==p2.DECISIONS["D3"]


def test_registration_separates_original_primary_and_history():
    old=dict(maximum_training_epochs=50,schedule_epochs=50,patience=7)
    new=dict(old,patience=51)
    record=p2.registration({"task":dict(config=new,historical_config=old)},{},[],"original")
    assert record["feature_policy"]=="N-original S0"
    assert record["primary_endpoint"]["view"]=="original"
    assert record["decisions"]["D1"]["proposal"]==p2.decisions_for_view("original")["D1"]
    assert record["config_diff"]=={"task":{"patience":{"before":7,"after":51}}}
    assert record["execution_authorized"] is False


def test_registration_and_plan_cannot_mix_primary_views(tmp_path):
    reg=put(tmp_path/"registration.json",dict(feature_policy="N-anon-s S0",
        primary_endpoint=dict(view="N-anon-s")))
    assert fv.validate_plan_view(dict(registration=reg))=="anonymous"
    with pytest.raises(ValueError):
        fv.validate_plan_view(dict(registration=reg,token_view="original"))
