import unittest

import numpy as np

from monogrowlab.corruptions import gaussian_noise


class CorruptionTests(unittest.TestCase):
    def test_gaussian_noise_is_deterministic(self):
        image = np.full((32, 32), 128, dtype=np.uint8)
        first = gaussian_noise(image, sigma=5.0, seed=17)
        second = gaussian_noise(image, sigma=5.0, seed=17)
        other = gaussian_noise(image, sigma=5.0, seed=18)
        np.testing.assert_array_equal(first, second)
        self.assertFalse(np.array_equal(first, other))

    def test_zero_sigma_is_identity(self):
        image = np.arange(64, dtype=np.uint8).reshape(8, 8)
        np.testing.assert_array_equal(image, gaussian_noise(image, sigma=0.0, seed=1))

    def test_invalid_inputs_fail_loudly(self):
        with self.assertRaises(ValueError):
            gaussian_noise(np.zeros((4, 4), dtype=np.float32), sigma=1.0, seed=1)
        with self.assertRaises(ValueError):
            gaussian_noise(np.zeros((4, 4), dtype=np.uint8), sigma=-1.0, seed=1)


if __name__ == "__main__":
    unittest.main()

