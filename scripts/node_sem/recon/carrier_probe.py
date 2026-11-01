"""NS-P0 CPU-only carrier interface probes; no training or stored checkpoints.

Read-only real input plus synthetic in-memory fixtures. Temporary files exist
only to exercise the existing checkpoint SHA binding API and are removed on exit.
This is not a NodeSem feature extractor or adapter implementation.
"""
import argparse
import contextlib
import copy
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import networkx as nx
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.experiments.common import tensor_digest
from scripts.DFG.dfg_v2 import DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW
from scripts.DFG.dfg_v2.model import make_model, validate_registration
from scripts.DFG.dfg_v2.benchmark_v2 import checkpoint, runtime_model, support
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import assemble
from scripts.DFG.dfg_v2.supervision import DfgV2Supervision


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _ref(path):
    return dict(path=str(path), sha256=_sha(path))


def _checked(reference):
    path = Path(reference["path"])
    if _sha(path) != reference["sha256"]:
        raise ValueError("Frozen input SHA differs: " + str(path))
    return path


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _fixture(enhanced=False):
    """Tiny file-disconnected graph with all v2 families when enhanced."""
    rng = np.random.RandomState(20)
    graph = nx.MultiDiGraph()
    for index, filename in enumerate(("train.sol", "val.sol", "test.sol")):
        nodes = ["{}:{}".format(filename, name) for name in ("decl", "write", "use")]
        for j, node in enumerate(nodes):
            graph.add_node(node, source_file=filename,
                           node_type="new_variable" if j == 0 else "expression_statement",
                           code="uint x;" if j == 0 else ("x = 1;" if j == 1 else "x + 1;"),
                           node_info_vulnerabilities=[{"category": "synthetic", "lines": [1]}]
                           if j == 1 else None,
                           token=rng.normal(size=512).astype(np.float32))
        graph.add_edge(nodes[0], nodes[1], edge_type="next_line")
        graph.add_edge(nodes[1], nodes[2], edge_type="next_line")
        if enhanced:
            graph.add_edge(nodes[1], nodes[2], edge_type=DATA_DEF_USE)
            graph.add_edge(nodes[1], nodes[0], edge_type=WRITES_STATE)
            graph.add_edge(nodes[0], nodes[2], edge_type=READS_STATE)
            env = filename + ":env"
            graph.add_node(env, source_file=filename, node_type="env_source",
                           code="msg.sender", token=rng.normal(size=512).astype(np.float32))
            graph.add_edge(env, nodes[2], edge_type=ENV_FLOW)
    return graph


def _carry(graph, width=600):
    result = copy.deepcopy(graph)
    rng = np.random.RandomState(61600)
    for _, attrs in result.nodes(data=True):
        attrs["token"] = rng.normal(size=width).astype(np.float32)
    return result


def _construct(graph, task, profile, layers=2):
    torch.manual_seed(616)
    start = time.monotonic()
    model = make_model(task, graph, profile, "cpu", node_feature="inside_token",
                       hidden_size=128, layers=layers, heads=8,
                       reducer="mean", layer_impl="shared_projection")
    seconds = time.monotonic() - start
    assert all(p.device.type == "cpu" for p in model.parameters())
    return model, seconds


def _temporary_binding(model, graph, parts, config):
    before = tensor_digest(model.state_dict())
    with tempfile.TemporaryDirectory(prefix="nodesem-nsp0-binding-", dir="/tmp") as folder:
        directory = Path(folder)
        # These are interface proof files, never formal experiment artifacts.
        np.savez(str(directory / "carrier.npz"),
                 features=np.stack([np.asarray(d["token"], dtype=np.float32)
                                    for _, d in graph.nodes(data=True)]))
        payloads = {
            "graph": {"kind": "in_memory_probe_graph_reference",
                      "fingerprint": graph_fingerprint(graph), "nodes": len(graph),
                      "edges": graph.number_of_edges()},
            "folds": {"kind": "probe_partition", "parts": parts},
            "labels": {"kind": "probe_only", "not_a_training_dataset": True},
            "label_view": {"kind": "probe_only", "label_policy": "unchanged"},
            "feature_view": {"kind": "random_float32_carrier_probe",
                             "shape": [len(graph), model.in_size], "width": model.in_size},
        }
        references = {}
        for name, payload in payloads.items():
            path = directory / (name + ".json")
            path.write_text(json.dumps(payload, sort_keys=True), encoding="utf8")
            references[name] = _ref(path)
        references["feature_npz"] = _ref(directory / "carrier.npz")
        registration = support.model_support(model, parts)
        binding = checkpoint.build_binding(
            model, task_id="NS-P0-interface-probe", fold=0, seed=1,
            profile=model.dfg_profile, reducer=model.dfg_reducer,
            graph_ref=references["graph"], fold_ref=references["folds"],
            label_ref=references["labels"], initial_sha256=before, config=config,
            split=parts, support=registration,
            initialization_record={"kind": "fresh_probe_no_training", "optimizer_steps": 0})
        binding.update({k: references[k] for k in ("label_view", "feature_view", "feature_npz")})
        checkpoint.validate_binding(model, binding, check_files=True, deep=True)
        # A checksum mutation must still be rejected; only this disposable file changes.
        altered = Path(references["feature_view"]["path"])
        original = altered.read_bytes()
        altered.write_bytes(original + b" ")
        rejected = False
        try:
            checkpoint.validate_binding(model, binding, check_files=True, deep=False)
        except ValueError as exc:
            rejected = "Bound input changed: feature_view" in str(exc)
        finally:
            altered.write_bytes(original)
        assert rejected, "Changed temporary feature manifest was not rejected"
        result = dict(build_binding_passed=True, validate_binding_passed=True,
                      changed_feature_manifest_rejected=rejected,
                      temporary_files_sha256={k:v["sha256"] for k,v in references.items()},
                      check_files=True, temporary_files_removed_on_exit=True,
                      caveat="SHA/registration API proof; manifests are explicitly synthetic, not a sealed NodeSem plan.")
    assert tensor_digest(model.state_dict()) == before
    assert not directory.exists()
    return result


