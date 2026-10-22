"""Artifact-only role adapter tests; original sealed runtime remains untouched."""
import copy
import importlib.util
import inspect
import json
from pathlib import Path

import pytest
from scripts.DFG.experiments.stage_i_diagnostics import aggregate as old
from scripts.DFG.experiments.stage_i_diagnostics.tests.test_aggregate import fixture, directory, seal, dump

SPEC=importlib.util.spec_from_file_location("stage_i_aggregate_adapter",Path(__file__).with_name("aggregate_stage_i.py"))
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def make_actual_role_fixture(root):
    jobs=fixture(root)
    plan={"jobs":jobs,"score_role":m.ROLE,"source_score_role":m.SOURCE_ROLE}
    dump(root/"plan.json",plan)
    dump(root/"plan.seal.json",{"plan_sha256":m.sha(root/"plan.json")})
    for i,j in enumerate(jobs):
        d=directory(root,jobs,i)
        for ck in ("best","last"):
            p=d/ck/"predictions.json";rows=json.loads(p.read_text())
            for row in rows:row["score_role"]=m.ROLE
            dump(p,rows)
            p=d/ck/"scores.json";rows=json.loads(p.read_text())
            for row in rows:row["score_role"]=m.ROLE
            dump(p,rows)
            p=d/ck/"audit.json";obj=json.loads(p.read_text());obj["score_role"]=m.ROLE;dump(p,obj)
        seal(d)
    return jobs


def test_exact_diagnostic_role_and_source_role_in_all_summaries(tmp_path):
    jobs=make_actual_role_fixture(tmp_path)
    result=m.summarize(tmp_path,jobs,write_outputs=False)
    assert result["status"]=="partial_preview"
    assert result["score_role"]==m.ROLE and result["source_score_role"]=="cv_validation"
    assert all(r["score_role"]==m.ROLE and r["source_score_role"]=="cv_validation"
               for r in result["fold_statistics"]+result["pooled_oof"])
    assert not (tmp_path/"REPORT_DATA.json").exists()
    assert result["changed_prediction_rows"]==40
    assert inspect.getsource(m._compare)==inspect.getsource(old._compare)
    assert inspect.getsource(m._mean_sd)==inspect.getsource(old._mean_sd)
    assert inspect.getsource(m.key)==inspect.getsource(old.key)


@pytest.mark.parametrize("where",["predictions","scores","audit","plan"])
def test_training_role_cannot_replace_diagnostic_role(tmp_path,where):
    jobs=make_actual_role_fixture(tmp_path);d=directory(tmp_path,jobs)
    if where=="plan":
        p=tmp_path/"plan.json";obj=json.loads(p.read_text());obj["score_role"]="cv_validation";dump(p,obj)
        dump(tmp_path/"plan.seal.json",{"plan_sha256":m.sha(p)})
    else:
        p=d/"best"/(where+".json");obj=json.loads(p.read_text())
        if isinstance(obj,list):obj[0]["score_role"]="cv_validation"
        else:obj["score_role"]="cv_validation"
        dump(p,obj);seal(d)
    with pytest.raises(ValueError,match="scoring role"):
        m.summarize(tmp_path,jobs,write_outputs=False)


def test_wrong_source_role_and_plan_sha_rejected(tmp_path):
    jobs=make_actual_role_fixture(tmp_path)
    p=tmp_path/"plan.json";obj=json.loads(p.read_text());obj["source_score_role"]="independent_test";dump(p,obj)
    with pytest.raises(ValueError,match="plan SHA"):
        m.summarize(tmp_path,jobs,write_outputs=False)
    dump(tmp_path/"plan.seal.json",{"plan_sha256":m.sha(p)})
    with pytest.raises(ValueError,match="source scoring role"):
        m.summarize(tmp_path,jobs,write_outputs=False)


def test_formal_outputs_refuse_inconsistent_existing_content(tmp_path):
    jobs=make_actual_role_fixture(tmp_path)
    report=m.summarize(tmp_path,jobs)
    assert report["status"]=="complete"
    assert m.summarize(tmp_path,jobs)==report
    p=tmp_path/"REPORT_DATA.json";p.write_text("preserve original")
    with pytest.raises(FileExistsError):m.summarize(tmp_path,jobs)
    assert p.read_text()=="preserve original"
