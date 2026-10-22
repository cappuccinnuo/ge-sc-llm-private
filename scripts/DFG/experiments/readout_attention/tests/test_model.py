"""Synthetic HCG interface tests; no training or Solidity compiler claim."""
import copy
import unittest
import networkx as nx
import numpy as np
import torch
from torch import nn
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.experiments.e23_pilot import model as old
from scripts.DFG.experiments.guard_extension import model as guard
from scripts.DFG.experiments.readout_attention import model as candidate
from sco_models.model_hgt import HGTLayer


def graph(enhanced=False):
    value = nx.MultiDiGraph()
    rng = np.random.RandomState(43)
    for filename, size in (("a.sol", 3), ("b.sol", 4)):
        for i in range(size):
            value.add_node(filename + str(i), source_file=filename,
                           node_type="expression" if i % 2 else "declaration",
                           token=rng.normal(size=512).astype(np.float32),
                           node_info_vulnerabilities=None if i % 2 else [{"category": "fixture"}],
                           node_source_code_lines=[i + 1], label="fixture")
        for i in range(size - 1):
            value.add_edge(filename + str(i), filename + str(i + 1), edge_type="next")
        if enhanced:
            value.add_edge(filename + "0", filename + "2", edge_type="DATA_DEF_USE")
            value.add_edge(filename + "1", filename + "2", edge_type="STATE_DEF_USE")
            value.add_edge(filename + "0", filename + "1", edge_type="CONTROL_DEPENDENCE")
    return value


class ReadoutModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.previous_threads)

    def models(self, enhanced=False):
        g = graph(enhanced)
        torch.manual_seed(923)
        original = (guard if enhanced else old).make_model("contract", g)
        expected_rng = torch.random.get_rng_state().clone()
        torch.manual_seed(923)
        attention = candidate.make_model("contract", g)
        self.assertTrue(torch.equal(expected_rng, torch.random.get_rng_state()))
        original.eval(); attention.eval()
        return original, attention

    def test_zero_vector_math_equivalence_and_gradients(self):
        hidden = torch.tensor([[1., 2.], [3., -4.], [-2., 1.]], requires_grad=True)
        vector = torch.zeros(2, requires_grad=True)
        pooled, alpha = candidate.attention_pool(hidden, vector)
        self.assertTrue(torch.allclose(pooled, hidden.mean(0), atol=1e-7, rtol=1e-6))
        self.assertTrue(torch.allclose(alpha, torch.full((3,), 1. / 3)))
        pooled[0].backward()
        self.assertGreater(float(vector.grad.abs().sum()), 0.)
        self.assertGreater(float(hidden.grad.abs().sum()), 0.)

    def test_nonzero_weights_normalized_and_analytic(self):
        hidden = torch.tensor([[1., 0.], [0., 1.]])
        vector = torch.tensor([2., -2.])
        pooled, alpha = candidate.attention_pool(hidden, vector)
        self.assertAlmostEqual(float(alpha.sum()), 1., places=6)
        self.assertTrue(torch.allclose(alpha, torch.softmax(torch.tensor([2., -2.]), 0)))
        self.assertTrue(torch.equal(pooled, alpha))

    def test_singleton_gradient_may_correctly_be_zero(self):
        vector = torch.zeros(2, requires_grad=True)
        hidden = torch.tensor([[2., 4.]], requires_grad=True)
        pooled, alpha = candidate.attention_pool(hidden, vector)
        pooled.sum().backward()
        self.assertTrue(torch.equal(alpha, torch.ones(1)))
        self.assertTrue(torch.equal(vector.grad, torch.zeros(2)))
        self.assertTrue(torch.equal(hidden.grad, torch.ones_like(hidden)))

    def test_invalid_pool_inputs_rejected(self):
        for hidden, vector in ((torch.zeros(0, 2), torch.zeros(2)),
                               (torch.zeros(3, 2), torch.zeros(3)),
                               (torch.zeros(3, 2), torch.zeros(1, 2))):
            with self.assertRaises(ValueError):
                candidate.attention_pool(hidden, vector)

    def test_original_hcg_forward_alignment_and_rng(self):
        self.assert_mean_alignment(False)

    def test_enhanced_graph_forward_alignment_and_rng(self):
        self.assert_mean_alignment(True)

    def assert_mean_alignment(self, enhanced):
        original, attention = self.models(enhanced)
        self.assertEqual(attention.etypes_dict, original.etypes_dict)
        self.assertEqual(attention.ntypes_dict, original.ntypes_dict)
        self.assertEqual(attention.node_ids_dict, original.node_ids_dict)
        self.assertTrue(all(type(x) is HGTLayer for x in attention.gcs))
        old_state, new_state = original.state_dict(), attention.state_dict()
        self.assertEqual(set(new_state) - set(old_state), {"readout_vector"})
        self.assertTrue(all(torch.equal(new_state[k], old_state[k]) for k in old_state))
        self.assertEqual(sum(p.numel() for p in attention.parameters()) -
                         sum(p.numel() for p in original.parameters()), 128)
        with torch.no_grad():
            before = original(["a.sol", "b.sol"])
            after = attention(["a.sol", "b.sol"])
        for a, b in zip(before, after):
            self.assertTrue(torch.allclose(a, b, rtol=1e-5, atol=1e-6))
        self.assertEqual(attention._forward_hooks, {})
        self.assertEqual(attention._forward_pre_hooks, {})

    def test_graph_nodes_edges_features_labels_are_unchanged(self):
        g = graph(True)
        before = fingerprint(g)
        model = candidate.make_model("contract", g)
        self.assertEqual(before, fingerprint(g))
        self.assertEqual(list(g), model.original_graph_node_ids)
        candidate.validate_registration(model)
        self.assertTrue(any(c[1] == "next" for c in model.etypes_dict))
        self.assertTrue(any(c[1] == "CONTROL_DEPENDENCE" for c in model.etypes_dict))

    def test_real_hgt_and_attention_gradients_from_file_supervision(self):
        _, attention = self.models(True)
        logits, _ = attention(["a.sol"])
        nn.functional.cross_entropy(logits, torch.tensor([1])).backward()
        self.assertGreater(float(attention.readout_vector.grad.abs().sum()), 0.)
        self.assertGreater(sum(float(p.grad.abs().sum()) for p in attention.gcs.parameters()
                               if p.grad is not None), 0.)
        self.assertGreater(sum(float(p.grad.abs().sum()) for p in attention.adapt_ws.parameters()
                               if p.grad is not None), 0.)
        self.assertGreater(float(attention.classify.weight.grad.abs().sum()), 0.)
        self.assertTrue(all(not attention.symmetrical_global_graph.nodes[t].data["inp"].requires_grad
                            for t in attention.ntypes_dict))

    def test_file_normalization_isolation_and_order(self):
        _, model = self.models(True)
        with torch.no_grad():
            model.readout_vector.copy_(torch.linspace(-1., 1., 128))
            first = model(["a.sol"])
            pair = model(["a.sol", "b.sol"])
            reverse = model(["b.sol", "a.sol"])
        for component in (0, 1):
            self.assertTrue(torch.allclose(first[component][0], pair[component][0], atol=1e-6, rtol=1e-5))
            self.assertTrue(torch.allclose(pair[component], reverse[component].flip(0), atol=1e-6, rtol=1e-5))
        for typ in model.ntypes_dict:
            ids = model.node_ids_dict[typ]
            inp = model.symmetrical_global_graph.nodes[typ].data["inp"]
            for row, global_id in enumerate(ids):
                if model.nx_graph.nodes[global_id]["source_file"] == "b.sol":
                    inp[row] += 100.
        with torch.no_grad():
            after = model(["a.sol"])
        self.assertTrue(torch.equal(first[0], after[0]))
        self.assertTrue(torch.equal(first[1], after[1]))

    def test_no_label_input_and_no_scoring_parameter_creation(self):
        _, model = self.models(True)
        before = {name: id(param) for name, param in model.named_parameters()}
        with torch.no_grad():
            output = model(["a.sol", "b.sol"])[0]
        for _, attrs in model.nx_graph.nodes(data=True):
            attrs["node_info_vulnerabilities"] = [{"category": "changed"}]
        with torch.no_grad():
            after = model(["a.sol", "b.sol"])[0]
        self.assertTrue(torch.equal(output, after))
        self.assertEqual(before, {name: id(param) for name, param in model.named_parameters()})

    def test_parameter_attachment_does_not_consume_rng(self):
        model = guard.make_model("contract", graph(False))
        before = torch.random.get_rng_state().clone()
        candidate.register_attention_parameter(model)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        with self.assertRaises(ValueError):
            candidate.register_attention_parameter(model)

    def test_strict_checkpoint_rejects_missing_or_extra_readout_parameter(self):
        original, attention = self.models(False)
        with self.assertRaises(RuntimeError):
            attention.load_state_dict(original.state_dict(), strict=True)
        with self.assertRaises(RuntimeError):
            original.load_state_dict(attention.state_dict(), strict=True)
        bad = dict(attention.state_dict())
        bad["readout_vector"] = torch.zeros(127)
        with self.assertRaises(RuntimeError):
            attention.load_state_dict(bad, strict=True)

    def test_explicit_mean_transfer_preserves_shared_values_and_rng(self):
        original, attention = self.models(True)
        with torch.no_grad():
            attention.readout_vector.fill_(9.)
        before = torch.random.get_rng_state().clone()
        candidate.load_mean_state(attention, original.state_dict())
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        self.assertTrue(torch.equal(attention.readout_vector, torch.zeros(128)))
        self.assertTrue(all(torch.equal(attention.state_dict()[k], value)
                            for k, value in original.state_dict().items()))

    def test_mean_transfer_rejects_corrupt_state_before_mutation(self):
        original, attention = self.models(False)
        for kind in ("missing", "extra", "shape", "dtype", "nan"):
            state = copy.deepcopy(original.state_dict())
            if kind == "missing": state.pop("classify.bias")
            elif kind == "extra": state["fake"] = torch.zeros(1)
            elif kind == "shape": state["classify.bias"] = torch.zeros(3)
            elif kind == "dtype": state["classify.bias"] = state["classify.bias"].double()
            else: state["classify.bias"][0] = float("nan")
            before = copy.deepcopy(attention.state_dict())
            with self.assertRaises(ValueError):
                candidate.load_mean_state(attention, state)
            self.assertTrue(all(torch.equal(attention.state_dict()[k], v) for k, v in before.items()))

    def test_task_and_graph_kind_restrictions(self):
        with self.assertRaises(ValueError):
            candidate.make_model("node", graph())
        with self.assertRaises(ValueError):
            candidate.make_model("contract", graph(), graph_kind="HCG_DDG_GUARD")
        with self.assertRaises(ValueError):
            candidate.make_model("contract", graph(True), graph_kind="HCG")
        model = candidate.make_model("contract", graph())
        self.assertFalse(any(c[1] in guard.FORWARD_RELATIONS for c in model.etypes_dict))


if __name__ == "__main__":
    unittest.main()
