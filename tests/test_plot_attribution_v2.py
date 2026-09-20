import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments import plot_attribution_v2 as plot_module


VARIANTS = ["variant-a", "variant-b", "variant-c", "variant-d"]
SEVERITIES = {
    "gaussian_noise": ["sigma_2", "sigma_8"],
    "gaussian_blur": ["sigma_0p5", "sigma_1p5"],
    "salt_pepper": ["amount_0p005", "amount_0p02"],
    "jpeg": ["quality_90", "quality_50"],
    "brightness_scale": ["factor_0p8", "factor_1p2"],
}
FIELDNAMES = [
    "variant",
    "corruption_family",
    "stratum",
    "metric",
    "mean",
    "ci95_low",
    "ci95_high",
    "sign_flip_p",
    "holm_p",
]


def make_rows() -> list[dict[str, str]]:
    rows = []
    for variant_index, variant in enumerate(VARIANTS):
        for family_index, (family, severities) in enumerate(SEVERITIES.items()):
            mean = 0.01 * (variant_index + family_index + 1)
            rows.append(
                {
                    "variant": variant,
                    "corruption_family": family,
                    "stratum": "family",
                    "metric": plot_module.PLOT_METRIC,
                    "mean": str(mean),
                    "ci95_low": str(mean - 0.01),
                    "ci95_high": str(mean + 0.01),
                    "sign_flip_p": "0.03",
                    "holm_p": "0.04",
                }
            )
            gt_mean = mean - 0.005
            rows.append(
                {
                    "variant": variant,
                    "corruption_family": family,
                    "stratum": "family",
                    "metric": plot_module.GT_METRIC,
                    "mean": str(gt_mean),
                    "ci95_low": str(gt_mean - 0.01),
                    "ci95_high": str(gt_mean + 0.01),
                    "sign_flip_p": "0.02",
                    "holm_p": "",
                }
            )
            for severity_index, severity in enumerate(severities):
                rows.append(
                    {
                        "variant": variant,
                        "corruption_family": family,
                        "stratum": f"severity={severity}",
                        "metric": plot_module.PLOT_METRIC,
                        "mean": str(mean + severity_index * 0.001),
                        "ci95_low": str(mean - 0.01),
                        "ci95_high": str(mean + 0.01),
                        "sign_flip_p": "0.5",
                        "holm_p": "",
                    }
                )
    return rows


