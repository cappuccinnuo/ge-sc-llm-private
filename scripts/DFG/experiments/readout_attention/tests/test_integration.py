"""Two-epoch CPU integration on tiny synthetic graphs, never formal results."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
import torch
from scripts.DFG.experiments.common import tensor_digest, digest
from scripts.DFG.experiments.e23_pilot import training as old_training
from scripts.DFG.experiments.paper_protocol import NAME, VERSION as PV, FORWARD_SCOPE, SCORE_ROLE
from scripts.DFG.experiments.readout_attention import model, training, runtime, checkpoint, checks, prepare
from scripts.DFG.experiments.readout_attention import VERSION, PAIR_VERSION, READOUT
from scripts.DFG.experiments.readout_attention.tests.test_model import graph


def binding(candidate, variant, split):
    return dict(protocol=NAME, protocol_version=PV, forward_scope=FORWARD_SCOPE,
        score_role=SCORE_ROLE, experiment_version=VERSION, pair_version=PAIR_VERSION,
        initialization_version=model.INITIALIZATION_VERSION, adapter_version=model.ADAPTER_VERSION,
        task_id="reentrancy_author_contract", task="contract", variant=variant,
        split=split, registered_schema=model.validate_registration(candidate),
        forward_only_enhancement_relations=sorted(model.FORWARD_RELATIONS),
        readout=copy.deepcopy(READOUT), graph_labels_sha256=digest({"a.sol": 1, "b.sol": 0}),
        source_mean=dict(manifest_sha256="m" * 64, initial_sha256="i" * 64,
                         initial_state_sha256="s" * 64, receipt_sha256="r" * 64))


class ReadoutFitIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.split = dict(fold=0, train_files=["a.sol"], val_files=["b.sol"])
        cls.labels = {"a.sol": 1, "b.sol": 0}
        cls.config = dict(initial_lr=.0002, weight_decay=0., max_lr=.005,
            schedule_epochs=50, div_factor=25, final_div_factor=1, cycle_momentum=True,
            patience=7, delta=.001, maximum_training_epochs=2, mode="smoke")
        cls.cases = {}
        for variant in ("HCG", "HCG_DDG_GUARD"):
            torch.manual_seed(123)
            candidate = model.make_model("contract", graph(variant != "HCG"), graph_kind=variant)
            initial = copy.deepcopy(candidate.state_dict())
            parts = {phase: runtime.Supervision(candidate, "contract", cls.split[phase + "_files"])
                     for phase in ("train", "val")}
            support = runtime.graph_schema_and_support(candidate.nx_graph, cls.split)
            bind = binding(candidate, variant, cls.split)
            dest = cls.root / variant
            torch.manual_seed(445)
            result = training.FIT(candidate, parts, "contract", cls.labels, cls.config,
                dest, bind, candidate.original_graph_node_ids, support)
            cls.cases[variant] = dict(model=candidate, initial=initial, parts=parts,
                support=support, binding=bind, dest=dest, result=result)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        torch.set_num_threads(cls.previous_threads)

    def fresh(self, variant):
        return model.make_model("contract", graph(variant != "HCG"), graph_kind=variant)

    def test_frozen_fit_code_identity_and_no_global_patch(self):
        self.assertIs(training.FIT.__code__, old_training.FIT.__code__)
        self.assertIs(training._frozen_fit.__code__, old_training.fit.__code__)
        self.assertIsNot(old_training.FIT.__globals__["gradient_audit"], runtime.gradient_audit)
        self.assertIsNot(old_training.FIT.__globals__["save_checkpoint"], checkpoint.save_checkpoint)
        self.assertIs(training.FIT.__globals__["save_checkpoint"], checkpoint.save_checkpoint)

    def test_two_epochs_best_last_reload_and_separate_gradients(self):
        for variant, case in self.cases.items():
            result = case["result"]
            self.assertEqual(result["history_rows"], 2)
            self.assertEqual(result["checkpoint_roundtrip_exact"], {"best": True, "last": True})
            self.assertTrue(result["no_parameters_created_during_training_or_scoring"])
            self.assertEqual(result["score_role"], "cv_validation")
            for epoch in result["gradient_audit"]["epochs"]:
                self.assertGreater(epoch["hgt_gradient_l1"], 0.)
                self.assertGreater(epoch["readout"]["gradient_l1"], 0.)
                self.assertTrue(epoch["readout"]["connected"])
            rows = json.loads((case["dest"] / "cv_validation_predictions.json").read_text())
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["file"], rows[0]["target"]), ("b.sol", 0))
            for name in ("best", "last"):
                fresh = self.fresh(variant)
                obj = checkpoint.restore_checkpoint(case["dest"] / (name + ".pt"), fresh,
                    case["binding"], result["checkpoint_sha256"][name])
                self.assertEqual(obj["format"], checkpoint.FORMAT)
                self.assertEqual(obj["binding"]["readout"], READOUT)
                self.assertEqual(obj["binding"]["source_mean"], case["binding"]["source_mean"])
                fresh.eval()
                with torch.no_grad():
                    logits = fresh(["b.sol"])[0]
                checkpoint.restore_checkpoint(case["dest"] / (name + ".pt"), fresh,
                    case["binding"], result["checkpoint_sha256"][name])
                with torch.no_grad():
                    self.assertTrue(torch.equal(logits, fresh(["b.sol"])[0]))
                self.assertEqual(int(logits.argmax(1)[0]), rows[0][name])
                self.assertAlmostEqual(float(logits.softmax(1)[0, 1]),
                                       rows[0][name + "_positive_probability"], places=7)
                self.assertGreater(float(fresh.readout_vector.detach().abs().sum()), 0.)

    def test_training_replay_from_same_initial_and_seed_is_exact(self):
        case = self.cases["HCG"]
        candidate = self.fresh("HCG")
        candidate.load_state_dict(case["initial"], strict=True)
        parts = {phase: runtime.Supervision(candidate, "contract", self.split[phase + "_files"])
                 for phase in ("train", "val")}
        torch.manual_seed(445)
        replay = training.FIT(candidate, parts, "contract", self.labels, self.config,
            self.root / "replay", case["binding"], candidate.original_graph_node_ids, case["support"])
        for name in ("best", "last"):
            reference = torch.load(str(case["dest"] / (name + ".pt")), map_location="cpu")
            repeated = torch.load(str(self.root / "replay" / (name + ".pt")), map_location="cpu")
            self.assertEqual(reference["state_sha256"], repeated["state_sha256"])
        self.assertEqual(case["result"]["cv_validation"], replay["cv_validation"])
        self.assertEqual((case["dest"] / "history.jsonl").read_text(),
                         (self.root / "replay" / "history.jsonl").read_text())

    def test_graph_feature_node_label_schema_and_binding_corruption_rejected(self):
        case = self.cases["HCG_DDG_GUARD"]
        for change in ("feature", "node_label", "schema", "base_edge", "graph_label_binding",
                       "readout_binding", "source_mean_binding", "role"):
            candidate = self.fresh("HCG_DDG_GUARD")
            bind = copy.deepcopy(case["binding"])
            if change == "feature":
                typ = candidate.node_types[0]
                candidate.symmetrical_global_graph.nodes[typ].data["inp"][0, 0] += 1.
            elif change == "node_label":
                candidate.nx_graph.nodes[0]["node_info_vulnerabilities"] = None
            elif change == "schema":
                candidate.etypes_dict.pop(next(iter(candidate.etypes_dict)))
            elif change == "base_edge":
                candidate.nx_graph.remove_edge(0, 1, 0)
            elif change == "graph_label_binding": bind["graph_labels_sha256"] = "changed"
            elif change == "readout_binding": bind["readout"]["normalization"] = "global"
            elif change == "source_mean_binding": bind["source_mean"]["initial_sha256"] = "changed"
            else: bind["score_role"] = "independent_test"
            with self.subTest(change=change), self.assertRaises((ValueError, AssertionError)):
                checkpoint.restore_checkpoint(case["dest"] / "best.pt", candidate, bind,
                    case["result"]["checkpoint_sha256"]["best"])

    def test_readout_gradient_cannot_hide_disconnected_hgt_or_reverse(self):
        candidate = self.fresh("HCG_DDG_GUARD")
        candidate.eval()
        torch.nn.functional.cross_entropy(candidate(["a.sol"])[0], torch.tensor([1])).backward()
        support = self.cases["HCG_DDG_GUARD"]["support"]
        audit = runtime.gradient_audit(candidate, support)
        self.assertGreater(audit["hgt_gradient_l1"], 0.)
        saved = {name: param.grad for name, param in candidate.named_parameters()}
        for name, param in candidate.named_parameters():
            if name.startswith(("gcs.", "adapt_ws.")): param.grad = None
        with self.assertRaises(AssertionError):
            runtime.gradient_audit(candidate, support)
        for name, param in candidate.named_parameters(): param.grad = saved[name]
        candidate.readout_vector.grad = None
        with self.assertRaises(AssertionError):
            runtime.gradient_audit(candidate, support)

    def source_fixture(self):
        state = {key: value.detach().clone() for key, value in self.cases["HCG"]["initial"].items()
                 if key != "readout_vector"}
        state_hash = tensor_digest(state)
        info = dict(task_id="reentrancy_author_contract", fold=0, fit_seed=445,
            graphs={"HCG": dict(sha256="graph")}, initialization_audit_sha256="pairing",
            initialization={"HCG": dict(state_sha256=state_hash)})
        plan = dict(pair_version="historical-mean-pair")
        record = dict(kind="untrained_initial", optimizer_steps=0, task_id=info["task_id"],
            fold=0, variant="HCG", fit_seed=445, pair_version=plan["pair_version"],
            graph_sha256="graph", pairing_sha256="pairing", state_dict=state, state_sha256=state_hash)
        return record, info, plan

    def test_historical_untrained_provenance_rejects_all_identity_drift(self):
        record, info, plan = self.source_fixture()
        prepare.validate_source_record(record, info, "HCG", plan)
        changes = dict(kind="best", optimizer_steps=1, task_id="access_control_author_contract",
            fold=1, variant="HCG_DDG_GUARD", fit_seed=446, pair_version="other",
            graph_sha256="other", pairing_sha256="other", state_sha256="other")
        for key, value in changes.items():
            bad = copy.deepcopy(record); bad[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                prepare.validate_source_record(bad, info, "HCG", plan)
        bad = copy.deepcopy(record); bad["state_dict"]["classify.bias"][0] += 1.
        with self.assertRaises(ValueError): prepare.validate_source_record(bad, info, "HCG", plan)

    def test_attention_untrained_identity_requires_zero_and_exact_readout(self):
        record, info, _ = self.source_fixture()
        record["pair_version"] = PAIR_VERSION
        record["readout"] = copy.deepcopy(READOUT)
        record["state_dict"]["readout_vector"] = torch.zeros(128)
        info["initialization"]["HCG"]["state_sha256"] = tensor_digest(record["state_dict"])
        record["state_sha256"] = info["initialization"]["HCG"]["state_sha256"]
        checks.check_initial(record, info, "HCG")
        bad = copy.deepcopy(record); bad["readout"]["initialization"] = "random"
        with self.assertRaises(ValueError): checks.check_initial(bad, info, "HCG")
        bad = copy.deepcopy(record); bad["state_dict"]["readout_vector"][0] = 1.
        updated_info = copy.deepcopy(info)
        updated_info["initialization"]["HCG"]["state_sha256"] = tensor_digest(bad["state_dict"])
        with self.assertRaises(ValueError): checks.check_initial(bad, updated_info, "HCG")


if __name__ == "__main__":
    unittest.main()
