import unittest

import numpy as np

from monogrowlab.metrics import (
    adjusted_rand_index,
    boundary_scores,
    partition_scores,
    variation_of_information,
)


class MetricTests(unittest.TestCase):
    def setUp(self):
        labels = np.zeros((16, 16), dtype=np.int32)
        labels[:, 8:] = 1
        self.reference = labels

    def test_identical_partitions_are_perfect(self):
        scores = boundary_scores(self.reference, self.reference, tolerance=0)
        self.assertEqual(scores.precision, 1.0)
        self.assertEqual(scores.recall, 1.0)
        self.assertEqual(scores.f1, 1.0)
        self.assertAlmostEqual(adjusted_rand_index(self.reference, self.reference), 1.0)
        self.assertAlmostEqual(variation_of_information(self.reference, self.reference)["total"], 0.0)

    def test_label_permutation_does_not_change_partition_scores(self):
        relabeled = np.where(self.reference == 0, 17, -4)
        scores = partition_scores(self.reference, relabeled)
        self.assertAlmostEqual(scores["adjusted_rand_index"], 1.0)
        self.assertAlmostEqual(scores["vi_total"], 0.0)
        self.assertAlmostEqual(boundary_scores(self.reference, relabeled).f1, 1.0)

    def test_tolerance_recovers_one_pixel_boundary_shift(self):
        shifted = np.zeros_like(self.reference)
        shifted[:, 9:] = 1
        exact = boundary_scores(self.reference, shifted, tolerance=0)
        tolerant = boundary_scores(self.reference, shifted, tolerance=1)
        self.assertLess(exact.f1, tolerant.f1)
        self.assertAlmostEqual(tolerant.f1, 1.0)

    def test_empty_boundary_conventions(self):
        flat_a = np.zeros((8, 8), dtype=np.int32)
        flat_b = np.ones((8, 8), dtype=np.int32)
        self.assertEqual(boundary_scores(flat_a, flat_b).f1, 1.0)
        split = flat_b.copy()
        split[:, 4:] = 2
        self.assertEqual(boundary_scores(flat_a, split).f1, 0.0)

    def test_invalid_inputs_fail_loudly(self):
        with self.assertRaises(ValueError):
            boundary_scores(self.reference, self.reference[:, :-1])
        with self.assertRaises(ValueError):
            boundary_scores(self.reference, self.reference, tolerance=-1)


if __name__ == "__main__":
    unittest.main()