def _ab(graph, name, parts, config):
    before = graph_fingerprint(graph)
    observations = {}
    print("Carrier probe A: {} 512 -> 600".format(name), file=sys.stderr, flush=True)
    base, elapsed = _construct(graph, "node", "G3R")
    assert base.in_size == 512
    baseline_count = sum(p.numel() for p in base.parameters())
    observations["512"] = dict(construction_seconds=elapsed, input_width=base.in_size,
                               parameter_count=baseline_count, registration_passed=True)
    del base
    gc.collect()
    changed = _carry(graph)
    model, elapsed = _construct(changed, "node", "G3R")
    assert model.in_size == 600
    assert all(layer.in_features == 600 and layer.out_features == 128 for layer in model.adapt_ws)
    assert graph_fingerprint(graph) == before
    observed = [list(model.symmetrical_global_graph.nodes[t].data["inp"].shape)
                for t in model.node_types]
    observations["600"] = dict(construction_seconds=elapsed, input_width=model.in_size,
                               parameter_count=sum(p.numel() for p in model.parameters()),
                               registered_input_shapes=observed, registration_passed=True)
    observations["width_parameter_delta"] = observations["600"]["parameter_count"] - baseline_count
    expected = len(model.node_types) * (600 - 512) * 128
    assert observations["width_parameter_delta"] == expected
    print("Carrier probe B: adapter replacement + binding " + name, file=sys.stderr, flush=True)
    torch.manual_seed(617)
    model.adapt_ws = nn.ModuleList([nn.Linear(600, 128) for _ in model.ntypes_dict])
    assert len(model.adapt_ws) == len(model.ntypes_dict)
    validate_registration(model)
    runtime_model.validate_registration(model)
    binding = _temporary_binding(model, changed, parts, config)
    assert graph_fingerprint(graph) == before
    result = dict(name=name, graph_nodes=len(graph), graph_edges=graph.number_of_edges(),
                  graph_fingerprint=before, input_graph_unchanged=True,
                  constructor=observations,
                  replacement=dict(adapters=len(model.adapt_ws), input_width=600,
                                   output_width=128, runtime_registration_passed=True,
                                   binding=binding),
                  optimizer_steps=0, trained_checkpoint_loaded=False,
                  forward_executed=False)
    del model, changed
    gc.collect()
    return result


def _zero_layers():
    print("Carrier probe C: G0 zero-layer node/contract backward", file=sys.stderr, flush=True)
    base = _fixture(False)
    graph = _carry(base)
    before, base_before = graph_fingerprint(graph), graph_fingerprint(base)
    parts = {"inner_train": ["train.sol"], "inner_val": ["val.sol"], "outer_test": ["test.sol"]}
    results = {}
    for task in ("node", "contract"):
        model, seconds = _construct(graph, task, "G0", layers=0)
        assert model.num_layers == 0 and len(model.gcs) == 0
        state_before = tensor_digest(model.state_dict())
        registration = support.model_support(model, parts)
        supervision = DfgV2Supervision(model, task, parts["inner_train"])
        model.train()
        logits = supervision.forward(model)
        targets = supervision.targets(model, {"train.sol": 1})
        loss = F.cross_entropy(logits, targets)
        assert bool(torch.isfinite(logits).all()) and bool(torch.isfinite(loss))
        loss.backward()
        gradients = support.gradient_audit(model, registration)
        assert gradients["backbone_gradient_l1"] > 0
        assert gradients["classifier_gradient_l1"] > 0
        assert gradients["v2_training_support"] == 0 and not gradients["v2_relations"]
        assert all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in model.parameters())
        assert tensor_digest(model.state_dict()) == state_before
        assert graph_fingerprint(graph) == before and graph_fingerprint(base) == base_before
        # The frozen classifier's zero-layer algebra is checked independently.
        model.eval()
        with torch.no_grad():
            hidden = torch.zeros(model.total_nodes, model.hidden_size)
            for typ, rows in model.node_ids_dict.items():
                hidden[rows] = F.gelu(model.adapt_ws[model.ntypes_dict[typ]](
                    model.symmetrical_global_graph.nodes[typ].data["inp"]))
            expected = (model.classify(hidden)[supervision.mask] if task == "node" else
                        model.classify(torch.stack([hidden[model.node_ids_by_filename[f]].mean(0)
                                                   for f in supervision.files])))
            assert torch.equal(expected, supervision.forward(model))
        results[task] = dict(layers=0, input_width=600, construction_seconds=seconds,
                             logits_shape=list(logits.shape), loss=float(loss.detach()),
                             gradient_audit=gradients, forward_backward_passed=True,
                             parameters_unchanged=True, graph_unchanged=True,
                             explicit_zero_layer_formula_bitwise_equal=True,
                             optimizer_steps=0, state_sha256=state_before)
        del model
        gc.collect()
    return results


