"""Freeze matrix/config/selection and keep Prompt8G preparation unauthorized."""
import copy
import pytest
from scripts.DFG.dfg_v2.benchmark_v2.spelling_plan import assert_frozen_matrix


def plans():
    old = {k: {"value":k} for k in
           ("protocol","protocol_version","split_seed","proposed_training_seeds",
            "label_policies","statistics","statistical_label_scope","selection_rule",
            "initialization","G0P","scoring")}
    old.update(jobs=[dict(task_id="toy",fold=0,seed=1,profile="G0",execution_authorized=False)],
               fit_count=170,tasks={"toy":dict(feature_view="old",effective_config={"lr":.001},
                                             folds="frozen",profiles={"G0":"frozen_graph"})})
    new=copy.deepcopy(old)
    new.update(execution_authorized=False,selected_training_seeds=None,
               selected_label_policy=None,selected_execution_location=None)
    new["tasks"]["toy"]["feature_view"]="new accepted view"
    return old,new


def test_only_feature_view_is_rebound():
    old,new=plans()
    assert_frozen_matrix(old,new)


@pytest.mark.parametrize("key",["jobs","fit_count","label_policies","statistics","selection_rule",
                                "initialization","G0P","scoring","split_seed"])
def test_frozen_matrix_or_rules_cannot_drift(key):
    old,new=plans()
    new[key]=None
    with pytest.raises(ValueError,match="Frozen experiment rule"):
        assert_frozen_matrix(old,new)


@pytest.mark.parametrize("key",["effective_config","folds","profiles"])
def test_task_config_fold_and_graph_cannot_change(key):
    old,new=plans()
    new["tasks"]["toy"][key]="different"
    with pytest.raises(ValueError,match="Frozen task input"):
        assert_frozen_matrix(old,new)


def test_preparation_cannot_enable_execution():
    old,new=plans();new["execution_authorized"]=True
    with pytest.raises(ValueError,match="cannot authorize"):
        assert_frozen_matrix(old,new)


@pytest.mark.parametrize("key",["selected_training_seeds","selected_label_policy","selected_execution_location"])
def test_no_silent_user_choice(key):
    old,new=plans();new[key]="chosen"
    with pytest.raises(ValueError,match="choices"):
        assert_frozen_matrix(old,new)
