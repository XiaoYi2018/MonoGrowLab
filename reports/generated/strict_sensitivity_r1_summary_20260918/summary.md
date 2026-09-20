# Experiment summary

Generated: 2026-09-18T00:32:37.132483+00:00

Source: `<repository>\experiments\runs\bsds500_multicorruption_v2_validation_10x160_strict_sensitivity_r1.jsonl`

Configuration: `configs/bsds500_multicorruption_v2_validation_10x160_strict_sensitivity_r1.json`; split: `val`; images: 10; configured maximum dimension: 160; human references per image: [5, 6, 7].

Run interpretation: schema-v2 strict-manifest secondary seed-detector sensitivity experiment on ten explicit BSDS500 validation images; not an official BSDS500 test-set benchmark result

Records: 1160; successful: 1160; failed: 0.

## Clean-image comparison

| Variant | n | Seeds | Runtime (s) | GT ARI | GT VI | Boundary F1 (t=1) |
|---|---:|---:|---:|---:|---:|---:|
| adams-strict | 10 | 1233.0000 | 2.2152 | 0.0690 | 4.6681 | 0.3229 |
| clerg-strict | 10 | 1233.0000 | 0.8867 | 0.0670 | 4.8664 | 0.3207 |
| fan2005-strict | 10 | 1233.0000 | 1.4284 | 0.0405 | 4.8913 | 0.3279 |
| levelset-strict | 10 | 1233.0000 | 1.5263 | 0.0355 | 4.9426 | 0.3294 |

## Strictly paired attribution

