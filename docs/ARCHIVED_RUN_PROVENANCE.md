# Archived-run provenance

MonoGrowLab preserves the run records and metadata used by the accompanying article. Each metadata file is an immutable ledger of the exact package state at run time. The release package is newer in several non-numerical or safety-related files, so attempting to resume an archived output with the release package is expected to fail closed.

## Stable execution anchors

- Schema-v2 runner at execution and release: `a96ea48a4a7a5130f70f029dbb575c0b2ea05f52aba652e2e71762fef0838ba6`
- Dataset manifest: `c6a49b978ef2df82b05bbb12c7a55e03e8778f96c4a29aeb15760acbb83c3418`
- Held-out run: 23,200 records, SHA-256 `9eab1ceca545977a1f87a40238354b30aefe385e44743d8217acc17caba2d693`
- Held-out metadata: SHA-256 `41c636cf2cd1f89c4967b721b65e89b7bb44cd37565d5efbf5a3ccaceb3a4c74`

## Recorded-to-release source changes

| File | Recorded SHA-256 | Release SHA-256 | Scope |
|---|---|---|---|
| `src/monogrowlab/cli.py` | `bd619aef2cba4f73fa9006177f720f32c28abecf6798a48f0da20d163918905c` | `408ef8a5159cdcf348edbc0bca35269b9de8b237030ec327dba080f9791f98f0` | Added plotting-label plumbing after the run; the runner does not import the CLI module. The frozen file is included as `docs/frozen_sources/test_run_cli.py`. |
| `src/monogrowlab/datasets.py` | `f32e504ae46d7e742cc22027195875c0419279288863507cd6e07e69600080de` | `e5f9ce973504b26db5f1212b20e0c172ccbbe3247e08512f336b2707e2f7aa37` | Release safety check: missing or empty split directories now raise an explicit error instead of producing a zero-record success. The run-time file is included as `docs/frozen_sources/run_datasets.py`. |
| `src/monogrowlab/experiment_schema.py` | `767ce0104bf8faea217e28dfbbd7922cf1c8e34d604f5983b49bad79e5d53b37` for smoke/validation | `808f955b2924317f469ff5bfc9bc42c31ff78b8eb924cc7804d5e494b4759c21` | Updated before the strict-sensitivity and held-out runs; those two metadata files already record the release hash. |
| `src/monogrowlab/reporting.py` | `ce4fe5ecd6b600dd0ae8e2f28ca4d8cb89fe26b08adf56b25824ac4f24a7cf23` for smoke/validation | `28e612cf98ea68ce154ebe967480011e6ec129c174585a7162832dce6dca12a6` | Updated before the strict-sensitivity and held-out runs; those two metadata files already record the release hash. |
| `experiments/analyze_attribution_v2.py` | `6782e3fd63d39b897cc155f8e7caf0702c8c256dbc15da6036b78f8f51b5be53` for validation; `420ad34aed782093d35b1d708ce991b07664cdfd83061ac1e837cc17b476def2` for strict/test | `c3b05b718ca05472eb72775ba7360744cf870e51c334c63ddbd5e3c5baad7048` | Updated report wording to identify validation and held-out roles explicitly. Re-analysis with the release analyzer reproduced all archived paired, image-level, and inference CSV files byte-for-byte. The strict/test analyzer is included as `docs/frozen_sources/strict_test_analyzer.py`. |

The four run ledgers list 14 historical Python files under `legacy_hashes`. The public runtime closure requires six project-owned kernels, all of which are included and indexed in `docs/legacy_source_manifest.csv`. The remaining eight recorded files were historical evaluation or utility modules not imported by the released adapter: `esr.py`, `evaluation_d.py`, `evaluation_dm_new.py`, `evaluation_f.py`, `evaluation_ssim.py`, `ppi.py`, `run_noise_stability_test.py`, and `run_srg_batch_test03.py`.

The release runner remains byte-identical to the runner used for all archived schema-v2 records. Fresh runs must use a copied configuration with a new output path; archived outputs remain immutable provenance objects.
