import unittest

from monogrowlab.experiment_schema import pair_records, variant_label


def v2_record(mode, **updates):
    base = {
        "schema_version": 2,
        "status": "ok",
        "mode": mode,
        "config": "cfg",
        "variant_id": "variant-a",
        "image_id": "image-1",
        "algorithm": {"name": "adams1994"},
        "seed_strategy": {"name": "gaussian_strict", "sigma": 2.0},
        "corruption_family": "gaussian_noise",
        "severity_id": "sigma_2",
        "corruption_params": {"sigma": 2.0},
        "corruption_units": "8-bit intensity standard deviation",
        "replicate": 0,
        "random_seed": 17,
        "clean_image_sha256": "clean",
        "corrupted_image_sha256": "abc",
        "source_image_sha256": "source",
        "ground_truth_sha256": "ground-truth",
        "height": 16,
        "width": 24,
        "stability_ari": 0.8 if mode == "fixed_clean" else 0.5,
        "stability_vi_total": 0.2 if mode == "fixed_clean" else 0.7,
        "stability_boundary_f1_t1": 0.9 if mode == "fixed_clean" else 0.6,
        "gt_ari_mean": 0.7 if mode == "fixed_clean" else 0.65,
        "gt_vi_total_mean": 0.4 if mode == "fixed_clean" else 0.5,
        "gt_boundary_f1_t1_mean": 0.8 if mode == "fixed_clean" else 0.75,
        "seed_count": 10 if mode == "fixed_clean" else 30,
    }
    base.update(updates)
    return base


def complete_records(**updates):
    return [
        v2_record(
            "clean",
            random_seed=None,
            corrupted_image_sha256="clean",
            **updates,
        ),
        v2_record("fixed_clean", **updates),
        v2_record("recomputed", **updates),
    ]


class ExperimentSchemaTests(unittest.TestCase):
    def test_pairing_directions_and_metadata(self):
        pair = pair_records(complete_records())[0]
        self.assertAlmostEqual(pair["delta_stability_ari"], 0.3)
        self.assertAlmostEqual(pair["fixed_advantage_stability_vi_total"], 0.5)
        self.assertAlmostEqual(pair["delta_stability_boundary_f1_t1"], 0.3)
        self.assertAlmostEqual(pair["delta_gt_ari_mean"], 0.05)
        self.assertAlmostEqual(pair["fixed_advantage_gt_vi_total_mean"], 0.1)
        self.assertAlmostEqual(pair["delta_gt_boundary_f1_t1_mean"], 0.05)
        self.assertEqual(pair["recomputed_minus_fixed_seed_count"], 20)
        self.assertEqual(pair["corrupted_image_sha256"], "abc")

    def test_missing_duplicate_and_mismatched_pairs_fail(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete pair"):
            pair_records([v2_record("clean"), v2_record("fixed_clean")])
        with self.assertRaisesRegex(RuntimeError, "duplicate paired mode"):
            pair_records(
                [v2_record("clean"), v2_record("fixed_clean"), v2_record("fixed_clean")]
            )
        with self.assertRaisesRegex(RuntimeError, "corrupted_image_sha256"):
            pair_records(
                [
                    v2_record("clean", random_seed=None, corrupted_image_sha256="clean"),
                    v2_record("fixed_clean"),
                    v2_record("recomputed", corrupted_image_sha256="different"),
                ]
            )
        with self.assertRaisesRegex(RuntimeError, "random_seed"):
            pair_records(
                [
                    v2_record("clean", random_seed=None, corrupted_image_sha256="clean"),
                    v2_record("fixed_clean"),
                    v2_record("recomputed", random_seed=18),
                ]
            )
        with self.assertRaisesRegex(RuntimeError, "source_image_sha256"):
            pair_records(
                [
                    v2_record("clean", random_seed=None, corrupted_image_sha256="clean"),
                    v2_record("fixed_clean"),
                    v2_record("recomputed", source_image_sha256="different"),
                ]
            )
        with self.assertRaisesRegex(RuntimeError, "clean-record mismatch in clean_image_sha256"):
            pair_records(
                [
                    v2_record(
                        "clean",
                        random_seed=None,
                        clean_image_sha256="different-clean",
                        corrupted_image_sha256="different-clean",
                    ),
                    v2_record("fixed_clean"),
                    v2_record("recomputed"),
                ]
            )

    def test_family_prevents_numeric_severity_collision(self):
        fixed_noise = v2_record("fixed_clean")
        recomputed_noise = v2_record("recomputed")
        fixed_blur = v2_record(
            "fixed_clean",
            corruption_family="gaussian_blur",
            severity_id="sigma_2",
            corruption_params={"sigma_px": 2.0, "truncate": 4.0, "boundary_mode": "reflect"},
            corruption_units="pixels",
            random_seed=None,
            corrupted_image_sha256="blur",
        )
        recomputed_blur = {**fixed_blur, "mode": "recomputed", "stability_ari": 0.4}
        pairs = pair_records(
            [
                v2_record("clean", random_seed=None, corrupted_image_sha256="clean"),
                fixed_noise,
                recomputed_noise,
                fixed_blur,
                recomputed_blur,
            ]
        )
        self.assertEqual(len(pairs), 2)

    def test_legacy_variant_fallback_is_algorithm_specific(self):
        first = {"algorithm": {"name": "adams1994"}, "seed_strategy": {"name": "strict"}}
        second = {"algorithm": {"name": "fan2005"}, "seed_strategy": {"name": "strict"}}
        self.assertNotEqual(variant_label(first), variant_label(second))

    def test_mixed_schema_versions_are_rejected(self):
        legacy = {
            **v2_record("fixed_clean"),
            "sigma": 2.0,
            "schema_version": 1,
        }
        legacy.pop("corruption_family")
        legacy.pop("severity_id")
        legacy.pop("corruption_params")
        legacy.pop("corruption_units")
        with self.assertRaisesRegex(RuntimeError, "mixed record schema versions"):
            pair_records([v2_record("fixed_clean"), v2_record("recomputed"), legacy])


if __name__ == "__main__":
    unittest.main()