def write_bundle(
    root: Path,
    *,
    rows: list[dict[str, str]] | None = None,
    fieldnames: list[str] | None = None,
    primary_variants: list[str] | None = None,
    analysis_name: str = "analysis",
    config_name: str = "config.json",
    split: str = "val",
    image_count: int = 10,
) -> Path:
    analysis = root / analysis_name
    analysis.mkdir()
    config = {
        "variants": [{"id": variant} for variant in VARIANTS],
        "corruptions": [
            {
                "family": family,
                "severities": [{"id": severity} for severity in severities],
            }
            for family, severities in SEVERITIES.items()
        ],
    }
    config_path = root / config_name
    config_path.write_text(json.dumps(config), encoding="utf-8")
    metadata = {
        "primary_variants": VARIANTS if primary_variants is None else primary_variants,
        "run_context": {
            "config_path": config_name,
            "config_sha256": plot_module.canonical_hash(config),
            "split": split,
            "image_count": image_count,
            "analysis_role": "test",
        },
    }
    (analysis / "analysis_metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    selected_fields = FIELDNAMES if fieldnames is None else fieldnames
    with (analysis / "inference.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=selected_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(make_rows() if rows is None else rows)
    return analysis


class PlotAttributionValidationTests(unittest.TestCase):
    def load(self, root: Path, analysis: Path) -> plot_module.PlotData:
        with patch.object(plot_module, "PROJECT_ROOT", root):
            return plot_module.load_plot_data(analysis)

    def test_missing_required_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = write_bundle(
                root, fieldnames=[name for name in FIELDNAMES if name != "holm_p"]
            )
            with self.assertRaisesRegex(ValueError, "missing required columns: holm_p"):
                self.load(root, analysis)

    def test_missing_family_cell_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = make_rows()
            rows.remove(
                next(
                    row
                    for row in rows
                    if row["variant"] == "variant-d"
                    and row["corruption_family"] == "jpeg"
                    and row["stratum"] == "family"
                    and row["metric"] == plot_module.PLOT_METRIC
                )
            )
            analysis = write_bundle(root, rows=rows)
            with self.assertRaisesRegex(ValueError, "family-level row count mismatch"):
                self.load(root, analysis)

    def test_missing_severity_cell_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = make_rows()
            rows.remove(
                next(
                    row
                    for row in rows
                    if row["variant"] == "variant-a"
                    and row["corruption_family"] == "jpeg"
                    and row["stratum"] == "severity=quality_50"
                )
            )
            analysis = write_bundle(root, rows=rows)
            with self.assertRaisesRegex(ValueError, "severity-level row count mismatch"):
                self.load(root, analysis)

    def test_duplicate_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = make_rows()
            duplicate = next(
                row.copy()
                for row in rows
                if row["stratum"] == "family"
                and row["metric"] == plot_module.PLOT_METRIC
            )
            rows.append(duplicate)
            analysis = write_bundle(root, rows=rows)
            with self.assertRaisesRegex(ValueError, "duplicate family-level cell"):
                self.load(root, analysis)

    def test_empty_primary_variants_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = write_bundle(root, primary_variants=[])
            with self.assertRaisesRegex(ValueError, "primary_variants must be a non-empty"):
                self.load(root, analysis)

    def test_severity_order_follows_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = write_bundle(root)
            data = self.load(root, analysis)
            self.assertEqual(data.severity_order["jpeg"], ["quality_90", "quality_50"])
            self.assertNotEqual(data.severity_order["jpeg"], sorted(data.severity_order["jpeg"]))

    def test_heatmap_svg_contains_no_embedded_raster(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = write_bundle(root)
            data = self.load(root, analysis)
            output = root / "figures" / "heatmap"
            plot_module.figure_heatmap(
                data.rows, data.variants, data.families, output, "vector heatmap"
            )
            svg = output.with_suffix(".svg").read_text(encoding="utf-8")
            self.assertNotIn("<image", svg)

    def test_missing_gt_family_cell_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = make_rows()
            rows.remove(
                next(
                    row
                    for row in rows
                    if row["variant"] == "variant-c"
                    and row["corruption_family"] == "salt_pepper"
                    and row["stratum"] == "family"
                    and row["metric"] == plot_module.GT_METRIC
                )
            )
            analysis = write_bundle(root, rows=rows)
            with self.assertRaisesRegex(ValueError, "GT family-level row count mismatch"):
                self.load(root, analysis)

    def test_duplicate_gt_family_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = make_rows()
            duplicate = next(
                row.copy()
                for row in rows
                if row["stratum"] == "family"
                and row["metric"] == plot_module.GT_METRIC
            )
            rows.append(duplicate)
            analysis = write_bundle(root, rows=rows)
            with self.assertRaisesRegex(ValueError, "duplicate GT family-level cell"):
                self.load(root, analysis)

    def test_nonfinite_gt_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = make_rows()
            target = next(
                row
                for row in rows
                if row["stratum"] == "family"
                and row["metric"] == plot_module.GT_METRIC
            )
            target["mean"] = "nan"
            analysis = write_bundle(root, rows=rows)
            with self.assertRaisesRegex(ValueError, "non-finite mean"):
                self.load(root, analysis)

    def test_gt_contrast_svg_contains_no_embedded_raster(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = write_bundle(root)
            data = self.load(root, analysis)
            output = root / "figures" / "gt_contrast"
            plot_module.figure_gt_contrast(
                data.rows,
                data.variants,
                data.families,
                output,
                "vector contrast",
            )
            svg = output.with_suffix(".svg").read_text(encoding="utf-8")
            self.assertNotIn("<image", svg)

    def test_two_split_svg_contains_no_embedded_raster(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_analysis = write_bundle(
                root,
                analysis_name="validation-analysis",
                config_name="validation-config.json",
                split="val",
                image_count=10,
            )
            right_analysis = write_bundle(
                root,
                analysis_name="heldout-analysis",
                config_name="heldout-config.json",
                split="test",
                image_count=200,
            )
            left = self.load(root, left_analysis)
            right = self.load(root, right_analysis)
            output = root / "figures" / "family_gap_two_split"
            plot_module.figure_family_gap_two_split(
                left, right, output, "shared-axis split comparison"
            )
            svg = output.with_suffix(".svg").read_text(encoding="utf-8")
            self.assertNotIn("<image", svg)
            self.assertIn("Validation subset (n = 10)", svg)
            self.assertIn("Held-out test split (n = 200)", svg)

    def test_two_split_variant_order_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_analysis = write_bundle(
                root,
                analysis_name="validation-analysis",
                config_name="validation-config.json",
            )
            right_analysis = write_bundle(
                root,
                analysis_name="heldout-analysis",
                config_name="heldout-config.json",
                primary_variants=list(reversed(VARIANTS)),
                split="test",
                image_count=200,
            )
            left = self.load(root, left_analysis)
            right = self.load(root, right_analysis)
            with self.assertRaisesRegex(ValueError, "primary variant order differs"):
                plot_module.validate_two_split_data(left, right)

    def test_two_split_same_split_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_analysis = write_bundle(
                root,
                analysis_name="left-analysis",
                config_name="left-config.json",
            )
            right_analysis = write_bundle(
                root,
                analysis_name="right-analysis",
                config_name="right-config.json",
            )
            left = self.load(root, left_analysis)
            right = self.load(root, right_analysis)
            with self.assertRaisesRegex(ValueError, "record the same split"):
                plot_module.validate_two_split_data(left, right)

    def test_nonfinite_heldout_value_is_rejected_before_two_split_plot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = make_rows()
            target = next(
                row
                for row in rows
                if row["stratum"] == "family"
                and row["metric"] == plot_module.PLOT_METRIC
            )
            target["ci95_high"] = "inf"
            analysis = write_bundle(
                root,
                rows=rows,
                analysis_name="heldout-analysis",
                config_name="heldout-config.json",
                split="test",
                image_count=200,
            )
            with self.assertRaisesRegex(ValueError, "non-finite ci95_high"):
                self.load(root, analysis)


if __name__ == "__main__":
    unittest.main()
