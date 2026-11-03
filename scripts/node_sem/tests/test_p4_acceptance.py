import copy
import pytest
from scripts.node_sem.p4_verify import verify_report


def example():
    job=dict(config=dict(maximum_training_epochs=50,initial_lr=.001))
    r=dict(job=job,passed=True,formal_fit=False,effective_config=dict(maximum_training_epochs=1,initial_lr=.001),
        epochs=1,only_config_override="maximum_training_epochs",history=[dict(epoch=0,train_loss=1.,inner_val_loss=2.)],
        checkpoint_roundtrip_exact={k:{c:True for c in ["best","last"]} for k in ["inner_val","outer_test"]},
        common_initial_exact=True,modality_projection_gradient_l1=dict(code=1.),gradients=dict(x=dict(finite=True)))
    return r,job


def test_valid_nonformal_acceptance():
    r,j=example();assert verify_report(r,j)


@pytest.mark.parametrize("damage",["job","formal","lr","epochs","loss","reload","initial","gradient","finite"])
def test_smoke_validation_rejects_false_acceptance(damage):
    r,j=example();r=copy.deepcopy(r)
    if damage=="job": r["job"]["config"]["initial_lr"]=1.
    elif damage=="formal": r["formal_fit"]=True
    elif damage=="lr": r["effective_config"]["initial_lr"]=1.
    elif damage=="epochs": r["epochs"]=2
    elif damage=="loss": r["history"][0]["train_loss"]=float("nan")
    elif damage=="reload": r["checkpoint_roundtrip_exact"]["outer_test"]["best"]=False
    elif damage=="initial": r["common_initial_exact"]=False
    elif damage=="gradient": r["modality_projection_gradient_l1"]["code"]=0.
    else: r["gradients"]["x"]["finite"]=False
    with pytest.raises(ValueError):verify_report(r,j)
