import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "experiments"))

from run_bsds_robustness_v2 import (  # noqa: E402
    dataset_file_index,
    normalize_corruption_specs,
    prepare_metadata,
    stable_seed,
    verify_dataset_files,
)
from monogrowlab.datasets import list_bsds500_ids  # noqa: E402


class RunnerV2Tests(unittest.TestCase):
    def test_dataset_discovery_rejects_missing_and_empty_split(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FileNotFoundError, "split directories are missing"):
                list_bsds500_ids(root, "test")

            (root / "images" / "test").mkdir(parents=True)
            (root / "groundTruth" / "test").mkdir(parents=True)
            with self.assertRaisesRegex(FileNotFoundError, "no BSDS500 image"):
                list_bsds500_ids(root, "test")

    def test_stable_seed_uses_all_condition_coordinates(self):
        base = stable_seed(17, "img", "gaussian_noise", "low", {"sigma": 2.0}, 0)
        self.assertEqual(
            base,
            stable_seed(17, "img", "gaussian_noise", "low", {"sigma": 2.0}, 0),
        )
        alternatives = {
            stable_seed(18, "img", "gaussian_noise", "low", {"sigma": 2.0}, 0),
            stable_seed(17, "other", "gaussian_noise", "low", {"sigma": 2.0}, 0),
            stable_seed(17, "img", "salt_pepper", "low", {"sigma": 2.0}, 0),
            stable_seed(17, "img", "gaussian_noise", "high", {"sigma": 2.0}, 0),
            stable_seed(17, "img", "gaussian_noise", "low", {"sigma": 3.0}, 0),
            stable_seed(17, "img", "gaussian_noise", "low", {"sigma": 2.0}, 1),
        }
        self.assertNotIn(base, alternatives)
        self.assertEqual(len(alternatives), 6)

    def test_normalization_rejects_ambiguous_specs(self):
        with self.assertRaisesRegex(ValueError, "deterministic family"):
            normalize_corruption_specs(
                {
                    "corruptions": [
                        {
                            "family": "jpeg",
                            "replicates": 2,
                            "severities": [
                                {
                                    "id": "q90",
                                    "params": {
                                        "quality": 90,
                                        "subsampling": 0,
                                        "optimize": False,
                                        "progressive": False,
                                    },
                                }
                            ],
                        }
                    ]
                }
            )
        with self.assertRaisesRegex(ValueError, "duplicate corruption severity"):
            normalize_corruption_specs(
                {
                    "corruptions": [
                        {
                            "family": "gaussian_noise",
                            "severities": [
                                {"id": "same", "params": {"sigma": 2.0}},
                                {"id": "same", "params": {"sigma": 3.0}},
                            ],
                        }
                    ]
                }
            )

    def test_metadata_creation_and_resume_are_fail_closed(self):
        immutable = {"schema_version": 2, "config_sha256": "abc"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "run.jsonl"
            metadata = root / "run.jsonl.meta.json"

            prepare_metadata(metadata, immutable, output)
            self.assertTrue(output.is_file())
            self.assertEqual(output.stat().st_size, 0)
            self.assertEqual(json.loads(metadata.read_text())["config_sha256"], "abc")
            prepare_metadata(metadata, immutable, output)

            with self.assertRaisesRegex(RuntimeError, "immutable metadata changed"):
                prepare_metadata(metadata, {**immutable, "config_sha256": "changed"}, output)

    def test_zero_byte_output_without_metadata_is_recoverable(self):
        immutable = {"schema_version": 2, "config_sha256": "abc"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "run.jsonl"
            metadata = root / "run.jsonl.meta.json"
            output.touch()
            prepare_metadata(metadata, immutable, output)
            self.assertTrue(metadata.is_file())

    def test_nonempty_output_without_metadata_is_rejected(self):
        immutable = {"schema_version": 2, "config_sha256": "abc"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "run.jsonl"
            metadata = root / "run.jsonl.meta.json"
            output.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "non-empty result JSONL"):
                prepare_metadata(metadata, immutable, output)

    def test_dataset_manifest_index_is_strict(self):
        payload = {
            "schema_version": 2,
            "dataset_root": "data/root",
            "files": [
                {
                    "path": "images/val/1.jpg",
                    "role": "image",
                    "bytes": 3,
                    "sha256": "a" * 64,
                }
            ],
        }
        index, summary = dataset_file_index(payload, "data/root")
        self.assertEqual(index["images/val/1.jpg"]["role"], "image")
        self.assertTrue(summary["per_file_hashes_declared"])
        self.assertNotIn("per_file_hashes_verified", summary)
        with self.assertRaisesRegex(ValueError, "root differs"):
            dataset_file_index(payload, "other/root")
        duplicate = {**payload, "files": payload["files"] * 2}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            dataset_file_index(duplicate, "data/root")
        with self.assertRaisesRegex(ValueError, "require dataset manifest schema_version=2"):
            dataset_file_index({"schema_version": 1}, "data/root")

    def test_full_manifest_verification_precedes_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "images" / "val" / "1.jpg"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"abc")
            payload = {
                "schema_version": 2,
                "dataset_root": "data/root",
                "files": [
                    {
                        "path": "images/val/1.jpg",
                        "role": "image",
                        "bytes": 3,
                        "sha256": hashlib.sha256(b"abc").hexdigest(),
                    }
                ],
            }
            index, declaration = dataset_file_index(payload, "data/root")
            verified = verify_dataset_files(root, index, declaration)
            self.assertTrue(verified["per_file_hashes_verified"])
            self.assertEqual(verified["verified_file_count"], 1)
            self.assertEqual(verified["verification_scope"], "entire_manifest_before_run")
            path.write_bytes(b"abd")
            with self.assertRaisesRegex(RuntimeError, "hash differs"):
                verify_dataset_files(root, index, declaration)


if __name__ == "__main__":
    unittest.main()
