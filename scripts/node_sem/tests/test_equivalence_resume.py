"""Acceptance-only scheduler revision and immutable completed-fit reuse."""
import copy
import json
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest
import torch
from torch.optim.lr_scheduler import OneCycleLR

from scripts.node_sem.equivalence import assert_exact
from scripts.node_sem import equivalence_resume as resume
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref, checked, read
from scripts.DFG.experiments.common import tensor_digest


def scheduler():
    parameter = torch.nn.Parameter(torch.tensor([1.0]))
    optimizer = torch.optim.Adam([parameter], lr=0.01)
    return OneCycleLR(optimizer, max_lr=0.01, total_steps=10)


def test_independent_onecycle_cosine_methods_have_same_semantics():
    a, b = scheduler(), scheduler()
    assert a is not b
    assert a.anneal_func != b.anneal_func
    assert a.anneal_func.__func__ is b.anneal_func.__func__
    assert_exact(a.state_dict(), b.state_dict(), "last/scheduler")


@pytest.mark.parametrize("replacement", ["linear", "wrong_owner", "plain_function", "same_name_different_function"])
def test_method_acceptance_is_exact_implementation_and_owner(replacement):
    a, b = scheduler(), scheduler()
    left, right = a.state_dict(), b.state_dict()
    if replacement == "linear":
        right["anneal_func"] = b._annealing_linear
    elif replacement == "wrong_owner":
        right["anneal_func"] = MethodType(OneCycleLR._annealing_cos, object())
    elif replacement == "plain_function":
        right["anneal_func"] = OneCycleLR._annealing_cos
    else:
        def _annealing_cos(self, start, end, pct):
            return start
        right["anneal_func"] = MethodType(_annealing_cos, b)
    with pytest.raises(AssertionError, match="implementation"):
        assert_exact(left, right, "best/scheduler")


def test_numerical_scheduler_state_remains_zero_tolerance():
    a, b = scheduler(), scheduler()
    left, right = a.state_dict(), b.state_dict()
    right["base_lrs"][0] += 1e-12
    with pytest.raises(AssertionError, match="base_lrs"):
        assert_exact(left, right, "best/scheduler")


def test_bound_methods_elsewhere_do_not_gain_exception():
    a, b = scheduler(), scheduler()
    with pytest.raises(AssertionError):
        assert_exact(a.anneal_func, b.anneal_func, "optimizer/anneal_func")