| Corruption | Severity | Variant | Pairs | Fixed stability ARI | Recomputed stability ARI | Stability gap | GT ARI difference | Seed increase |
|---|---|---|---:|---:|---:|---:|---:|---:|
| brightness_scale | factor_0p8 | adams-strict | 10 | 0.4856 | 0.7724 | -0.2868 | 0.0715 | -65.6000 |
| brightness_scale | factor_1p2 | adams-strict | 10 | 0.5108 | 0.6854 | -0.1746 | 0.0183 | -47.5000 |
| gaussian_blur | sigma_0p5 | adams-strict | 10 | 0.7034 | 0.5874 | 0.1160 | -0.0059 | -425.5000 |
| gaussian_blur | sigma_1p5 | adams-strict | 10 | 0.3541 | 0.1948 | 0.1593 | -0.1156 | -1149.7000 |
| gaussian_noise | sigma_2 | adams-strict | 20 | 0.6513 | 0.3574 | 0.2939 | 0.0676 | 323.2500 |
| gaussian_noise | sigma_8 | adams-strict | 20 | 0.4960 | 0.2335 | 0.2625 | 0.0643 | 1012.7000 |
| jpeg | quality_50 | adams-strict | 10 | 0.5489 | 0.3965 | 0.1524 | 0.0263 | -172.9000 |
| jpeg | quality_90 | adams-strict | 10 | 0.6542 | 0.4581 | 0.1961 | 0.0604 | 145.0000 |
| salt_pepper | amount_0p005 | adams-strict | 20 | 0.9739 | 0.9131 | 0.0608 | 0.0167 | 56.6000 |
| salt_pepper | amount_0p02 | adams-strict | 20 | 0.9119 | 0.7250 | 0.1868 | 0.0340 | 200.6500 |
| brightness_scale | factor_0p8 | clerg-strict | 10 | 0.3050 | 0.6630 | -0.3579 | 0.0383 | -65.6000 |
| brightness_scale | factor_1p2 | clerg-strict | 10 | 0.2136 | 0.5203 | -0.3067 | -0.0002 | -47.5000 |
| gaussian_blur | sigma_0p5 | clerg-strict | 10 | 0.7256 | 0.4179 | 0.3077 | 0.0061 | -425.5000 |
| gaussian_blur | sigma_1p5 | clerg-strict | 10 | 0.3730 | 0.1706 | 0.2024 | -0.1114 | -1149.7000 |
| gaussian_noise | sigma_2 | clerg-strict | 20 | 0.6160 | 0.3086 | 0.3074 | 0.0622 | 323.2500 |
| gaussian_noise | sigma_8 | clerg-strict | 20 | 0.2533 | 0.1998 | 0.0535 | 0.0284 | 1012.7000 |
| jpeg | quality_50 | clerg-strict | 10 | 0.4342 | 0.3183 | 0.1159 | -0.0134 | -172.9000 |
| jpeg | quality_90 | clerg-strict | 10 | 0.6354 | 0.3912 | 0.2442 | 0.0585 | 145.0000 |
| salt_pepper | amount_0p005 | clerg-strict | 20 | 0.9265 | 0.8773 | 0.0493 | 0.0215 | 56.6000 |
| salt_pepper | amount_0p02 | clerg-strict | 20 | 0.7939 | 0.6682 | 0.1257 | 0.0355 | 200.6500 |
| brightness_scale | factor_0p8 | fan2005-strict | 10 | 0.3628 | 0.7882 | -0.4255 | 0.0955 | -65.6000 |
| brightness_scale | factor_1p2 | fan2005-strict | 10 | 0.3749 | 0.6752 | -0.3002 | 0.0389 | -47.5000 |
| gaussian_blur | sigma_0p5 | fan2005-strict | 10 | 0.6491 | 0.5585 | 0.0906 | -0.0017 | -425.5000 |
| gaussian_blur | sigma_1p5 | fan2005-strict | 10 | 0.2834 | 0.1479 | 0.1355 | -0.1060 | -1149.7000 |
| gaussian_noise | sigma_2 | fan2005-strict | 20 | 0.6363 | 0.3552 | 0.2811 | 0.0479 | 323.2500 |
| gaussian_noise | sigma_8 | fan2005-strict | 20 | 0.5568 | 0.2119 | 0.3449 | 0.0330 | 1012.7000 |
| jpeg | quality_50 | fan2005-strict | 10 | 0.4558 | 0.3688 | 0.0870 | 0.0571 | -172.9000 |
| jpeg | quality_90 | fan2005-strict | 10 | 0.5658 | 0.4253 | 0.1405 | 0.0485 | 145.0000 |
| salt_pepper | amount_0p005 | fan2005-strict | 20 | 0.9816 | 0.9068 | 0.0747 | 0.0065 | 56.6000 |
| salt_pepper | amount_0p02 | fan2005-strict | 20 | 0.9017 | 0.6987 | 0.2030 | 0.0149 | 200.6500 |
| brightness_scale | factor_0p8 | levelset-strict | 10 | 0.4245 | 0.7632 | -0.3387 | 0.0903 | -65.6000 |
| brightness_scale | factor_1p2 | levelset-strict | 10 | 0.5731 | 0.6683 | -0.0952 | -0.0253 | -47.5000 |
| gaussian_blur | sigma_0p5 | levelset-strict | 10 | 0.8335 | 0.5653 | 0.2683 | -0.0096 | -425.5000 |
| gaussian_blur | sigma_1p5 | levelset-strict | 10 | 0.5116 | 0.1377 | 0.3738 | -0.1422 | -1149.7000 |
| gaussian_noise | sigma_2 | levelset-strict | 20 | 0.8321 | 0.3844 | 0.4477 | 0.0286 | 323.2500 |
| gaussian_noise | sigma_8 | levelset-strict | 20 | 0.6306 | 0.2297 | 0.4009 | 0.0320 | 1012.7000 |
| jpeg | quality_50 | levelset-strict | 10 | 0.6846 | 0.3769 | 0.3077 | 0.0166 | -172.9000 |
| jpeg | quality_90 | levelset-strict | 10 | 0.7984 | 0.4411 | 0.3573 | 0.0206 | 145.0000 |
| salt_pepper | amount_0p005 | levelset-strict | 20 | 0.9874 | 0.9294 | 0.0580 | 0.0040 | 56.6000 |
| salt_pepper | amount_0p02 | levelset-strict | 20 | 0.9524 | 0.7600 | 0.1924 | 0.0119 | 200.6500 |

## Interpretation boundary

These tables describe the configured run only. Development and validation-subset experiments are not test-set benchmark claims. Boundary F1 is the documented MonoGrowLab tolerance metric, not the official BSDS500 boundary benchmark implementation.
