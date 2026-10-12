"""Regression tests for loss selection and patience; no full graph training.

Callers save on ``improved``. These tests exercise that public protocol while
keeping absolute best loss separate from the significant-improvement anchor.
"""

import math
import os
import tempfile
import unittest

import torch

from sco_models.tools import EarlyStopping


class EarlyStoppingTests(unittest.TestCase):
    def test_small_improvements_save_best_without_resetting_patience(self):
        stopper = EarlyStopping(patience=7, delta=0.001)
        stopper(1.0)
        self.assertTrue(stopper.improved)
        self.assertEqual(stopper.counter, 0)

        stopper(0.9995)
        self.assertTrue(stopper.improved)
        self.assertAlmostEqual(stopper.best_val_loss, 0.9995)
        self.assertEqual(stopper.best_score, -1.0)
        self.assertEqual(stopper.counter, 1)

        # Cumulative improvement is measured against the significant anchor.
        stopper(0.9988)
        self.assertTrue(stopper.improved)
        self.assertAlmostEqual(stopper.best_val_loss, 0.9988)
        self.assertAlmostEqual(stopper.best_score, -0.9988)
        self.assertEqual(stopper.counter, 0)

    def test_exact_delta_is_not_a_significant_improvement(self):
        # Binary-exact values avoid floating-point ambiguity at the boundary.
        stopper = EarlyStopping(patience=7, delta=0.125)
        stopper(1.0)
        stopper(0.875)
        self.assertTrue(stopper.improved)
        self.assertEqual(stopper.best_val_loss, 0.875)
        self.assertEqual(stopper.best_score, -1.0)
        self.assertEqual(stopper.counter, 1)
        stopper(0.75)
        self.assertEqual(stopper.best_score, -0.75)
        self.assertEqual(stopper.counter, 0)

    def test_tied_loss_does_not_save_or_reset_even_with_zero_delta(self):
        stopper = EarlyStopping(patience=2, delta=0.0)
        stopper(0.5)
        stopper(0.5)
        self.assertFalse(stopper.improved)
        self.assertEqual(stopper.counter, 1)
        self.assertFalse(stopper.early_stop)
        stopper(0.5)
        self.assertFalse(stopper.improved)
        self.assertEqual(stopper.counter, 2)
        self.assertTrue(stopper.early_stop)
        self.assertEqual(stopper.best_val_loss, 0.5)

    def test_patience_exhaustion_keeps_the_earlier_best(self):
        stopper = EarlyStopping(patience=3, delta=0.001)
        stopper(1.0)
        stopper(0.5)
        for expected_count, loss in enumerate((0.6, 0.7, 0.8), 1):
            stopper(loss)
            self.assertFalse(stopper.improved)
            self.assertEqual(stopper.counter, expected_count)
            self.assertEqual(stopper.early_stop, expected_count == 3)
        self.assertEqual(stopper.best_val_loss, 0.5)
        self.assertEqual(stopper.best_score, -0.5)

    def test_new_fold_has_independent_loss_and_patience_state(self):
        first = EarlyStopping(patience=1, delta=0.001)
        first(0.1)
        first(0.2)
        self.assertTrue(first.early_stop)

        second = EarlyStopping(patience=1, delta=0.001)
        second(5.0)
        self.assertTrue(second.improved)
        self.assertFalse(second.early_stop)
        self.assertEqual(second.counter, 0)
        self.assertEqual(second.best_val_loss, 5.0)
        self.assertEqual(second.best_score, -5.0)
        self.assertEqual(first.best_val_loss, 0.1)
        self.assertTrue(first.early_stop)

    def test_first_nonfinite_loss_is_rejected_without_state_changes(self):
        for loss in (math.nan, math.inf, -math.inf):
            with self.subTest(loss=loss):
                stopper = EarlyStopping(patience=2, delta=0.001)
                original = dict(vars(stopper))
                with self.assertRaises(ValueError):
                    stopper(loss)
                self.assertEqual(vars(stopper), original)

    def test_nonfinite_loss_does_not_damage_existing_best_or_counter(self):
        for loss in (math.nan, math.inf, -math.inf):
            with self.subTest(loss=loss):
                stopper = EarlyStopping(patience=2, delta=0.001)
                stopper(0.5)
                stopper(0.6)
                original = dict(vars(stopper))
                with self.assertRaises(ValueError):
                    stopper(loss)
                self.assertEqual(vars(stopper), original)

    def test_saved_absolute_best_weights_survive_later_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'fold0_best.pth')
            model = torch.nn.Linear(1, 1, bias=False)
            stopper = EarlyStopping(patience=2, delta=0.001, path=path)
            saved_values = []
            for loss, weight in ((1.0, 1.0), (0.9995, 2.0), (1.2, 3.0)):
                with torch.no_grad():
                    model.weight.fill_(weight)
                stopper(loss)
                if stopper.improved:
                    stopper.save_checkpoint(loss, model)
                    saved_values.append(weight)
                if stopper.early_stop:
                    break

            self.assertTrue(stopper.early_stop)
            self.assertEqual(saved_values, [1.0, 2.0])
            self.assertEqual(model.weight.item(), 3.0)
            saved_state = torch.load(path, map_location='cpu')
            # Preserve the raw state_dict format expected by existing inference.
            self.assertEqual(set(saved_state), {'weight'})
            model.load_state_dict(saved_state)
            self.assertEqual(model.weight.item(), 2.0)
            self.assertAlmostEqual(stopper.best_val_loss, 0.9995)


if __name__ == '__main__':
    unittest.main()
