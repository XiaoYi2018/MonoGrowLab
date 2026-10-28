import unittest
from pathlib import Path

import numpy as np

from monogrowlab.corruptions import gaussian_noise
from monogrowlab.legacy_adapter import LegacyAdapter
from monogrowlab.synthetic import extrema_fixture


class SeedStrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy_root = Path(__file__).resolve().parents[1] / "legacy_reference" / "core"
        cls.adapter = LegacyAdapter(cls.legacy_root)

    def test_seed_strategies_produce_valid_bundles(self):
        image, _ = extrema_fixture(49)
        for strategy in (
            {"name": "strict"},
            {"name": "gaussian_strict", "sigma": 1.0},
            {"name": "h_extrema", "height": 4.0},
        ):
            seeds = self.adapter.extract_seeds(image, strategy)
            self.assertGreater(seeds.count, 0)
            self.assertEqual(seeds.y.shape, (seeds.count,))
            self.assertEqual(seeds.x.shape, (seeds.count,))
            self.assertEqual(seeds.statistics.shape, (seeds.count, 2))
            self.assertEqual(int(np.count_nonzero(seeds.labels)), seeds.count)

    def test_h_extrema_suppresses_noise_seeds(self):
        image = np.full((65, 65), 128, dtype=np.uint8)
        noisy = gaussian_noise(image, sigma=8.0, seed=9)
        strict = self.adapter.extract_seeds(noisy, {"name": "strict"})
        suppressed = self.adapter.extract_seeds(noisy, {"name": "h_extrema", "height": 8.0})
        self.assertGreater(strict.count, 0)
        self.assertGreater(suppressed.count, 0)
        self.assertLess(suppressed.count, strict.count)


if __name__ == "__main__":
    unittest.main()

