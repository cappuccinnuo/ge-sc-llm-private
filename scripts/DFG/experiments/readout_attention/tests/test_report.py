"""Regression checks for complete, identity-aligned contract 2x2 summaries."""
import copy
import json
import math
import unittest
from scripts.DFG.experiments.common import metrics
from scripts.DFG.experiments.readout_attention.report import (
    CELLS, build_tables, assert_comparable, _validate_fit)

TASK = "reentrancy_author_contract"


def fixtures():
    all_files = ["f%d_%d.sol" % (fold, label) for fold in range(5) for label in (0, 1)]
    fits = []
    for fold in range(5):
        files = ["f%d_%d.sol" % (fold, label) for label in (0, 1)]
        for graph, readout in CELLS:
            info = dict(task_id=TASK, task="contract", cohort="reentrancy_author", fold=fold,
                fit_seed=1000 + fold, labels_sha256="labels", feature={"sha": "features"},
                source_prepared_manifest_sha256="sources", source_splits_sha256="splits",
                graphs={g: {"sha256": g} for g, _ in CELLS},
                config={"max_lr": .01, "patience": 7},
                split=dict(train_files=[f for f in all_files if f not in files], val_files=files))
            pred = []
            for label, filename in enumerate(files):
                # Only plain-HCG attention loses the positive example in fold 0.
                best = 0 if (graph, readout, fold, label) == ("HCG", "attention", 0, 1) else label
                last = 1 if label == 0 and readout == "attention" else label
                pred.append(dict(file=filename, target=label, best=best, last=last,
                    best_positive_probability=.8 if best else .2,
                    last_positive_probability=.7 if last else .3, score_role="cv_validation"))
            result = dict(status="complete", score_role="cv_validation", history_rows=2,
                best_epoch=0, last_epoch=1, checkpoint_roundtrip_exact={"best": True, "last": True},
                cv_validation={ck: metrics([r["target"] for r in pred], [r[ck] for r in pred])
                               for ck in ("best", "last")},
                parameters=100, wall_seconds_monotonic=1.2,
                resource=dict(peak_allocated_bytes=1048576, peak_reserved_bytes=2097152,
                    card=dict(minimum_whole_card_free_mib=200)),
                gradient_audit=dict(epochs=[dict(epoch=0, enhancement_relations=[])]))
            if readout == "attention":
                result["gradient_audit"]["epochs"][0]["readout"] = {"gradient_l1": .5}
            fits.append(dict(job=dict(task_id=TASK, fold=fold, variant=graph), readout=readout,
                info=info, result=result, predictions=pred, folder="/synthetic/fit",
                expected={(r["file"], json.dumps(None)): r["target"] for r in pred},
                sources={f: {"sha256": "sha-" + f} for f in files}))
    return fits, {TASK: all_files}


