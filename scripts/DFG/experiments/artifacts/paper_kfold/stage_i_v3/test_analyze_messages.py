"""Stdlib-only synthetic audit fixtures; does not read real replay predictions."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SPEC=importlib.util.spec_from_file_location("message_postprocess",Path(__file__).with_name("analyze_messages.py"))
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True),encoding="utf8")


def data_row(c,train,val,selected,layer,zero):
    original=3.0 if c[1]=="next" else 2.0
    if zero and layer==1:original+=4
    return {"canonical":list(c),"masked":selected and zero,"edge_count":train+val,
        "destination_node_count":3,"cross_mean_relation_count":2,"observations":1,
        "original_aggregate_l2_sum":original,"original_aggregate_l2_max":original,
        "zeroed_aggregate_l2_sum":original if selected and zero else 0.,
        "effective_aggregate_l2_sum":0. if selected and zero else original}


def make_audit(support,fold):
    train,val=(0,2) if fold==0 else (1,1)
    normal,zero={},{}
    schema=[tuple(r["canonical"]) for r in support["schema"]["canonical_relations"]]
    for layer in (0,1):
        for dest,is_zero in ((normal,False),(zero,True)):
            dest[str(layer)]={"forward_calls":1,"canonical":{
                json.dumps(list(c)):data_row(c,train,val,c[1] in m.STATE,layer,is_zero) for c in schema},
                "cross_mean":{"s":{"cross_mean_relation_count":2,"observations":1,
                    "effective_aggregate_l2_sum":1.0,"effective_aggregate_l2_max":1.0}}}
    messages={name:{"record":False,"layers":{}} for name in m.CONDITIONS}
    for name,layers in (("N",normal),("Z_ALL",zero)):
        messages[name]={"record":True,"layers":layers,"norm_unit":"canonical_destination_sum_Frobenius_L2",
            "requested_relations":[] if name=="N" else sorted(m.STATE)}
    return {"score_role":m.SCORE_ROLE,"gates":{
        "wrapper_exact":True,"restored_native_exact":True,"weights_unchanged":True,
        "parameter_objects_unchanged":True,"input_unchanged":True,"no_gradients":True,"optimizer_steps":0,
        "archive_replay":{"predictions_exact":True,"metrics_match":True,"probability_exact":False,"probability_abs_max":1e-7}},
        "messages":messages}


def build_fixture(root,count=60):
    jobs=[]
    canonical=[("s","next","s"),("s","STATE_DEF_USE","s")]
    for cohort in ("reentrancy_author","access_control_author"):
        for task in ("contract","node"):
            for fold in range(5 if task=="contract" else 10):
                for variant in ("E3a","E3b"):
                    train,val=(0,2) if fold==0 else (1,1)
                    support={"schema":{"canonical_relations":[{"canonical":list(c)} for c in canonical]},
                        "relations":[{"canonical":list(c),"train_edges":train,"val_edges":val} for c in canonical],
                        "enhancement_support":{r:{"train":train if r=="STATE_DEF_USE" else 0,"val":val if r=="STATE_DEF_USE" else 0} for r in m.STATE}}
                    job={"task_id":cohort+"_"+task,"task":task,"cohort":cohort,"fold":fold,"variant":variant,
                         "receipt_sha256":"a"*64}
                    p=root/"manifests"/(job["task_id"]+str(fold)+variant+".json")
                    info=dict(job,config={"layers":2},support={variant:support})
                    dump(p,info);job.update(task_manifest=str(p),task_manifest_sha256=m.sha(p));jobs.append(job)
    plan={"jobs":jobs,"score_role":m.SCORE_ROLE,"source_score_role":m.SOURCE_SCORE_ROLE,"optimizer_steps":0,"retraining":False,"inference_only":True,
          "record_messages":"N and Z_ALL only; others sensitivity-only to avoid redundant reductions"}
    dump(root/"plan.json",plan);dump(root/"plan.seal.json",{"plan_sha256":m.sha(root/"plan.json")})
    for job in jobs[:count]:
        d=root/"replays"/job["task_id"]/("fold_"+str(job["fold"]))/job["variant"]
        info=json.loads(Path(job["task_manifest"]).read_text())
        for ck in ("best","last"):
            dump(d/ck/"audit.json",make_audit(info["support"][job["variant"]],job["fold"]))
            dump(d/ck/"scores.json",[]);dump(d/ck/"predictions.json",[])
        reseal(root,d)
    return jobs


def reseal(root,d):
    artifacts={str(p.relative_to(d)):m.sha(p) for p in d.glob("*/*.json")}
    dump(d/"receipt.json",{"status":"passed","plan_sha256":m.sha(root/"plan.json"),
        "source_receipt_sha256":"a"*64,"artifact_sha256":artifacts})


def first(root,jobs):
    j=jobs[0]
    return root/"replays"/j["task_id"]/("fold_"+str(j["fold"]))/j["variant"]


def test_full60_message_validation_support_and_idempotence(tmp_path):
    build_fixture(tmp_path)
    report=m.analyze(tmp_path)
    assert report["completed_models"]==60 and report["checkpoint_audits"]==120
    assert report["state_canonical_layer_observations"]==240
    assert report["state_normal_nonzero_observations"]==240
    assert report["all_requested_state_effective_messages_zero"]
    assert report["all_cross_mean_denominators_preserved"]
    assert report["not_per_edge_norms"] and report["not_causal_contribution_share"]
    assert any(r["train_edges"]==0 and r["val_edges"]>0 for r in report["relation_presence"])
    assert any(r["status"]=="absent_expected_noop" for r in report["relation_presence"])
    assert (tmp_path/"message_norm_summary.csv").exists()
    assert m.analyze(tmp_path)==report


def test_partial_never_writes_and_formal_refuses(tmp_path):
    build_fixture(tmp_path,2)
    report=m.analyze(tmp_path,True)
    assert report["status"]=="partial_preview" and report["completed_models"]==2
    assert not (tmp_path/"message_norm_summary.csv").exists()
    with pytest.raises(ValueError,match="all 60"):
        m.analyze(tmp_path)


@pytest.mark.parametrize("change,expected",[("mean","denominator"),("zero","completely zero"),
    ("base","Base/DATA"),("support","split support"),("layer0","First-layer"),
    ("nonfinite","finite nonnegative"),("schema","schema mismatch"),("record","recording strategy")])
def test_changed_messages_refused_even_with_receipt(tmp_path,change,expected):
    jobs=build_fixture(tmp_path,1);d=first(tmp_path,jobs);p=d/"best/audit.json";a=m.read(p)
    layer=a["messages"]["Z_ALL"]["layers"]["0"]
    base=next(r for r in layer["canonical"].values() if r["canonical"][1]=="next")
    state=next(r for r in layer["canonical"].values() if r["canonical"][1]=="STATE_DEF_USE")
    if change=="mean":state["cross_mean_relation_count"]+=1
    elif change=="zero":state["effective_aggregate_l2_sum"]=1
    elif change=="base":base["zeroed_aggregate_l2_sum"]=1
    elif change=="support":state["edge_count"]+=1
    elif change=="layer0":state["original_aggregate_l2_sum"]+=1;state["zeroed_aggregate_l2_sum"]+=1
    elif change=="nonfinite":state["original_aggregate_l2_sum"]=float("inf")
    elif change=="schema":layer["canonical"].pop(next(iter(layer["canonical"])))
    elif change=="record":a["messages"]["Z_D"]["record"]=True
    dump(p,a);reseal(tmp_path,d)
    with pytest.raises(ValueError,match=expected):m.analyze(tmp_path,True)


def test_artifact_changed_without_receipt_rejected(tmp_path):
    jobs=build_fixture(tmp_path,1);d=first(tmp_path,jobs);p=d/"best/audit.json"
    p.write_text(p.read_text()+" ")
    with pytest.raises(ValueError,match="artifact changed"):m.analyze(tmp_path,True)


def test_different_summary_never_overwritten(tmp_path):
    build_fixture(tmp_path);m.analyze(tmp_path)
    p=tmp_path/"message_edge_effectiveness.json";p.write_text("preserve me")
    with pytest.raises(FileExistsError,match="Refuse different"):m.analyze(tmp_path)
    assert p.read_text()=="preserve me"


def test_exact_actual_diagnostic_role_required_not_training_or_arbitrary_role(tmp_path):
    jobs=build_fixture(tmp_path,1);d=first(tmp_path,jobs);p=d/"best/audit.json"
    audit=m.read(p)
    assert audit["score_role"]=="exploratory_cv_validation_fixed_checkpoint_sensitivity"
    report=m.analyze(tmp_path,True)
    assert report["score_role"]==audit["score_role"]
    assert report["source_score_role"]=="cv_validation"
    audit["score_role"]="cv_validation";dump(p,audit);reseal(tmp_path,d)
    with pytest.raises(ValueError,match="Wrong scoring role"):m.analyze(tmp_path,True)


def test_plan_cannot_authorize_an_arbitrary_score_role(tmp_path):
    build_fixture(tmp_path,0)
    p=tmp_path/"plan.json";plan=m.read(p)
    plan["score_role"]="independent_test";dump(p,plan)
    dump(tmp_path/"plan.seal.json",{"plan_sha256":m.sha(p)})
    with pytest.raises(ValueError,match="sealed diagnostic/source scoring role"):
        m.analyze(tmp_path,True)
