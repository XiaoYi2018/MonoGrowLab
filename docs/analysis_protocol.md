# Analysis protocol

## Research question

For extrema-seeded region growing, how much of the segmentation change under an image perturbation is attributable to the growth rule itself, and how much is added by regenerating the seeds from the perturbed image?

This question is evaluated with two paired execution modes for the same image, perturbation level, random draw, growth algorithm, and seed policy:

- `fixed_clean`: extract seeds from the clean image and reuse them on the perturbed image;
- `recomputed`: extract seeds again from the perturbed image.

The first mode measures growth-stage sensitivity conditional on the clean seed state. The second measures full-pipeline sensitivity. Their paired difference is the seed-attribution gap, turning the modular distinction between seed generation and growth into a controlled robustness measurement.

## Development and confirmation split

- BSDS500 training data may be used for software debugging and invariant checks.
- BSDS500 validation data are used for seed-policy screening, corruption-level selection, and runtime feasibility.
- BSDS500 test data remain untouched until the variant set, corruption suite, metrics, and analysis code are frozen.
- Pilot and validation-subset outputs are not reported as official BSDS500 benchmark results.
- Image resizing, if used, is treated as part of the experimental condition and reported explicitly.

For the reported runs, images exceeding the configured maximum dimension are resized with aspect ratio preserved, bilinear interpolation, and antialiasing. Human label maps use nearest-neighbour interpolation without antialiasing. The resized RGB image is then converted to grayscale and min--max normalized per image to unsigned 8-bit values before seed extraction or corruption; a constant image maps to zero. Intensity-valued corruption parameters therefore operate on this normalized 0--255 scale.

## Variant policy

The validation seed screen selected one regularized seed policy per historical growth rule:

- CLERG: Gaussian-smoothed strict extrema with seed-detection sigma 1;
- Adams 1994: Gaussian-smoothed strict extrema with seed-detection sigma 2;
- Fan 2005: Gaussian-smoothed strict extrema with seed-detection sigma 2;
- Level-set 2004: Gaussian-smoothed strict extrema with seed-detection sigma 2.

Strict-extrema variants are retained as diagnostic baselines. They are not promoted to primary variants merely because a local result is favorable.

## Outcomes

### Primary outcome

For each primary variant, the seed-attribution effect is

`delta_ARI = stability_ARI(fixed_clean) - stability_ARI(recomputed)`.

The experimental unit is the image. Replicates at the same corruption level are averaged within image before across-image inference.

For the multi-corruption primary analysis, the family-level estimand is the equal-weight mean across the two prespecified severity levels after replicate averaging. Severity-specific effects and trends are secondary analyses and remain visible rather than being used as additional primary tests.

### Secondary outcomes

- paired difference in stability VI;
- paired difference in tolerance-aware boundary F1;
- paired fixed-versus-recomputed difference in ARI, VI, and boundary F1 against the human references, so that a stability advantage is not interpreted automatically as an accuracy advantage;
- change in seed count after recomputation;
- clean-image agreement with each human reference and the reference-averaged score;
- region count, coverage, runtime, and failure rate;
- interaction of corruption severity with the attribution gap.

Boundary F1 in the current implementation is the documented MonoGrowLab tolerance metric. It is not labelled as the official BSDS500 boundary benchmark.

## Inference

- Report per-image distributions, mean, median, and 95% confidence intervals.
- Obtain confidence intervals by paired bootstrap resampling of images, not individual replicate rows.
- Test a zero paired attribution effect with an exact or Monte Carlo sign-flip permutation test at image level.
- Apply Holm correction across the four primary algorithm variants for a corruption family.
- Report effect sizes and uncertainty whether or not a corrected p-value crosses 0.05.
- Treat strict-extrema variants, per-severity contrasts, and metric-specific subgroups as secondary analyses.

## Corruption families

The initial pilot uses additive Gaussian noise at 2, 5, and 8 intensity units. The schema-v2 suite additionally includes blur, impulse noise, JPEG compression, and brightness change. Each family has deterministic parameterization and explicit units. One shared `clean` mode supplies the unperturbed reference for all families; corruption operators therefore exclude nominal identity parameters rather than pretending that, for example, JPEG quality 100 is lossless. Random corruptions record a stable per-image seed derived from every condition coordinate.

## Decision gates

Proceed from pilot to a larger validation run only if:

1. records are complete and reproducible after resume;
2. fixed and recomputed modes are exactly paired;
3. the attribution effect has a consistent interpretable direction on multiple images;
4. clean-quality and runtime results identify a usable seed policy without relying on a single image;
5. no metric implementation failure or label-dependence is detected.

Freeze the test protocol only after at least one non-Gaussian corruption family and the statistical summarizer pass deterministic tests. The test split is then run once under the frozen configuration.

Before inference, the analyzer reconstructs the expected record grid from the configuration and dataset manifest. Every configured variant, selected image, corruption, severity, replicate, and both seed modes must be present exactly once; paired units and image hashes must also agree.
