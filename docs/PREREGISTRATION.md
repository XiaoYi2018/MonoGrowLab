# Held-out BSDS500 pre-registration

This protocol was frozen on 2026-09-18 before any held-out test-split result was inspected. Its purpose was to confirm the seed-attribution result developed on the validation split in one prespecified run.

## Frozen design

- Configuration: `configs/bsds500_multicorruption_v2_test_200x160_r1.json`
- Canonical configuration SHA-256: `388ae01cfbcae627343afbc00a4fb3d4694e49940560e51e0b5d9aa22ae5c71c`
- File SHA-256 at freeze: `1d888a57844fdefb7879ebcee712eceaa25d2047f024accb77ae6d8be610d352`
- Split: all 200 BSDS500 test images; no image subset or limit
- Maximum image dimension: 160 pixels
- Primary variants: `clerg-gaussian1`, `adams-gaussian2`, `fan2005-gaussian2`, and `levelset-gaussian2`
- Corruptions: five families, each at two prespecified severities; stochastic families use the same replicate and base-seed design as validation
- Expected records: 23,200
- Dataset manifest: schema 2, 1,000 files with per-file SHA-256 hashes

The strict-extrema variant was reserved for validation sensitivity analysis and was not part of the confirmatory test family.

## Primary endpoint and inference

The primary endpoint is the family-level seed-attribution gap,
`delta_stability_ari = stability_ARI(fixed_clean) - stability_ARI(recomputed)`,
with image as the experimental unit (`n = 200`). Confidence intervals use 10,000 image-level paired bootstrap resamples. Sign-flip tests use 100,000 Monte Carlo permutations for `n > 18`. Holm correction is applied separately within each corruption family across the four primary variants.

The decision rule is fixed as follows:

1. A variant passes only when its family-level mean has the prespecified positive sign and its Holm-adjusted p-value is below 0.05.
2. A corruption family is supported only when at least three of its four primary variants pass.
3. The overall held-out statement is licensed only when at least four of the five corruption families are supported.

Ground-truth ARI, variation of information, and boundary agreement are mandatory secondary results but do not change the primary decision rule. Severity-level results are descriptive secondary analyses.

## Frozen constraints

The held-out result could not be used to add or replace variants, change corruption parameters, resize rules, metrics, random seeds, image subsets, or Holm families. The test split could not be rerun or selectively reported. A disagreement with validation would have changed only the conclusion selected by the fixed decision rule, not the protocol.

The machine-readable freeze ledger is [`test_split_freeze.json`](test_split_freeze.json). The completed run is summarized in [`heldout_acceptance.json`](heldout_acceptance.json).
