# Corruption protocol (schema version 2)

## Purpose and scope

The corruption suite is designed for paired attribution experiments, not for training augmentation. Each perturbed image is evaluated twice with the same growth algorithm and identical corrupted pixels: once with seeds extracted from the clean image (`fixed_clean`) and once with seeds extracted from the corrupted image (`recomputed`). The paired difference therefore isolates the additional instability associated with seed regeneration.

Schema-v1 Gaussian records remain immutable historical pilot data. New multi-family runs use schema version 2, a separate runner, separate configurations, and separate result files. The v2 runner refuses to append when its configuration, dataset manifest, dependencies, legacy sources, maintained package sources, or runner hash differs from the metadata that created the result file.

## Families and units

| Family | Parameters | Definition |
|---|---|---|
| `gaussian_noise` | `sigma` | Add independent zero-mean Gaussian noise in 8-bit intensity units, round to nearest even, clip to `[0, 255]`, and cast to `uint8`. |
| `gaussian_blur` | `sigma_px`, `truncate`, `boundary_mode` | Apply SciPy Gaussian filtering in floating point. Sigma is in pixels; the accepted boundary mode is `reflect`. Output is rounded to nearest even and clipped to `uint8`. |
| `salt_pepper` | `amount`, `salt_fraction`, `sampling` | Select exactly `round(amount * pixel_count)` distinct pixels without replacement. Assign the rounded salt fraction to 255 and the remainder to 0. |
| `jpeg` | `quality`, `subsampling`, `optimize`, `progressive` | Encode and decode an 8-bit grayscale Pillow image with fixed quality, subsampling 0, and both optimize and progressive disabled. |
| `brightness_scale` | `factor`, `rounding`, `clipping` | Multiply intensities in floating point, round to nearest even, clip to `[0, 255]`, and cast to `uint8`. Factor 1 is excluded because clean images are recorded separately. |

Random families (`gaussian_noise` and `salt_pepper`) use a deterministic 64-bit seed derived from the experiment base seed, image identifier, family, severity identifier, normalized parameters, and replicate. Deterministic families require a null random seed and exactly one replicate.

## Identity and pairing

Every v2 perturbed record contains:

- schema version, configuration hash, variant identifier, algorithm parameters, and seed policy;
- image identifier, source-image hash, ground-truth hash, resized clean-image hash, and corrupted-image hash;
- corruption family, stable severity identifier, canonical parameter object, units, replicate, and random seed;
- execution mode, dimensions, status, diagnostics, and evaluation metrics.

Fixed and recomputed records are paired only when all condition coordinates match. Pair construction rejects missing modes, duplicates, failed records, or mismatches in configuration, algorithm, seed policy, dimensions, replicate, random seed, and image hashes.

## Reference fixture

`docs/corruption_gold_hashes.json` stores fixed-input output hashes generated on the reference Windows environment. Unit tests recompute every family and compare against these stored hashes. The JSON also records Python, NumPy, SciPy, Pillow, and platform versions. A dependency upgrade that intentionally changes an operator must therefore be reviewed and accompanied by a justified fixture update rather than silently changing experiment pixels.

## Statistical unit

Replicates are first averaged within image and severity. Severities are then averaged within image and corruption family. Across-image confidence intervals and sign-flip tests use images—not replicate rows—as experimental units. Holm correction is applied separately within each corruption family across the four primary algorithm variants. Severity-specific analyses are secondary.
