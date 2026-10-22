import copy
import pytest
import torch
from scripts.DFG.experiments.stage_k_pilot.common import expected_jobs,TASKS,tensor_digest
from scripts.DFG.experiments.stage_k_pilot import training,checkpoint
from scripts.DFG.experiments.e23_pilot import training as oldtraining
from scripts.DFG.experiments.e23_pilot.model import make_model,validate_registration
from scripts.DFG.experiments.e23_pilot.runtime import graph_schema_and_support
from scripts.DFG.experiments.stage_k_pilot.worker import check_initial
from scripts.DFG.experiments.paper_protocol import NAME,VERSION,FORWARD_SCOPE,SCORE_ROLE
from scripts.DFG.state.stage_f.initialization import INITIALIZATION_VERSION
from scripts.DFG.experiments.stage_k_pilot import VERSION as K
from scripts.DFG.state.stage_j.tests.test_pipeline import graph

def test_only_two_tasks_four_overall_fits():
 jobs=expected_jobs()
 assert len(jobs)==4 and {j["variant"] for j in jobs}=={"B0","B1"}
 assert {j["task_id"] for j in jobs}==set(TASKS)
 assert all(j["fold"]==0 for j in jobs)

def test_numerical_training_loop_reused_without_mutating_original():
 assert training.FIT.__code__ is oldtraining.FIT.__code__
 assert training.fit.__code__ is oldtraining.fit.__code__
 assert oldtraining.fit.__globals__["FIT"] is oldtraining.FIT
 assert oldtraining.FIT.__globals__["save_checkpoint"] is not checkpoint.save_checkpoint

@pytest.fixture
def model_binding():
 m=make_model("node",graph(),"cpu")
 schema=validate_registration(m)
 b={"protocol":NAME,"protocol_version":VERSION,"forward_scope":FORWARD_SCOPE,"score_role":SCORE_ROLE,
    "experiment_version":K,"initialization_version":INITIALIZATION_VERSION,"variant":"B1",
    "split":{"fold":0},"registered_schema":schema}
 return m,b

def test_real_schema_binding(model_binding):
 m,b=model_binding;checkpoint.validate_binding(m,b)

@pytest.mark.parametrize("key,value",[("variant","E3b"),("score_role","independent_test"),("experiment_version","old")])
def test_foreign_binding_rejected(model_binding,key,value):
 m,b=model_binding;b=copy.deepcopy(b);b[key]=value
 with pytest.raises(ValueError):checkpoint.validate_binding(m,b)

def test_unregistered_or_misaligned_relation_rejected(model_binding):
 m,b=model_binding
 c=next(iter(m.etypes_dict));m.etypes_dict[c]=len(m.etypes_dict)+3
 with pytest.raises((ValueError,AssertionError)):checkpoint.validate_binding(m,b)

def test_initial_state_identity_and_untrained_requirement():
 state={"a":torch.ones(3)}
 info={"task_id":"sample","fit_seed":1,"initialization":{"B1":{"state_sha256":tensor_digest(state)}}}
 rec={"kind":"untrained_initial","optimizer_steps":0,"task_id":"sample","fold":0,"variant":"B1",
      "fit_seed":1,"state_dict":state}
 check_initial(rec,info,"B1")
 for key,value in [("optimizer_steps",1),("task_id","wrong"),("variant","B0"),("fit_seed",2)]:
  changed=dict(rec);changed[key]=value
  with pytest.raises(ValueError):check_initial(changed,info,"B1")
 changed=dict(rec,state_dict={"a":torch.zeros(3)})
 with pytest.raises(ValueError):check_initial(changed,info,"B1")
