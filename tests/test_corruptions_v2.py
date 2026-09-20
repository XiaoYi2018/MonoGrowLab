import json
import unittest
from pathlib import Path

import numpy as np

from monogrowlab.corruptions_v2 import apply_corruption, normalize_parameters


class CorruptionV2Tests(unittest.TestCase):
    def setUp(self):
        self.image = (np.arange(32 * 24, dtype=np.uint16).reshape(24, 32) % 256).astype(
            np.uint8
        )
        self.cases = [
            ("gaussian_noise", {"sigma": 5.0}, 11),
            (
                "gaussian_blur",
                {"sigma_px": 1.0, "truncate": 4.0, "boundary_mode": "reflect"},
                None,
            ),
            (
                "salt_pepper",
                {"amount": 0.1, "salt_fraction": 0.5, "sampling": "without_replacement"},
                12,
            ),
            (
                "jpeg",
                {"quality": 70, "subsampling": 0, "optimize": False, "progressive": False},
                None,
            ),
            (
                "brightness_scale",
                {"factor": 0.8, "rounding": "nearest_even", "clipping": "uint8_0_255"},
                None,
            ),
        ]

    def test_all_families_are_repeatable_and_shape_safe(self):
        for family, parameters, seed in self.cases:
            with self.subTest(family=family):
                first = apply_corruption(self.image, family, parameters, seed=seed)
                second = apply_corruption(self.image, family, parameters, seed=seed)
                np.testing.assert_array_equal(first, second)
                self.assertEqual(first.dtype, np.uint8)
                self.assertEqual(first.shape, self.image.shape)

    def test_random_families_change_with_seed(self):
        for family, parameters in [
            ("gaussian_noise", {"sigma": 5.0}),
            (
                "salt_pepper",
                {"amount": 0.1, "salt_fraction": 0.5, "sampling": "without_replacement"},
            ),
        ]:
            with self.subTest(family=family):
                first = apply_corruption(self.image, family, parameters, seed=1)
                second = apply_corruption(self.image, family, parameters, seed=2)
                self.assertFalse(np.array_equal(first, second))

    def test_random_and_deterministic_seed_contracts(self):
        with self.assertRaises(ValueError):
            apply_corruption(self.image, "gaussian_noise", {"sigma": 2.0}, seed=None)
        with self.assertRaises(ValueError):
            apply_corruption(
                self.image,
                "gaussian_blur",
                {"sigma_px": 1.0, "truncate": 4.0, "boundary_mode": "reflect"},
                seed=1,
            )

    def test_parameter_boundaries_fail(self):
        invalid = [
            ("gaussian_noise", {"sigma": -1.0}),
            (
                "gaussian_blur",
                {"sigma_px": 1.0, "truncate": 4.0, "boundary_mode": "wrap"},
            ),
            (
                "salt_pepper",
                {"amount": 1.1, "salt_fraction": 0.5, "sampling": "without_replacement"},
            ),
            (
                "jpeg",
                {"quality": 0, "subsampling": 0, "optimize": False, "progressive": False},
            ),
            (
                "brightness_scale",
                {"factor": 1.0, "rounding": "nearest_even", "clipping": "uint8_0_255"},
            ),
        ]
        for family, parameters in invalid:
            with self.subTest(family=family), self.assertRaises(ValueError):
                normalize_parameters(family, parameters)

    def test_reference_environment_gold_hashes(self):
        project_root = Path(__file__).resolve().parents[1]
        gold = json.loads(
            (project_root / "docs" / "corruption_gold_hashes.json").read_text(
                encoding="utf-8"
            )
        )
        from monogrowlab.experiment_schema import array_sha256

        self.assertEqual(array_sha256(self.image), gold["fixture"]["sha256"])
        for name, case in gold["cases"].items():
            with self.subTest(case=name):
                output = apply_corruption(
                    self.image,
                    case["family"],
                    case["params"],
                    seed=case["seed"],
                )
                self.assertEqual(array_sha256(output), case["output_sha256"])


if __name__ == "__main__":
    unittest.main()
