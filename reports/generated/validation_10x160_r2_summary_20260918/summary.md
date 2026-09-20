# Experiment summary

Generated: 2026-09-17T23:40:25.929730+00:00

Source: `<repository>\experiments\runs\bsds500_multicorruption_v2_validation_10x160_r2.jsonl`

Configuration: `configs/bsds500_multicorruption_v2_validation_10x160_r2.json`; split: `val`; images: 10; configured maximum dimension: 160; human references per image: [5, 6, 7].

Run interpretation: schema-v2 strict-manifest multi-corruption development experiment on ten explicit BSDS500 validation images; not an official BSDS500 test-set benchmark result

Records: 1160; successful: 1160; failed: 0.

## Clean-image comparison

| Variant | n | Seeds | Runtime (s) | GT ARI | GT VI | Boundary F1 (t=1) |
|---|---:|---:|---:|---:|---:|---:|
| adams-gaussian2 | 10 | 34.2000 | 2.7178 | 0.2848 | 2.1135 | 0.4109 |
| clerg-gaussian1 | 10 | 224.1000 | 1.2874 | 0.1151 | 3.4363 | 0.3410 |
| fan2005-gaussian2 | 10 | 34.2000 | 3.4894 | 0.2904 | 2.1016 | 0.4113 |
| levelset-gaussian2 | 10 | 34.2000 | 3.9725 | 0.2690 | 2.1637 | 0.4098 |

## Strictly paired attribution

