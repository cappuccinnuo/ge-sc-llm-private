import copy
import pytest
from scripts.node_sem.llm_pilot_v2 import choose
from scripts.node_sem.llm_post import gates


def candidates():
    rows=[]
    for task in ("access_control_contract","access_control_node","reentrancy_contract","reentrancy_node"):
        for solidifi in (False,True):
            for i in range(20):
                key="{}:{}:{}".format(task,solidifi,i)
                rows.append(dict(task_id=task,solidifi=solidifi,cache_key=key,function_id=key,
                    function_source_sha256=key,overlap_v1=False,positive_function=task.endswith("_node") and not solidifi and i<8))
    return rows


def test_fixed_pilot_unique_strata_positive_and_reproducibility():
    a=choose(candidates())
    assert a==choose(list(reversed(candidates())))
    assert len(a)==50 and len({x["cache_key"] for x in a})==50
    assert sum(not x["solidifi"] for x in a)==26
    assert sum(x["positive_function"] for x in a)>=10
    for task in {x["task_id"] for x in a}:
        assert sum(x["task_id"]==task for x in a)==(13 if task.endswith("_node") else 12)


def test_sampling_refuses_unsatisfied_positive_quota():
    rows=candidates()
    for row in rows:row["positive_function"]=False
    with pytest.raises(ValueError,match="ten"):
        choose(rows)


def test_sampling_does_not_count_duplicate_cache_as_new_function():
    rows=candidates()
    for row in rows:row["cache_key"]="same"
    with pytest.raises(ValueError,match="ten"):
        choose(rows)

def test_only_minimal_positive_overlap_and_no_duplicate_function_sha():
    rows=candidates()
    for row in rows:
        row["overlap_v1"]=row["positive_function"]
    a=choose(rows)
    assert len([r for r in a if r["overlap_v1"]])==10
    assert all(r["positive_function"] for r in a if r["overlap_v1"])
    assert len({r["function_source_sha256"] for r in a})==50
    for row in rows:
        if row["positive_function"] and row["function_id"].endswith(":0"):
            row["overlap_v1"]=False
    a=choose(rows)
    assert len([r for r in a if r["overlap_v1"]])==8

def test_excludes_nonpositive_old_functions():
    rows=candidates()
    for row in rows:
        row["overlap_v1"]=not row["positive_function"] and row["function_id"].endswith(":0")
    assert not any(r["overlap_v1"] for r in choose(rows))
