import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_bsds500_file_manifest",
    PROJECT_ROOT / "experiments" / "build_bsds500_file_manifest.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DatasetManifestTests(unittest.TestCase):
    def setUp(self):
        self.counts = {
            "images": {split: 1 for split in MODULE.SPLITS},
            "ground_truth": {split: 1 for split in MODULE.SPLITS},
        }
        self.source = {
            "image_counts": {split: 1 for split in MODULE.SPLITS},
            "ground_truth_counts": {split: 1 for split in MODULE.SPLITS},
        }
        self.rows = []
        for split in MODULE.SPLITS:
            self.rows.extend(
                [
                    {"split": split, "image_id": "1", "role": "image"},
                    {"split": split, "image_id": "1", "role": "ground_truth"},
                ]
            )

    def test_validate_inventory_accepts_paired_identifiers(self):
        MODULE.validate_inventory(self.rows, self.counts, self.source)

    def test_validate_inventory_rejects_count_mismatch(self):
        changed = {**self.counts, "images": {**self.counts["images"], "val": 2}}
        with self.assertRaisesRegex(RuntimeError, "dataset counts differ"):
            MODULE.validate_inventory(self.rows, changed, self.source)

    def test_validate_inventory_rejects_identifier_mismatch(self):
        changed = [dict(row) for row in self.rows]
        changed[-1]["image_id"] = "other"
        with self.assertRaisesRegex(RuntimeError, "identifier mismatch"):
            MODULE.validate_inventory(changed, self.counts, self.source)


if __name__ == "__main__":
    unittest.main()