| Corruption | Severity | Variant | Pairs | Fixed stability ARI | Recomputed stability ARI | Stability gap | GT ARI difference | Seed increase |
|---|---|---|---:|---:|---:|---:|---:|---:|
| brightness_scale | factor_0p8 | adams-gaussian2 | 10 | 0.6304 | 0.5847 | 0.0457 | -0.0037 | -3.7000 |
| brightness_scale | factor_1p2 | adams-gaussian2 | 10 | 0.7976 | 0.5963 | 0.2014 | -0.0053 | 2.6000 |
| gaussian_blur | sigma_0p5 | adams-gaussian2 | 10 | 0.7750 | 0.5090 | 0.2661 | -0.0092 | -3.2000 |
| gaussian_blur | sigma_1p5 | adams-gaussian2 | 10 | 0.4663 | 0.3478 | 0.1186 | 0.0285 | -18.1000 |
| gaussian_noise | sigma_2 | adams-gaussian2 | 20 | 0.8330 | 0.5784 | 0.2546 | 0.0291 | 2.7500 |
| gaussian_noise | sigma_8 | adams-gaussian2 | 20 | 0.6798 | 0.5219 | 0.1579 | 0.0164 | 2.9500 |
| jpeg | quality_50 | adams-gaussian2 | 10 | 0.6808 | 0.5028 | 0.1779 | 0.0056 | 1.3000 |
| jpeg | quality_90 | adams-gaussian2 | 10 | 0.8472 | 0.6321 | 0.2151 | 0.0140 | 0.2000 |
| salt_pepper | amount_0p005 | adams-gaussian2 | 20 | 0.9432 | 0.6165 | 0.3266 | 0.0013 | 1.2500 |
| salt_pepper | amount_0p02 | adams-gaussian2 | 20 | 0.9213 | 0.4852 | 0.4361 | 0.0584 | 14.1500 |
| brightness_scale | factor_0p8 | clerg-gaussian1 | 10 | 0.3445 | 0.4131 | -0.0686 | -0.0046 | -23.5000 |
| brightness_scale | factor_1p2 | clerg-gaussian1 | 10 | 0.3035 | 0.4124 | -0.1089 | -0.0355 | 14.2000 |
| gaussian_blur | sigma_0p5 | clerg-gaussian1 | 10 | 0.5683 | 0.3315 | 0.2368 | -0.0042 | -42.0000 |
| gaussian_blur | sigma_1p5 | clerg-gaussian1 | 10 | 0.2734 | 0.1854 | 0.0880 | -0.0100 | -177.3000 |
| gaussian_noise | sigma_2 | clerg-gaussian1 | 20 | 0.6535 | 0.3377 | 0.3157 | 0.0519 | 7.8000 |
| gaussian_noise | sigma_8 | clerg-gaussian1 | 20 | 0.3519 | 0.1577 | 0.1942 | 0.0664 | 80.5000 |
| jpeg | quality_50 | clerg-gaussian1 | 10 | 0.5132 | 0.2864 | 0.2269 | -0.0054 | 10.0000 |
| jpeg | quality_90 | clerg-gaussian1 | 10 | 0.6305 | 0.3868 | 0.2437 | 0.0080 | 2.5000 |
| salt_pepper | amount_0p005 | clerg-gaussian1 | 20 | 0.9177 | 0.7073 | 0.2104 | -0.0027 | 38.0000 |
| salt_pepper | amount_0p02 | clerg-gaussian1 | 20 | 0.8184 | 0.4098 | 0.4086 | 0.0341 | 134.2500 |
| brightness_scale | factor_0p8 | fan2005-gaussian2 | 10 | 0.6701 | 0.5339 | 0.1362 | 0.0015 | -3.7000 |
| brightness_scale | factor_1p2 | fan2005-gaussian2 | 10 | 0.7985 | 0.5914 | 0.2071 | 0.0008 | 2.6000 |
| gaussian_blur | sigma_0p5 | fan2005-gaussian2 | 10 | 0.7983 | 0.5087 | 0.2897 | -0.0039 | -3.2000 |
| gaussian_blur | sigma_1p5 | fan2005-gaussian2 | 10 | 0.4697 | 0.3625 | 0.1072 | 0.0313 | -18.1000 |
| gaussian_noise | sigma_2 | fan2005-gaussian2 | 20 | 0.7761 | 0.5238 | 0.2522 | 0.0254 | 2.7500 |
| gaussian_noise | sigma_8 | fan2005-gaussian2 | 20 | 0.5436 | 0.4478 | 0.0958 | 0.0216 | 2.9500 |
| jpeg | quality_50 | fan2005-gaussian2 | 10 | 0.6803 | 0.4658 | 0.2145 | 0.0133 | 1.3000 |
| jpeg | quality_90 | fan2005-gaussian2 | 10 | 0.8201 | 0.5730 | 0.2471 | 0.0171 | 0.2000 |
| salt_pepper | amount_0p005 | fan2005-gaussian2 | 20 | 0.9638 | 0.6060 | 0.3578 | -0.0036 | 1.2500 |
| salt_pepper | amount_0p02 | fan2005-gaussian2 | 20 | 0.9211 | 0.4832 | 0.4379 | 0.0702 | 14.1500 |
| brightness_scale | factor_0p8 | levelset-gaussian2 | 10 | 0.6287 | 0.5432 | 0.0854 | 0.0088 | -3.7000 |
| brightness_scale | factor_1p2 | levelset-gaussian2 | 10 | 0.7280 | 0.5733 | 0.1546 | -0.0021 | 2.6000 |
| gaussian_blur | sigma_0p5 | levelset-gaussian2 | 10 | 0.8031 | 0.5177 | 0.2854 | -0.0039 | -3.2000 |
| gaussian_blur | sigma_1p5 | levelset-gaussian2 | 10 | 0.5236 | 0.3651 | 0.1585 | -0.0180 | -18.1000 |
| gaussian_noise | sigma_2 | levelset-gaussian2 | 20 | 0.8185 | 0.5595 | 0.2590 | 0.0179 | 2.7500 |
| gaussian_noise | sigma_8 | levelset-gaussian2 | 20 | 0.6914 | 0.5118 | 0.1796 | 0.0074 | 2.9500 |
| jpeg | quality_50 | levelset-gaussian2 | 10 | 0.6892 | 0.5071 | 0.1821 | 0.0136 | 1.3000 |
| jpeg | quality_90 | levelset-gaussian2 | 10 | 0.8389 | 0.6287 | 0.2102 | 0.0137 | 0.2000 |
| salt_pepper | amount_0p005 | levelset-gaussian2 | 20 | 0.9712 | 0.6018 | 0.3694 | -0.0010 | 1.2500 |
| salt_pepper | amount_0p02 | levelset-gaussian2 | 20 | 0.9142 | 0.4508 | 0.4634 | 0.0539 | 14.1500 |

## Interpretation boundary

These tables describe the configured run only. Development and validation-subset experiments are not test-set benchmark claims. Boundary F1 is the documented MonoGrowLab tolerance metric, not the official BSDS500 boundary benchmark implementation.
