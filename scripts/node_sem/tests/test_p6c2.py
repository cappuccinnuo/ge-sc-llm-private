import copy
import numpy as np
import pytest
from scripts.node_sem.p6c2_core import (aligned_kinds, controls, population,
    column_mask, redundancy_one, signal_population)
from scripts.node_sem.p6c_core import logistic_probe, split_indices
from scripts.node_sem.static_profile import load_schema
from scripts.node_sem.facts_schema import NODE_KINDS


def test_applicable_population_and_prevalence():
    schema=load_schema();kinds=np.array(["statement","state_decl","state_decl","function"])
    a=np.zeros((4,schema["dimension"]),dtype=np.float32)
    f=next(f for f in schema["fields"] if f["name"]=="state_decl.public")
    a[:,f["start"]]=[1,1,0,1]  # inapplicable values must not affect prevalence
    presence={n:np.ones(4,dtype=bool) for n in ("code","ctx","static")}
    cols=population(kinds,a,presence,schema);c=cols[f["start"]]
    assert c["n"]==2 and c["positive"]==1 and c["prevalence"]==.5 and c["eligible"]
    assert column_mask(kinds,presence,c).tolist()==[False,True,True,False]
    presence["code"][1]=False
    c=population(kinds,a,presence,schema)[f["start"]]
    assert c["n"]==1 and c["prevalence"]==0 and not c["eligible"]


@pytest.mark.parametrize("field",load_schema()["fields"],ids=lambda f:f["name"])
def test_every_field_uses_its_exact_applicability(field):
    kinds=np.array(NODE_KINDS);presence={n:np.ones(len(kinds),dtype=bool) for n in ("code","ctx","static")}
    got=column_mask(kinds,presence,field)
    assert got.tolist()==[k in field["applicable"] for k in kinds]


def test_missing_ctx_does_not_silently_change_comparison_population():
    presence={n:np.ones(2,dtype=bool) for n in ("code","ctx","static")}
    presence["ctx"][0]=False
    with pytest.raises(ValueError,match="CTX absent"):
        column_mask(np.array(["statement","statement"]),presence,dict(applicable=["statement"]))


def test_control_contains_only_kind_and_syntax():
    schema=load_schema();rng=np.random.RandomState(1)
    a=rng.randint(2,size=(3,schema["dimension"])).astype(np.float32)
    kinds=np.array(["statement","function","condition"])
    syntax=next(f for f in schema["fields"] if f["name"]=="syntax")
    x,names=controls(kinds,a,schema)
    b=1-a;b[:,syntax["start"]:syntax["stop"]]=a[:,syntax["start"]:syntax["stop"]]
    assert np.array_equal(x,controls(kinds,b,schema)[0])
    assert names[:len(NODE_KINDS)]==["node_kind="+k for k in NODE_KINDS]
    assert names[len(NODE_KINDS):]==["syntax="+v for v in syntax["values"]]
    assert np.array_equal(x[:,len(NODE_KINDS):],a[:,syntax["start"]:syntax["stop"]])


def test_fact_alignment_reorders_by_bound_identity():
    rows=[dict(row_key=i,file="f",node_type="t",code_sha256=str(i)) for i in (7,4)]
    facts=[dict(row_key=4,facts=dict(node_kind="function")),dict(row_key=7,facts=dict(node_kind="statement"))]
    assert aligned_kinds(rows,list(reversed(rows)),facts).tolist()==["statement","function"]
    bad=copy.deepcopy(rows);bad[0]["code_sha256"]="different"
    with pytest.raises(ValueError,match="identity"):
        aligned_kinds(rows,bad,facts)
    with pytest.raises(ValueError,match="Duplicate"):
        aligned_kinds(rows,rows+[rows[0]],facts)


