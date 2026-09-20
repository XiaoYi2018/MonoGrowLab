# Experiment summary

Generated: 2026-09-19T04:33:12.754795+00:00

Source: `<repository>\experiments\runs\bsds500_multicorruption_v2_test_200x160_r1.jsonl`

Configuration: `configs/bsds500_multicorruption_v2_test_200x160_r1.json`; split: `test`; images: 200; configured maximum dimension: 160; human references per image: [4, 5, 6, 7, 8].

Run interpretation: schema-v2 strict-manifest BSDS500 test-split confirmatory experiment on all 200 test images; single prespecified run; not to be re-tuned after inspection

Records: 23200; successful: 23200; failed: 0.

## Clean-image comparison

| Variant | n | Seeds | Runtime (s) | GT ARI | GT VI | Boundary F1 (t=1) |
|---|---:|---:|---:|---:|---:|---:|
| adams-gaussian2 | 200 | 34.0050 | 2.8117 | 0.3272 | 1.9396 | 0.4531 |
| clerg-gaussian1 | 200 | 222.5400 | 1.3003 | 0.0780 | 3.3770 | 0.3703 |
| fan2005-gaussian2 | 200 | 34.0050 | 3.3632 | 0.3119 | 2.0044 | 0.4556 |
| levelset-gaussian2 | 200 | 34.0050 | 4.1098 | 0.3144 | 1.9857 | 0.4560 |

## Strictly paired attribution

