import unittest

from monogrowlab.reporting import render_html


class ReportingTests(unittest.TestCase):
    def test_render_is_standalone_and_escapes_metadata(self):
        context = {
            "config_path": "configs/<unsafe>.json",
            "split": "val",
            "image_count": 2,
            "configured_max_dimension": 96,
            "interpretation": "development & validation",
        }
        inference = [
            {
                "variant": "clerg-gaussian1",
                "corruption_family": "gaussian_noise",
                "stratum": "family",
                "metric": "delta_stability_ari",
                "n_images": "2",
                "mean": "0.2",
                "ci95_low": "0.1",
                "ci95_high": "0.3",
                "sign_flip_p": "0.5",
                "test_method": "exact",
                "minimum_attainable_p": "0.5",
                "holm_p": "0.5",
            },
            {
                "variant": "clerg-gaussian1",
                "corruption_family": "gaussian_noise",
                "stratum": "family",
                "metric": "delta_gt_ari_mean",
                "n_images": "2",
                "mean": "0.01",
                "ci95_low": "-0.02",
                "ci95_high": "0.04",
                "sign_flip_p": "0.5",
                "test_method": "exact",
                "minimum_attainable_p": "0.5",
                "holm_p": "",
            },
        ]
        document = render_html(context, inference, [], [])
        self.assertIn("<!doctype html>", document)
        self.assertIn("configs/&lt;unsafe&gt;.json", document)
        self.assertIn("development &amp; validation", document)
        self.assertIn("0.2000", document)
        self.assertIn("0.5000 (n.s.)", document)
        self.assertIn("minimum attainable two-sided sign-flip p", document)
        self.assertIn("hsl(216", document)
        self.assertNotIn("hsl(145", document)
        self.assertNotIn("<unsafe>", document)

    def test_small_p_values_use_scientific_notation(self):
        context = {
            "config_path": "config.json",
            "split": "val",
            "image_count": 19,
            "configured_max_dimension": 160,
            "interpretation": "development",
        }
        inference = [
            {
                "variant": "clerg-gaussian1",
                "corruption_family": "gaussian_noise",
                "stratum": "family",
                "metric": "delta_stability_ari",
                "n_images": "19",
                "mean": "0.2",
                "ci95_low": "0.1",
                "ci95_high": "0.3",
                "sign_flip_p": "0.0000199998",
                "test_method": "monte_carlo",
                "minimum_attainable_p": "0.0000099999",
                "holm_p": "0.0000799992",
            }
        ]
        document = render_html(context, inference, [], [])
        self.assertIn("8.00e-05", document)
        self.assertIn("1.00e-05", document)
        self.assertNotIn(">0.0000<", document)

    def test_custom_primary_variants_control_table_assignment(self):
        context = {
            "config_path": "strict.json",
            "split": "val",
            "image_count": 10,
            "configured_max_dimension": 160,
            "interpretation": "secondary sensitivity",
            "analysis_role": "secondary_sensitivity",
        }
        inference = [
            {
                "variant": "clerg-strict",
                "corruption_family": "gaussian_noise",
                "stratum": "family",
                "metric": "delta_stability_ari",
                "n_images": "10",
                "mean": "0.125",
                "ci95_low": "0.05",
                "ci95_high": "0.2",
                "sign_flip_p": "0.001953125",
                "test_method": "exact",
                "minimum_attainable_p": "0.001953125",
                "holm_p": "0.0078125",
            }
        ]
        document = render_html(
            context,
            inference,
            [],
            [],
            primary_variants=["clerg-strict"],
        )
        family_section, sensitivity_section = document.split(
            "<h2>Seed-policy sensitivity variants</h2>"
        )
        self.assertIn("clerg-strict", family_section)
        self.assertNotIn("clerg-strict", sensitivity_section)
        self.assertIn("Prespecified secondary sensitivity", document)
        self.assertIn("Secondary sensitivity: family-level attribution", document)

    def test_empty_primary_variants_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            render_html({}, [], [], [], primary_variants=[])


if __name__ == "__main__":
    unittest.main()