def fixture():
    rng=np.random.RandomState(3);rows=[dict(file=str(i//4),row_key=i) for i in range(24)]
    split=dict(inner_train_files=["0","1","2"],inner_val_files=["3"],outer_test_files=["4","5"])
    kinds=np.array(["statement","statement","function","function"]*6)
    y=np.array([0,1,0,1]*6);x=rng.randn(24,3);static=y[:,None]
    presence={n:np.ones(24,dtype=bool) for n in ("code","ctx","static")}
    return rows,split,kinds,y,x,static,presence


def test_wrapper_calls_frozen_probe_and_uses_selected_split_only():
    rows,split,kinds,y,x,static,presence=fixture()
    col=dict(index=0,applicable=["statement"])
    parts=dict(code=x,ctx=x*.5,static=static)
    got,ix=redundancy_one(parts,rows,kinds,presence,col,split,x[:,:1])
    assert all(kinds[i]=="statement" for indexes in ix.values() for i in indexes)
    expected=logistic_probe(x,y,ix);expected.pop("probabilities");expected.pop("predictions")
    assert got["code"]==expected
    changed=x.copy();changed[ix["outer_test"]]+=100
    again,_=redundancy_one(dict(parts,code=changed),rows,kinds,presence,col,split,x[:,:1])
    assert again["code"]["selected_C"]==got["code"]["selected_C"]
    assert again["code"]["candidates"]==got["code"]["candidates"]


def test_kind_only_confound_removed_within_applicable_population():
    rows,split,kinds,y,x,static,presence=fixture()
    control=(kinds=="function").astype(float)[:,None]
    ix=split_indices([r["file"] for r in rows],split,kinds=="statement")
    result=logistic_probe(control,y,ix)
    assert result["auc"]==.5


def test_signal_subset_keeps_only_statement_and_condition_and_counts_originals():
    kinds=np.array(["statement","condition","state_decl","function","env"])
    rows=[dict(file="normal.sol",node_type="type"+str(i),original_graph_node_id=i) for i in range(5)]
    labels=[dict(file=r["file"],original_graph_node_id=i,node_type=r["node_type"],
        **{"L-audit_target":1,"L-audit_include":True}) for i,r in enumerate(rows[:4])]
    presence={n:np.ones(5,dtype=bool) for n in ("code","static")}
    y,base,selected,counts=signal_population(rows,kinds,presence,labels)
    assert base.tolist()==[True,True,True,True,False]
    assert selected.tolist()==[True,True,False,False,False]
    assert counts==dict(statement=1,condition=1,state_decl=1,function=1)

def test_report_group_denominators_keep_unestimable_bits():
    from scripts.node_sem.p6c2_report import bit_summary, grouped
    rows=[]
    for idx,values in ((0,[.96,.98]),(1,[None,None]),(2,[.5,None])):
        for fold,auc in enumerate(values):
            rows.append(dict(task_id="t",fold=fold,source="code",
                column=dict(index=idx,group="A1",parent_group="A"),
                auc=auc,balanced_accuracy=auc,status="ok" if auc is not None else "not_estimable"))
    bits=bit_summary(rows)
    g=next(r for r in grouped(bits) if r["level"]=="all")
    assert g["eligible_bits"]==3 and g["estimable_bits"]==2 and g["high_auc_bits"]==1
    assert g["high_auc_fraction_estimable"]==.5 and g["high_auc_fraction_eligible"]==1/3
    assert g["all_folds_estimable_bits"]==1
    assert g["median_fold_mean_auc"]==pytest.approx(.735)


def test_report_refuses_duplicate_result_identity():
    from scripts.node_sem.p6c2_report import bit_summary
    r=dict(task_id="t",fold=0,source="code",column=dict(index=0),auc=.9,balanced_accuracy=.9)
    with pytest.raises(ValueError,match="Duplicate"):
        bit_summary([r,r])


def test_report_pairs_only_same_bit_and_fold():
    from scripts.node_sem.p6c2_report import pair_rows
    def row(fold,source,auc):
        return dict(task_id="t",fold=fold,source=source,
            column=dict(index=1,group="K",parent_group="K"),auc=auc,status="ok")
    result=pair_rows([row(0,"code",.8),row(1,"code",.7)],
                    [row(0,"kind_syntax",.5)],"comparison","kind_syntax")
    assert result[0]["auc_delta"]==pytest.approx(.3)
    assert result[1]["auc_delta"] is None
    assert result[1]["reference_status"]=="ineligible_in_reference"


def test_report_names_parent_and_atomic_groups_separately():
    from scripts.node_sem.p6c2_report import bit_summary, grouped
    rows=[dict(task_id="t",fold=0,source="code",column=dict(index=i,group=g,parent_group="A"),
        auc=.8,balanced_accuracy=.8) for i,g in enumerate(["A","A1"])]
    summary=grouped(bit_summary(rows))
    parent=next(r for r in summary if r["level"]=="parent" and r["group"]=="A")
    atomic=next(r for r in summary if r["level"]=="atomic" and r["group"]=="A")
    assert parent["eligible_bits"]==2 and atomic["eligible_bits"]==1