| Corruption | Severity | Variant | Pairs | Fixed stability ARI | Recomputed stability ARI | Stability gap | GT ARI difference | Seed increase |
|---|---|---|---:|---:|---:|---:|---:|---:|
| brightness_scale | factor_0p8 | adams-gaussian2 | 200 | 0.6652 | 0.5784 | 0.0869 | 0.0222 | -6.2800 |
| brightness_scale | factor_1p2 | adams-gaussian2 | 200 | 0.7399 | 0.5965 | 0.1433 | 0.0141 | 3.5750 |
| gaussian_blur | sigma_0p5 | adams-gaussian2 | 200 | 0.7661 | 0.5508 | 0.2153 | 0.0012 | -2.4700 |
| gaussian_blur | sigma_1p5 | adams-gaussian2 | 200 | 0.5131 | 0.3900 | 0.1231 | 0.0182 | -18.1000 |
| gaussian_noise | sigma_2 | adams-gaussian2 | 400 | 0.8237 | 0.6005 | 0.2233 | 0.0003 | 0.2800 |
| gaussian_noise | sigma_8 | adams-gaussian2 | 400 | 0.7155 | 0.5306 | 0.1849 | 0.0189 | 2.0825 |
| jpeg | quality_50 | adams-gaussian2 | 200 | 0.7183 | 0.5552 | 0.1631 | -0.0012 | -0.0450 |
| jpeg | quality_90 | adams-gaussian2 | 200 | 0.7983 | 0.6405 | 0.1578 | 0.0005 | 0.0000 |
| salt_pepper | amount_0p005 | adams-gaussian2 | 400 | 0.9566 | 0.6383 | 0.3183 | 0.0257 | 3.9600 |
| salt_pepper | amount_0p02 | adams-gaussian2 | 400 | 0.9077 | 0.4808 | 0.4269 | 0.0802 | 13.5900 |
| brightness_scale | factor_0p8 | clerg-gaussian1 | 200 | 0.3384 | 0.3767 | -0.0382 | -0.0143 | -22.8350 |
| brightness_scale | factor_1p2 | clerg-gaussian1 | 200 | 0.2812 | 0.3959 | -0.1148 | -0.0131 | 11.0200 |
| gaussian_blur | sigma_0p5 | clerg-gaussian1 | 200 | 0.5532 | 0.3056 | 0.2477 | 0.0023 | -42.1950 |
| gaussian_blur | sigma_1p5 | clerg-gaussian1 | 200 | 0.2258 | 0.1331 | 0.0926 | -0.0387 | -176.3700 |
| gaussian_noise | sigma_2 | clerg-gaussian1 | 400 | 0.6416 | 0.3348 | 0.3069 | 0.0148 | 9.0000 |
| gaussian_noise | sigma_8 | clerg-gaussian1 | 400 | 0.3129 | 0.1565 | 0.1564 | 0.0248 | 103.3125 |
| jpeg | quality_50 | clerg-gaussian1 | 200 | 0.4692 | 0.2378 | 0.2314 | -0.0081 | 15.8550 |
| jpeg | quality_90 | clerg-gaussian1 | 200 | 0.6218 | 0.3758 | 0.2460 | -0.0051 | 4.6550 |
| salt_pepper | amount_0p005 | clerg-gaussian1 | 400 | 0.9419 | 0.7161 | 0.2258 | -0.0008 | 40.4250 |
| salt_pepper | amount_0p02 | clerg-gaussian1 | 400 | 0.8552 | 0.4123 | 0.4429 | 0.0069 | 150.2075 |
| brightness_scale | factor_0p8 | fan2005-gaussian2 | 200 | 0.6570 | 0.5504 | 0.1067 | 0.0244 | -6.2800 |
| brightness_scale | factor_1p2 | fan2005-gaussian2 | 200 | 0.7281 | 0.5668 | 0.1613 | 0.0132 | 3.5750 |
| gaussian_blur | sigma_0p5 | fan2005-gaussian2 | 200 | 0.7379 | 0.5222 | 0.2158 | -0.0003 | -2.4700 |
| gaussian_blur | sigma_1p5 | fan2005-gaussian2 | 200 | 0.4938 | 0.3870 | 0.1067 | 0.0148 | -18.1000 |
| gaussian_noise | sigma_2 | fan2005-gaussian2 | 400 | 0.7846 | 0.5567 | 0.2279 | 0.0085 | 0.2800 |
| gaussian_noise | sigma_8 | fan2005-gaussian2 | 400 | 0.5685 | 0.4396 | 0.1289 | 0.0137 | 2.0825 |
| jpeg | quality_50 | fan2005-gaussian2 | 200 | 0.6915 | 0.5109 | 0.1806 | 0.0086 | -0.0450 |
| jpeg | quality_90 | fan2005-gaussian2 | 200 | 0.7564 | 0.6061 | 0.1503 | 0.0028 | 0.0000 |
| salt_pepper | amount_0p005 | fan2005-gaussian2 | 400 | 0.9658 | 0.6115 | 0.3544 | 0.0216 | 3.9600 |
| salt_pepper | amount_0p02 | fan2005-gaussian2 | 400 | 0.9006 | 0.4665 | 0.4341 | 0.0713 | 13.5900 |
| brightness_scale | factor_0p8 | levelset-gaussian2 | 200 | 0.6542 | 0.5552 | 0.0990 | 0.0354 | -6.2800 |
| brightness_scale | factor_1p2 | levelset-gaussian2 | 200 | 0.7377 | 0.5709 | 0.1669 | 0.0173 | 3.5750 |
| gaussian_blur | sigma_0p5 | levelset-gaussian2 | 200 | 0.7627 | 0.5311 | 0.2316 | -0.0020 | -2.4700 |
| gaussian_blur | sigma_1p5 | levelset-gaussian2 | 200 | 0.5241 | 0.3946 | 0.1295 | -0.0012 | -18.1000 |
| gaussian_noise | sigma_2 | levelset-gaussian2 | 400 | 0.8314 | 0.5827 | 0.2487 | 0.0027 | 0.2800 |
| gaussian_noise | sigma_8 | levelset-gaussian2 | 400 | 0.7241 | 0.5146 | 0.2095 | 0.0224 | 2.0825 |
| jpeg | quality_50 | levelset-gaussian2 | 200 | 0.7248 | 0.5303 | 0.1945 | 0.0004 | -0.0450 |
| jpeg | quality_90 | levelset-gaussian2 | 200 | 0.8109 | 0.6337 | 0.1772 | 0.0027 | 0.0000 |
| salt_pepper | amount_0p005 | levelset-gaussian2 | 400 | 0.9670 | 0.6293 | 0.3377 | 0.0269 | 3.9600 |
| salt_pepper | amount_0p02 | levelset-gaussian2 | 400 | 0.9107 | 0.4661 | 0.4447 | 0.0805 | 13.5900 |

## Interpretation boundary

These tables describe the configured run only. Development and validation-subset experiments are not test-set benchmark claims. Boundary F1 is the documented MonoGrowLab tolerance metric, not the official BSDS500 boundary benchmark implementation.