def archive_fixture(tmp_path, monkeypatch):
    def dump(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf8")
        return ref(path)
    previous = tmp_path / "old_equivalence.py"
    previous.write_text("# original comparator")
    retained = tmp_path / "completed_fit.json"
    retained.write_text('{"completed":true}')
    source = dump("h8_plan.json", {"historical": True})
    old_runtime = {"scripts/node_sem/equivalence.py": ref(previous)["sha256"],
                   "scripts/DFG/frozen.py": "a" * 64}
    old_plan = dump("plan.json", {"runtime": old_runtime, "source_h8_plan": source})
    old_seal = dump("plan.seal.json", {"plan": old_plan})
    failure = dump("failure.json", {"error": "best/scheduler/anneal_func"})
    approval = dict(approved=True, user_answer="Approved exact bound method semantics",
        retrain_reentrancy=False, formal_training=False,
        old_plan=old_plan, old_seal=old_seal, failure=failure,
        previous_source=ref(previous), retained_files={str(retained): ref(retained)["sha256"]})
    current = dict(old_runtime)
    current["scripts/node_sem/equivalence.py"] = "b" * 64
    current["scripts/node_sem/equivalence_resume.py"] = "c" * 64
    # Replace only this new acceptance module's dependencies, never frozen modules.
    monkeypatch.setattr(resume, "execution", SimpleNamespace(runtime_refs=lambda: copy.deepcopy(current)))
    monkeypatch.setattr(resume, "h8", SimpleNamespace(load=lambda path: read(path)))
    return approval, current


def test_archive_keeps_original_plan_seal_and_completed_fit_unchanged(tmp_path, monkeypatch):
    approval, _ = archive_fixture(tmp_path, monkeypatch)
    before = {str(p): p.read_bytes() for p in tmp_path.iterdir()}
    original = resume._archive(approval)
    assert original["runtime"]["scripts/node_sem/equivalence.py"] == approval["previous_source"]["sha256"]
    assert before == {str(p): p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("mutation", ["frozen_source", "extra_file", "missing_file", "no_revision"])
def test_archive_rejects_unapproved_runtime_changes(tmp_path, monkeypatch, mutation):
    approval, current = archive_fixture(tmp_path, monkeypatch)
    if mutation == "frozen_source":
        current["scripts/DFG/frozen.py"] = "d" * 64
    elif mutation == "extra_file":
        current["scripts/node_sem/unapproved.py"] = "d" * 64
    elif mutation == "missing_file":
        del current["scripts/DFG/frozen.py"]
    else:
        current["scripts/node_sem/equivalence.py"] = approval["previous_source"]["sha256"]
    with pytest.raises(ValueError):
        resume._archive(approval)


@pytest.mark.parametrize("field,value", [
    ("approved", False), ("user_answer", ""), ("retrain_reentrancy", True), ("formal_training", True),
])
def test_archive_requires_bounded_explicit_approval(tmp_path, monkeypatch, field, value):
    approval, _ = archive_fixture(tmp_path, monkeypatch)
    approval[field] = value
    with pytest.raises(PermissionError):
        resume._archive(approval)


@pytest.mark.parametrize("target", ["old_seal", "previous_source", "retained"])
def test_archive_detects_tampered_retained_evidence(tmp_path, monkeypatch, target):
    approval, _ = archive_fixture(tmp_path, monkeypatch)
    path = (Path(next(iter(approval["retained_files"]))) if target == "retained"
            else Path(approval[target]["path"]))
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError):
        resume._archive(approval)


@pytest.mark.parametrize("side", ["historical", "nodesem"])
def test_completed_reconstruction_reads_weights_without_any_fit(tmp_path, monkeypatch, side):
    def dump(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf8")
        return ref(path)
    initial = {"w": torch.tensor([1.0])}
    binding = {"initial_state_sha256": tensor_digest(initial)}
    cfg = {"maximum_training_epochs": 50}
    references = {}
    payloads = {}
    for name, value in (("best", 2.0), ("last", 3.0)):
        checkpoint = tmp_path / (name + ".pt")
        checkpoint.write_bytes(("sealed fixture " + name).encode())
        references[name] = ref(checkpoint)
        payloads[str(checkpoint)] = dict(binding=binding, model_input={"input": "same"},
                                        state_dict={"w": torch.tensor([value])})
    dump("cpu_acceptance.json", dict(kind="nonformal_cpu_equivalence",
        original_config=cfg, effective_config={"maximum_training_epochs": 2},
        only_config_override=["maximum_training_epochs"], actual_device="cpu",
        checkpoint_refs=references, constructor_seconds=1.0, fit_seconds=2.0))
    dump("binding.json", binding)
    dump("result.json", {"checkpoint_sha256": {k: v["sha256"] for k, v in references.items()}})
    (tmp_path / "history.jsonl").write_text('{"epoch":0}\n{"epoch":1}\n')
    for role in ("inner_val", "outer_test", "inner_val_orig_all", "outer_test_orig_all"):
        dump(role + "_predictions.json", [{"file": "fixture", "target": 1, "best": 1, "last": 1}])
    model = object()
    events = []
    def construct(plan, job, device):
        events.append(("construct", device))
        return model
    def guard_input(value, expected, external_inputs):
        assert value is model
        assert expected == {"input": "same"}
        assert external_inputs == binding
        events.append(("input", True))
    def load(reference, map_location):
        checked(reference)
        assert map_location == "cpu"
        events.append(("load", Path(reference["path"]).name))
        return payloads[reference["path"]]
    dependency = SimpleNamespace(construct=construct,
        binding_parts=lambda *args: (binding, {}))
    monkeypatch.setattr(resume, "h8", dependency)
    monkeypatch.setattr(resume, "execution", dependency)
    monkeypatch.setattr(resume, "snapshot", lambda value: {"state": initial})
    monkeypatch.setattr(resume, "load_checked", load)
    monkeypatch.setattr(resume, "assert_model_input", guard_input)
    monkeypatch.setattr(resume, "_one_fit",
                        lambda *args, **kwargs: pytest.fail("Completed fit must never restart"))
    before = {str(p): p.read_bytes() for p in tmp_path.iterdir()}
    value = resume._retained_fit(side, {}, {}, {}, {"config": cfg}, tmp_path)
    assert events.count(("construct", "cpu")) == 1
    assert ("load", "best.pt") in events and ("load", "last.pt") in events
    assert torch.equal(value["after"]["w"], torch.tensor([3.0]))
    assert value["retained_fit"] is True and value["initial_snapshot_reconstructed"] is True
    assert before == {str(p): p.read_bytes() for p in tmp_path.iterdir()}