def _code_refs(root):
    wanted = {
        "scripts/DFG/dfg_v2/model.py": ("def _features", "def _construct", "model.in_size",
            "model.adapt_ws", "def validate_registration", "torch.equal(actual.cpu()"),
        "sco_models/model_hgt.py": ("    def forward(self):", "    def forward(self, batched_g_name",
            "F.gelu(self.adapt_ws"),
        "scripts/DFG/dfg_v2/benchmark_v2/runtime_model.py": ("def validate_registration",),
        "scripts/DFG/dfg_v2/benchmark_v2/checkpoint.py": ("def build_binding", "def validate_binding"),
        "scripts/DFG/dfg_v2/benchmark_v2/support.py": ("def gradient_audit", "def model_support"),
        "scripts/DFG/dfg_v2/benchmark_v2/spelling_features.py": ("def assemble",),
        "sco_models/graph_utils.py": ("def get_node_token",),
    }
    return [dict(path=relative, sha256=_sha(root/relative),
                 lines=[dict(line=i+1, text=line.strip()) for i,line in enumerate(
                     (root/relative).read_text(encoding="utf8").splitlines())
                        if any(token in line for token in tokens)])
            for relative,tokens in wanted.items()]


def run(repo_root=None):
    root = Path(repo_root or ROOT).resolve()
    torch.set_num_threads(2)
    rng = torch.get_rng_state()
    try:
        fixture = _fixture(True)
        parts = {"inner_train": ["train.sol"], "inner_val": ["val.sol"], "outer_test": ["test.sol"]}
        config = dict(hidden_size=128, layers=2, heads=8, layer_impl="shared_projection",
                      reducer="mean", node_feature="inside_token", device="cpu",
                      purpose="NS-P0 interface acceptance; no optimizer")
        with contextlib.redirect_stdout(sys.stderr):
            small = _ab(fixture, "synthetic", parts, config)
            plan_path = root/"scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json"
            plan = _json(plan_path)
            task = plan["tasks"]["reentrancy_node"]
            info = _json(_checked(task["prepared"]["0/1"]))
            graph_ref = info["profiles"]["G3R"]["graph"]
            assert graph_ref == task["profiles"]["G3R"]["graph"]
            original = read_graph(_checked(graph_ref))
            original_fingerprint = graph_fingerprint(original)
            anonymous = assemble(original, task["feature_view"])
            assert graph_fingerprint(original) == original_fingerprint
            real = _ab(anonymous, "reentrancy_node:G3R:N-anon-s", info["split"], config)
            assert graph_fingerprint(original) == original_fingerprint
            real.update(original_graph_ref=graph_ref, feature_view=task["feature_view"],
                        original_graph_fingerprint=original_fingerprint,
                        original_graph_unchanged=True,
                        original_hcg_nodes=sum(d["node_type"]!="env_source"
                                               for _,d in original.nodes(data=True)),
                        auxiliary_nodes=sum(d["node_type"]=="env_source"
                                            for _,d in original.nodes(data=True)))
            del original, anonymous
            gc.collect()
            zero = _zero_layers()
        return dict(passed=True, scope="NS-P0 section 2", device="cpu",
                    gpu_used=False, trained_checkpoints_loaded=False, optimizer_steps=0,
                    fit_calls=0, formal_artifacts_written=False,
                    synthetic=small, real=real, zero_layers=zero,
                    code_references=_code_refs(root),
                    limitation="Checks width-600 Linear replacement and zero-layer execution; a real NodeSemAdapter/spec implementation is still future NS-P4 work.")
    finally:
        torch.set_rng_state(rng)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(ROOT))
    args = parser.parse_args()
    print(json.dumps(run(args.repo_root), ensure_ascii=False, indent=2))