class ReportTests(unittest.TestCase):
    def test_complete_matrix_and_independent_metric_counts(self):
        fits, files = fixtures()
        tables = build_tables(fits, (TASK,), files)
        self.assertEqual(len(tables["fold_results.csv"]), 40)
        self.assertEqual(len(tables["best_fold_results.csv"]), 20)
        self.assertEqual(len(tables["last_fold_results.csv"]), 20)
        self.assertEqual(len(tables["oof_predictions.csv"]), 40)
        self.assertEqual(len(tables["resources.csv"]), 20)
        self.assertEqual(len(tables["readout_gradients.csv"]), 10)
        self.assertEqual(len(tables["pooled_oof.csv"]), 8)
        self.assertTrue(all(r["n"] == 10 for r in tables["pooled_oof.csv"]))
        self.assertTrue(all(r["folds"] == 5 for r in tables["fold_statistics.csv"]))

    def test_interaction_sign_and_best_last_separation(self):
        fits, files = fixtures()
        tables = build_tables(fits, (TASK,), files)
        row = next(r for r in tables["interaction_deltas.csv"] if r["fold"] == 0 and r["checkpoint"] == "best")
        self.assertAlmostEqual(row["buggy_f1_delta_pp"], 100.)
        summary = next(r for r in tables["interaction_statistics.csv"] if r["checkpoint"] == "best")
        self.assertAlmostEqual(summary["buggy_f1_delta_pp_mean"], 20.)
        self.assertAlmostEqual(summary["buggy_f1_delta_pp_sample_std"], math.sqrt(2000.))
        self.assertEqual((summary["buggy_f1_improved"], summary["buggy_f1_tied"], summary["buggy_f1_declined"]), (1, 4, 0))
        last = next(r for r in tables["interaction_statistics.csv"] if r["checkpoint"] == "last")
        self.assertAlmostEqual(last["buggy_f1_delta_pp_mean"], 0.)

    def test_prediction_changes_align_identity_not_csv_order(self):
        fits, files = fixtures()
        for fit in fits[::2]:
            fit["predictions"].reverse()
        tables = build_tables(fits, (TASK,), files)
        changes = [r for r in tables["prediction_changes.csv"]
                   if r["fold"] == 0 and r["checkpoint"] == "best"
                   and r["contrast"] == "HCG:attention-HCG:mean"]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["transition"], "regressed")
        self.assertEqual(changes[0]["source_sha256"], "sha-f0_1.sol")

    def test_missing_or_duplicate_fit_rejected(self):
        fits, files = fixtures()
        for bad in (fits[:-1], fits + [fits[0]]):
            with self.assertRaises(ValueError):
                build_tables(bad, (TASK,), files)

    def test_mixed_score_role_rejected(self):
        fits, files = fixtures()
        fits[0]["predictions"][0]["score_role"] = "outer_test"
        with self.assertRaisesRegex(ValueError, "scoring role"):
            build_tables(fits, (TASK,), files)

    def test_wrong_target_rejected(self):
        fits, files = fixtures()
        fits[0]["predictions"][0]["target"] = 1
        with self.assertRaisesRegex(ValueError, "population/label"):
            build_tables(fits, (TASK,), files)

    def test_metric_summary_cannot_override_predictions(self):
        fits, files = fixtures()
        fits[0]["result"]["cv_validation"]["best"]["buggy_f1"] = 99.
        with self.assertRaisesRegex(ValueError, "Independent metric"):
            build_tables(fits, (TASK,), files)

    def test_nonfinite_probability_rejected(self):
        fits, files = fixtures()
        fits[0]["predictions"][0]["best_positive_probability"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Invalid prediction"):
            build_tables(fits, (TASK,), files)

    def test_source_sha_mismatch_rejected(self):
        fits, files = fixtures()
        fits[1]["sources"]["f0_0.sol"]["sha256"] = "different-source"
        with self.assertRaisesRegex(ValueError, "source identity"):
            build_tables(fits, (TASK,), files)

    def test_wrong_oof_population_rejected(self):
        fits, files = fixtures()
        files[TASK].append("missing.sol")
        with self.assertRaisesRegex(ValueError, "OOF file coverage"):
            build_tables(fits, (TASK,), files)

    def test_original_config_preserved_readout_metadata_allowed(self):
        fits, _ = fixtures()
        info = fits[0]["info"]
        updated = copy.deepcopy(info)
        updated["config"]["readout"] = "attention"
        assert_comparable(updated, info, "HCG")
        updated["config"]["max_lr"] = .001
        with self.assertRaisesRegex(ValueError, "configuration"):
            assert_comparable(updated, info, "HCG")

    def test_original_graph_features_labels_split_seed_required(self):
        fits, _ = fixtures()
        info = fits[0]["info"]
        for field in ("fit_seed", "labels_sha256", "feature", "split"):
            changed = copy.deepcopy(info)
            changed[field] = "changed"
            with self.assertRaisesRegex(ValueError, "Historical comparison"):
                assert_comparable(changed, info, "HCG")
        changed = copy.deepcopy(info)
        changed["graphs"]["HCG"]["sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "Historical graph"):
            assert_comparable(changed, info, "HCG")

    def test_invalid_reload_or_epoch_rejected(self):
        fits, _ = fixtures()
        fit = fits[0]
        fit["result"]["checkpoint_roundtrip_exact"]["last"] = False
        with self.assertRaisesRegex(ValueError, "reload"):
            _validate_fit(fit)
        fit["result"]["checkpoint_roundtrip_exact"]["last"] = True
        fit["result"]["best_epoch"] = 2
        with self.assertRaisesRegex(ValueError, "epoch"):
            _validate_fit(fit)

    def test_nonfinite_or_drifting_relation_audit_rejected(self):
        fits, files = fixtures()
        audit = fits[0]["result"]["gradient_audit"]["epochs"]
        relation = dict(canonical=["a", "DATA_DEF_USE", "b"],
                        train_edges=1, val_edges=0, message_gradient_l1=float("nan"))
        audit[0]["enhancement_relations"] = [relation]
        with self.assertRaisesRegex(ValueError, "Nonfinite relation"):
            build_tables(fits, (TASK,), files)
        relation["message_gradient_l1"] = 0.
        audit.append(dict(epoch=1, enhancement_relations=[dict(relation, train_edges=2)]))
        with self.assertRaisesRegex(ValueError, "support changed"):
            build_tables(fits, (TASK,), files)


if __name__ == "__main__":
    unittest.main()
