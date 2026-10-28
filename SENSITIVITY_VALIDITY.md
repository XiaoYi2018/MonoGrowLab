# Supplementary sensitivity validity contract

The supplementary grid retains every planned image, variant, severity, replicate and mode. A well-formed empty strict-extrema set is recorded explicitly; malformed bundles and unrelated errors still stop execution.

- `ok`: an actual prediction and its reported metrics are defined.
- `no_seeds`: the detector returns no seeds; no label map or zero-valued score is manufactured.
- `no_clean_reference`: the clean seed state is empty, so the paired clean reference cannot be computed. True branch seed counts and input hashes remain available; contrast metrics are null.

If a recomputed seed set is empty but the clean reference is defined, the valid fixed branch retains its actual metrics. Pairwise contrasts require both valid branches. Missing conditions propagate through replicate, severity and image aggregation. Family summaries require all ten prescribed images; otherwise means and intervals are NA with the defined-image count. No image or parameter setting is replaced or silently omitted. Archived baseline effects and confidence intervals remain unchanged.

The input project root is explicit and verified against its configuration and dataset manifest. It may be the same directory as the code checkout. New outputs must be in a new subdirectory of `results/`; archived or completed outputs remain immutable.
