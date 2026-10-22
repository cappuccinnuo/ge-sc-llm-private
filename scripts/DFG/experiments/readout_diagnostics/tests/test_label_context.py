"""Corruption and population-conservation checks for frozen label diagnostics."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.DFG.experiments.readout_diagnostics import label_context as lc


def sample():
    rows, evidence, reviewed_files = [], {}, {}
    for variant in lc.VARIANTS:
        for number, filename, target, predicted in (
                (1, "a.sol", 0, 1), (2, "b.sol", 1, 0), (3, "c.sol", 0, 1)):
            rows.append(dict(task_id="reentrancy_author_node", cohort="reentrancy_author",
                             source_sha256="a" * 64, file=filename, original_graph_node_id=str(number),
                             model_node_id=str(number), node_type="expression_statement", fold=0,
                             variant=variant, target=target, score_role="cv_validation",
                             best=predicted, last=target,
                             best_positive_probability=0.9 if predicted else 0.1,
                             last_positive_probability=0.9 if target else 0.1))
    for row, public in ((rows[0], 0), (rows[1], 0)):
        key = lc.identity(row)
        evidence[key] = dict(author_label=row["target"], public_endpoint_label=public,
                             node_type=row["node_type"], evidence_file="review.json")
        reviewed_files[key[:3]] = 1
    return rows, evidence, reviewed_files


class LabelContextTests(unittest.TestCase):
    def test_strata_keep_unreviewed_separate_and_preserve_predictions(self):
        rows, evidence, files = sample()
        before = copy.deepcopy(rows)
        annotated = lc.stratify(rows, evidence, files)
        self.assertEqual(rows, before)
        self.assertEqual([row["review_stratum"] for row in annotated[:3]], list(lc.STRATA))
        self.assertEqual(annotated[2]["public_endpoint_label"], "")
        self.assertEqual(annotated[1]["target"], 1)
        self.assertEqual(annotated[1]["public_endpoint_label"], 0)
        aggregate, per_file = lc.summarize(annotated)
        for variant in lc.VARIANTS:
            best = {row["review_stratum"]: row for row in aggregate
                    if row["variant"] == variant and row["checkpoint"] == "best"}
            self.assertEqual(best["REFERENCE_AGREED"]["false_positive"], 1)
            self.assertEqual(best["DISPUTED"]["false_negative"], 1)
            self.assertEqual(best["UNREVIEWED"]["false_positive"], 1)
            self.assertEqual(best["ALL"]["nodes"], 3)
            self.assertEqual(best["ALL"]["errors"], 3)
            self.assertEqual(sum(best[stratum]["errors"] for stratum in lc.STRATA), 3)
        self.assertTrue(all(row["errors"] == 0 for row in aggregate if row["checkpoint"] == "last"))
        self.assertEqual(len(per_file), 3 * 3 * 2 * 4)

    def test_duplicate_prediction_rejected_even_across_folds(self):
        rows, evidence, files = sample()
        duplicate = dict(rows[0], fold=1)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            lc.stratify(rows + [duplicate], evidence, files)

    def test_missing_variant_node_rejected(self):
        rows, evidence, files = sample()
        with self.assertRaisesRegex(ValueError, "Variant node population"):
            lc.stratify(rows[:-1], evidence, files)

    def test_frozen_author_target_mismatch_rejected(self):
        rows, evidence, files = sample()
        evidence[lc.identity(rows[0])]["author_label"] = 1
        with self.assertRaisesRegex(ValueError, "does not equal reviewed author"):
            lc.stratify(rows, evidence, files)

    def test_unmatched_review_id_rejected(self):
        rows, evidence, files = sample()
        original_key = lc.identity(rows[0])
        evidence[original_key[:-1] + ("999",)] = evidence.pop(original_key)
        with self.assertRaisesRegex(ValueError, "Unmatched reviewed"):
            lc.stratify(rows, evidence, files)

    def test_review_source_sha_mismatch_rejected(self):
        rows, evidence, files = sample()
        original_key = lc.identity(rows[0])
        altered = original_key[:2] + ("b" * 64, original_key[3])
        evidence[altered] = evidence.pop(original_key)
        with self.assertRaisesRegex(ValueError, "Unmatched reviewed"):
            lc.stratify(rows, evidence, files)

    def test_partial_review_coverage_is_not_silently_unreviewed(self):
        rows, evidence, files = sample()
        evidence.pop(lc.identity(rows[0]))
        with self.assertRaisesRegex(ValueError, "Incomplete reviewed file evidence"):
            lc.stratify(rows, evidence, files)

    def test_variant_fold_or_type_mismatch_rejected(self):
        rows, evidence, files = sample()
        rows[3]["fold"] = 1
        with self.assertRaisesRegex(ValueError, "target/fold/type"):
            lc.stratify(rows, evidence, files)

    def test_invalid_probabilities_and_class_drift_rejected(self):
        rows, _, _ = sample()
        for value in (float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Invalid probability"):
                lc.normalize_prediction(dict(rows[0], best_positive_probability=value))
        with self.assertRaisesRegex(ValueError, "prediction/probability mismatch"):
            lc.normalize_prediction(dict(rows[0], best_positive_probability=0.5))

    def test_identity_contains_cohort_and_source(self):
        rows, _, _ = sample()
        base = rows[0]
        alternate = dict(base, cohort="access_control_author", task_id="access_control_author_node")
        self.assertNotEqual(lc.identity(base), lc.identity(alternate))
        self.assertNotEqual(lc.identity(base), lc.identity(dict(base, source_sha256="b" * 64)))

    def test_hash_binding_and_input_drift_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text('{"label": 0}', encoding="utf8")
            inputs = lc.Inputs()
            inputs.read(path, lc.sha256(path))
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                lc.Inputs().read(path, "0" * 64)
            path.write_text('{"label": 1}', encoding="utf8")
            with self.assertRaisesRegex(ValueError, "Input changed"):
                inputs.verify_unchanged()

    def test_exact_hard_file_counts_and_corruption(self):
        per_file = []
        for (cohort, filename), (nodes, errors, disputed) in lc.HARD_COUNTS.items():
            for variant in lc.VARIANTS:
                base = dict(cohort=cohort, file=filename, variant=variant, checkpoint="best")
                per_file.append(dict(base, review_stratum="ALL", nodes=nodes, errors=errors))
                per_file.append(dict(base, review_stratum="DISPUTED", nodes=0, errors=disputed))
        self.assertEqual(len(lc.verify_hard_counts(per_file)), 9)
        per_file[1]["errors"] += 1
        with self.assertRaisesRegex(ValueError, "Hard-file count mismatch"):
            lc.verify_hard_counts(per_file)

    def test_csv_writer_never_overwrites_existing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.csv"
            lc.write_csv(path, [dict(value=1)])
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                lc.write_csv(path, [dict(value=2)])
            self.assertEqual(path.read_bytes(), original)

    def test_duplicate_evidence_detected_before_dictionary_collapse(self):
        duplicate = [dict(node_id=1), dict(node_id="1")]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            lc.index_unique(duplicate, lambda row: str(row["node_id"]), "review")

    def test_frozen_export_corruption_rejected_with_sealed_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def write(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf8")
                return lc.sha256(path)
            source = root / "a.sol"
            source.write_text("contract Example {}", encoding="utf8")
            source_sha = lc.sha256(source)
            prepared = root / "prepared.json"
            prepared_sha = write(prepared, {"sources": {"a.sol": {"path": str(source), "sha256": source_sha}}})
            base, guard = root / "base", root / "guard"
            csv_rows = []
            for batch, variants in ((base, lc.VARIANTS[:2]), (guard, lc.VARIANTS[2:])):
                task = dict(task_id="reentrancy_author_node", cohort="reentrancy_author", fold=0,
                            source_prepared_manifest=str(prepared), source_prepared_manifest_sha256=prepared_sha,
                            split={"val_files": ["a.sol"], "fold": 0},
                            graphs={v: {"sha256": "b"*64, "node_attributes_sha256": "c"*64} for v in variants})
                task_sha = write(batch / "task.json", task)
                plan = {"tasks": [{"task_id": task["task_id"], "fold": 0,
                                  "manifest": str(batch / "task.json"), "sha256": task_sha}]}
                if batch == guard:
                    plan.update(source_batch=str(base), source_plan_sha256=lc.sha256(base / "plan.json"))
                write(batch / "plan.seal.json", {"sha256": write(batch / "plan.json", plan)})
                for variant in variants:
                    folder = batch / "runs/reentrancy_author_node/fold_0" / variant / "attempt_001"
                    binding = dict(plan_sha256=lc.digest(plan), task_id=task["task_id"], variant=variant,
                                   cohort=task["cohort"], split=task["split"],
                                   graph_sha256="b"*64, node_attributes_sha256="c"*64)
                    prediction = dict(file="a.sol", original_graph_node_id=1, model_node_id=1,
                                      node_type="expression_statement", target=0, best=0, last=0,
                                      best_positive_probability=0.1, last_positive_probability=0.1,
                                      score_role="cv_validation", graph_stored_source_lines=[[1]],
                                      graph_label_anchor="anchor")
                    artifacts = {"binding.json": write(folder / "binding.json", binding),
                                 "cv_validation_predictions.json": write(folder / "cv_validation_predictions.json", [prediction])}
                    write(folder / "receipt.json", dict(status="complete", task_id=task["task_id"], fold=0,
                          variant=variant, plan_sha256=lc.digest(plan), binding_sha256=lc.digest(binding), artifacts=artifacts))
                    csv_rows.append(dict(prediction, graph_stored_source_lines="[[1]]", variant=variant,
                                         fold=0, cohort=task["cohort"], task_id=task["task_id"], source_sha256=source_sha))
            path = guard / "oof_predictions.csv"
            lc.write_csv(path, csv_rows)
            self.assertEqual(len(lc.load_frozen_predictions(guard, lc.Inputs())[0]), 3)
            csv_rows[0]["target"] = 1
            with path.open("w", newline="", encoding="utf8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]))
                writer.writeheader()
                writer.writerows(csv_rows)
            with self.assertRaisesRegex(ValueError, "Frozen export mismatch: target"):
                lc.load_frozen_predictions(guard, lc.Inputs())
            receipt_path = base / "runs/reentrancy_author_node/fold_0/HCG/attempt_001/receipt.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["binding_sha256"] = "0"*64
            write(receipt_path, receipt)
            with self.assertRaisesRegex(ValueError, "Binding digest mismatch"):
                lc.load_frozen_predictions(guard, lc.Inputs())


if __name__ == "__main__":
    unittest.main()
