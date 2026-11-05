import copy
import json
from pathlib import Path
import pytest
from scripts.node_sem import reporting as r
from scripts.node_sem import batch_na_worker as w
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref


def rows_case():
    job=dict(task_id="fixture_node",granularity="node",
        split=dict(outer_test_files=["a.sol"],inner_val_files=["b.sol"]))
    labels=dict(fixture_node=[dict(file="a.sol",original_graph_node_id=7,
        orig=0,**{"L-audit_target":1,"L-audit_include":True},source_sha256="a"*64)])
    rows=[dict(file="a.sol",original_graph_node_id=7,target=1,score_role="outer_test",best=1,last=0)]
    return job,labels,rows


def test_scoring_aligns_by_identity_not_row_number():
    j,l,rows=rows_case()
    accepted=r.aligned_rows(rows,j,l)
    assert accepted[0]["source_sha256"]=="a"*64
    assert accepted[0]["cohort"]=="nonSolidiFI"


@pytest.mark.parametrize("damage",["file","node","target","role","duplicate","missing"])
def test_scoring_refuses_identity_label_or_population_drift(damage):
    j,l,rows=rows_case()
    if damage=="file":rows[0]["file"]="b.sol"
    elif damage=="node":rows[0]["original_graph_node_id"]=8
    elif damage=="target":rows[0]["target"]=0
    elif damage=="role":rows[0]["score_role"]="inner_val"
    elif damage=="duplicate":rows+=copy.deepcopy(rows)
    else:rows=[]
    with pytest.raises(ValueError):r.aligned_rows(rows,j,l)


def test_no_report_for_incomplete_or_duplicate_matrix():
    with pytest.raises(ValueError):r.summarize_records([],dict(jobs=[dict(task_id="x",profile="G0",name="S4",fold=0,seed=1)]))


def test_selection_reads_only_inner_and_seals_before_outer(tmp_path,monkeypatch):
    j,l,rows=rows_case()
    j.update(profile="G3R",fold=0,seed=1,name="S4",carrier_dim=760)
    j["split"]["inner_val_files"]=["a.sol"]
    rows[0]["score_role"]="inner_val"
    jobs=[]
    for name,width in (("S1o",513),("S2",257),("S4",760)):
        jobs.append(dict(j,name=name,carrier_dim=width))
    plan=dict(jobs=jobs,statistics=dict(s_star=dict(candidates=["S1o","S2","S4"])))
    (tmp_path/"plan.json").write_text(json.dumps(plan))
    entries={}
    for job in jobs:
        d=tmp_path/job["name"];(d/"fit").mkdir(parents=True)
        (d/"fit/inner_val_predictions.json").write_text(json.dumps(rows))
        entries[w.job_id(job)]=(d,{})
    accessed=[]
    def read_inner(entry,name):
        accessed.append(name)
        assert name=="inner_val_predictions.json"
        return rows
    monkeypatch.setattr(r,"read_artifact",read_inner)
    selection=r.select_inner(tmp_path,plan,entries,l)
    assert selection["selected"]=="S2" and not selection["outer_test_used"]
    assert (tmp_path/"selection.seal.json").exists()
    assert len(accessed)==3
    # Restart reuses the sealed choice and does not reread predictions.
    assert r.select_inner(tmp_path,plan,entries,l)==selection and len(accessed)==3

def test_full_synthetic_reporting_matrix(tmp_path,monkeypatch):
    from scripts.node_sem import batch_na as na
    from scripts.DFG.experiments.common import metrics
    from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref
    root=tmp_path
    labels={};jobs=[];entries={};data={}
    for task,k in na.TASK_FOLDS:
        kind=task.rsplit("_",1)[-1];labels[task]=[]
        for f in range(k):
            for i in (0,1):
                item=dict(file="{}_{}.sol".format(f,i),source_sha256=str(i)*64,
                    orig=i,**{"L-audit_target":i,"L-audit_include":True})
                if kind=="node":item["original_graph_node_id"]=f*2+i
                labels[task].append(item)
        for f in range(k):
            for graph in na.PROFILES:
                for name in na.NAMES:
                    job=dict(task_id=task,granularity=kind,fold=f,seed=1,profile=graph,name=name,
                        carrier_dim={"S0o":512,"S1o":513,"S2":257,"S4":760}[name],
                        split={role+"_files":["{}_{}.sol".format(f,i) for i in (0,1)]
                            for role in ("inner_val","outer_test")},support={})
                    jobs.append(job);key=w.job_id(job);d=root/"runs"/key;(d/"fit").mkdir(parents=True)
                    receipt=dict(total_seconds=1.,actual_device={},resources={})
                    entries[key]=(d,receipt);record={}
                    for role in ("inner_val","outer_test"):
                        rows=[dict(file=src["file"],target=src["orig"],best=src["orig"],last=src["orig"],
                            score_role=role,best_positive_probability=float(src["orig"]),last_positive_probability=float(src["orig"]),
                            **({"original_graph_node_id":src["original_graph_node_id"]} if kind=="node" else {}))
                            for src in labels[task] if src["file"] in job["split"][role+"_files"]]
                        for suffix in ("","_orig_all"):
                            record[role+suffix+"_predictions.json"]=rows
                            (d/"fit"/(role+suffix+"_predictions.json")).write_text(json.dumps(rows))
                    score=metrics([0,1],[0,1])
                    record["result.json"]=dict(outer_test=dict(best=score,last=score),
                        best_epoch=0,last_epoch=0,parameter_count=10,seconds=1.)
                    record["gradient_audit.json"]={}
                    data[str(d)]=record
    lp=root/"labels.json";lp.write_text(json.dumps(labels))
    for j in jobs:j["label_view"]=ref(lp)
    history=root/"historical";(history/"reports").mkdir(parents=True)
    hp=history/"plan.json";hp.write_text("{}")
    hr=history/"reports/report.json";hr.write_text(json.dumps(dict(keyword_baselines=[])))
    hf=history/"reports/fold_metrics.json"
    old=[dict(task_id=j["task_id"],task_kind=j["granularity"],profile=j["profile"],
        fold=j["fold"],seed=1,checkpoint=ck,metrics=metrics([0,1],[0,1]))
        for j in jobs if j["name"]=="S0o" for ck in ("best","last")]
    hf.write_text(json.dumps(old))
    plan=dict(jobs=jobs,statistics=na.statistics_spec(),source_h8_plan=ref(hp))
    (root/"plan.json").write_text(json.dumps(plan))
    (root/"execution_revision.json").write_text(json.dumps(dict(analysis_refs={"report.json":ref(hr),"fold_metrics.json":ref(hf)})))
    (root/"attention").mkdir();(root/"attention/complete.json").write_text(json.dumps(dict(passed=True,count=120,artifacts=[])))
    monkeypatch.setattr(r.worker,"load_plan",lambda *a:plan)
    monkeypatch.setattr(r,"manifest_attempts",lambda *a:entries)
    seen_outer=[]
    def artifact(entry,name):
        if name.startswith("outer_test") or name=="result.json":
            assert (root/"selection.seal.json").exists()
            seen_outer.append(name)
        return data[str(entry[0])][name]
    monkeypatch.setattr(r,"read_artifact",artifact)
    result=r.build(root)
    assert result["passed"] and result["formal_fits"]==240
    assert len(result["paired"])==64 and result["holm"]["family_size"]==4
    assert result["selection"]["selected"]=="S2" and seen_outer
    assert len(json.loads((root/"reports/fold_metrics.json").read_text()))==480
