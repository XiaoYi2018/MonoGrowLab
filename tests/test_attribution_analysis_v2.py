import random
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "experiments"))

from analyze_attribution_v2 import inference_row, report  # noqa: E402


class AttributionAnalysisV2Tests(unittest.TestCase):
    def test_minimum_attainable_p_matches_exact_and_monte_carlo_methods(self):
        exact = inference_row(
            "variant",
            "family",
            "family",
            "metric",
            [1.0, 1.0],
            bootstrap=20,
            permutations=99,
            rng=random.Random(17),
        )
        self.assertEqual(exact["test_method"], "exact")
        self.assertEqual(exact["minimum_attainable_p"], 0.5)

        monte_carlo = inference_row(
            "variant",
            "family",
            "family",
            "metric",
            [1.0] * 19,
            bootstrap=20,
            permutations=99,
            rng=random.Random(17),
        )
        self.assertEqual(monte_carlo["test_method"], "monte_carlo")
        self.assertEqual(monte_carlo["minimum_attainable_p"], 0.01)

    def test_report_scope_tracks_dataset_split(self):
        context = {
            "config_path": "configs/example.json",
            "split": "validation",
            "image_count": 10,
            "configured_max_dimension": 160,
            "ground_truth_references_per_image": 5,
            "interpretation": "validation",
        }
        validation_text = report([], (), context)
        self.assertIn("designated non-test split", validation_text)
        self.assertNotIn("held-out result", validation_text)

        context["split"] = "test"
        context["image_count"] = 200
        context["interpretation"] = "held-out confirmation"
        test_text = report([], (), context)
        self.assertIn("held-out result", test_text)
        self.assertIn("reserved test split", test_text)
        self.assertNotIn("designated non-test split", test_text)


if __name__ == "__main__":
    unittest.main()
