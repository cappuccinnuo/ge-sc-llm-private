"""Local directional adapter; original classifiers, HGT and features unchanged."""
from types import FunctionType
from scripts.DFG.state.stage_f import model_adapter as prior_adapter
from scripts.DFG.state.stage_f import initialization as prior_init
from scripts.DFG.state.stage_f import FORWARD_RELATIONS as OLD_FORWARD
from scripts.DFG.experiments.e23_pilot import model as prior
from sco_models.model_hgt import HGTVulNodeClassifier, HGTVulGraphClassifier
from scripts.DFG.experiments.common import tensor_digest
from . import RELATION
FORWARD_RELATIONS = frozenset(OLD_FORWARD) | {RELATION}
ADAPTER_VERSION = "author-hcg-ddg-guard-directional-v1"
INITIALIZATION_VERSION = prior_init.INITIALIZATION_VERSION + "/saved-untrained-guard-v1"

def adapt(fn, **handlers):
    return FunctionType(fn.__code__, dict(fn.__globals__, **handlers), fn.__name__, fn.__defaults__, fn.__closure__)

reflected_input = adapt(prior_adapter.reflected_input, FORWARD_RELATIONS=FORWARD_RELATIONS)
build_dgl = adapt(prior_adapter.build_dgl, reflected_input=reflected_input)
_construct = adapt(prior._construct, reflected_input=reflected_input, build_dgl=build_dgl)
validate_registration = adapt(prior.validate_registration, reflected_input=reflected_input)
semantic_state = prior.semantic_state
move_to_device = prior.move_to_device
_initialize = adapt(prior_init.initialize_pair, FORWARD_RELATIONS=FORWARD_RELATIONS,
                    INITIALIZATION_VERSION=INITIALIZATION_VERSION)

class GuardNodeClassifier(HGTVulNodeClassifier):
    def __init__(self, path, device="cpu", hidden_size=128, layers=2, heads=8):
        _construct(self, "node", path, device, hidden_size, layers, heads)

class GuardGraphClassifier(HGTVulGraphClassifier):
    def __init__(self, path, device="cpu", hidden_size=128, layers=2, heads=8):
        _construct(self, "contract", path, device, hidden_size, layers, heads)

def make_model(task, path, device="cpu", hidden_size=128, layers=2, heads=8):
    if task not in ("node", "contract"):
        raise ValueError("Unknown task")
    cls = GuardNodeClassifier if task == "node" else GuardGraphClassifier
    model = cls(path, device, hidden_size, layers, heads).to(device)
    validate_registration(model)
    return model

def extend_saved_initial(baseline, candidate, record, expected, seed):
    """Only sealed optimizer_steps=0 weights qualify; never a trained checkpoint."""
    import torch
    checks = dict(kind="untrained_initial", optimizer_steps=0, **expected)
    if any(record.get(k) != v for k, v in checks.items()):
        raise ValueError("Historical untrained identity mismatch")
    if tensor_digest(record["state_dict"]) != record["state_sha256"]:
        raise ValueError("Historical untrained tensor digest mismatch")
    baseline.load_state_dict(record["state_dict"], strict=True)
    if any(p.grad is not None for m in (baseline, candidate) for p in m.parameters()):
        raise ValueError("Initialization has gradient history")
    if any(c[1] == RELATION for c in baseline.etypes_dict):
        raise ValueError("Historical baseline already contains CONTROL_DEPENDENCE")
    before = tensor_digest(baseline.state_dict())
    new = set(candidate.etypes_dict) - set(baseline.etypes_dict)
    if any(c[1] != RELATION for c in new):
        raise ValueError("Only CONTROL_DEPENDENCE may extend the sealed baseline")
    result = _initialize(baseline, candidate, seed=seed)
    a, b = semantic_state(baseline), semantic_state(candidate)
    if not set(a) <= set(b) or any(not torch.equal(a[k], b[k]) for k in a):
        raise AssertionError("Common semantic initial parameters differ")
    if tensor_digest(baseline.state_dict()) != before:
        raise AssertionError("Historical untrained baseline was changed")
    prior._independent_storage({"baseline":baseline,"candidate":candidate})
    result.update(initialization_source="sealed overall_cv optimizer_steps=0 state; never trained weights",
                  all_common_semantic_tensors_equal=True, shared_sha256=tensor_digest(a),
                  baseline_state_sha256=before, independent_storage=True,
                  numeric_algorithm_unchanged=True)
    return result
