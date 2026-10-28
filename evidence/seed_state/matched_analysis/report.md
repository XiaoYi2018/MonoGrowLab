# Matched-cardinality validation supplement

Secondary analysis on the original ten validation images. No held-out re-run, new primary significance tests, or parameter selection.

| Variant | Family | Original mean gap | Matched mean gap | Matched 95% CI | Positive images / 10 |
|---|---|---:|---:|---|---:|
| adams-gaussian2 | brightness_scale | +0.1235 | +0.1403 | [+0.0707, +0.2020] | 9 |
| adams-gaussian2 | gaussian_blur | +0.1923 | +0.1982 | [+0.1394, +0.2515] | 9 |
| adams-gaussian2 | gaussian_noise | +0.2062 | +0.2154 | [+0.1745, +0.2568] | 10 |
| adams-gaussian2 | jpeg | +0.1965 | +0.2047 | [+0.1367, +0.2686] | 9 |
| adams-gaussian2 | salt_pepper | +0.3814 | +0.3926 | [+0.3517, +0.4351] | 10 |
| clerg-gaussian1 | brightness_scale | -0.0888 | -0.0546 | [-0.1173, +0.0054] | 3 |
| clerg-gaussian1 | gaussian_blur | +0.1624 | +0.2027 | [+0.1713, +0.2401] | 10 |
| clerg-gaussian1 | gaussian_noise | +0.2550 | +0.2705 | [+0.2221, +0.3327] | 10 |
| clerg-gaussian1 | jpeg | +0.2353 | +0.2378 | [+0.1927, +0.3016] | 10 |
| clerg-gaussian1 | salt_pepper | +0.3095 | +0.3999 | [+0.3593, +0.4387] | 10 |
| fan2005-gaussian2 | brightness_scale | +0.1716 | +0.1882 | [+0.1113, +0.2676] | 9 |
| fan2005-gaussian2 | gaussian_blur | +0.1984 | +0.1935 | [+0.1555, +0.2365] | 10 |
| fan2005-gaussian2 | gaussian_noise | +0.1740 | +0.1733 | [+0.1328, +0.2088] | 10 |
| fan2005-gaussian2 | jpeg | +0.2308 | +0.2379 | [+0.1834, +0.2881] | 10 |
| fan2005-gaussian2 | salt_pepper | +0.3979 | +0.3973 | [+0.3577, +0.4453] | 10 |
| levelset-gaussian2 | brightness_scale | +0.1200 | +0.1245 | [+0.0508, +0.1990] | 8 |
| levelset-gaussian2 | gaussian_blur | +0.2219 | +0.1882 | [+0.1447, +0.2291] | 10 |
| levelset-gaussian2 | gaussian_noise | +0.2193 | +0.2307 | [+0.1836, +0.2803] | 10 |
| levelset-gaussian2 | jpeg | +0.1961 | +0.1878 | [+0.1497, +0.2203] | 10 |
| levelset-gaussian2 | salt_pepper | +0.4164 | +0.4075 | [+0.3815, +0.4358] | 10 |

Matched-source sensitivity uses its own common clean reference. It is not a causal decomposition of the original gap; seed coordinates and initial intensities remain parts of the replaced state.

Seed density/coordinates are summarized in seed_diagnostics_family.csv; nearest distances do not establish point identities.
