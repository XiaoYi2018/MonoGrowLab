# Archived-run provenance

MonoGrowLab preserves the run records and metadata used by the accompanying article. Each metadata file is an immutable ledger of the exact package state at run time. The release package is newer in several non-numerical or safety-related files, so attempting to resume an archived output with the release package is expected to fail closed.

## Stable execution anchors

- Schema-v2 runner at execution and in the v0.1.0 release: `a96ea48a4a7a5130f70f029dbb575c0b2ea05f52aba652e2e71762fef0838ba6`
- Dataset manifest: `c6a49b978ef2df82b05bbb12c7a55e03e8778f96c4a29aeb15760acbb83c3418`
- Held-out run: 23,200 records, SHA-256 `9eab1ceca545977a1f87a40238354b30aefe385e44743d8217acc17caba2d693`
- Held-out metadata: SHA-256 `41c636cf2cd1f89c4967b721b65e89b7bb44cd37565d5efbf5a3ccaceb3a4c74`

## Recorded-to-v0.1.0 source changes

| File | Recorded SHA-256 | v0.1.0 SHA-256 | Scope |
|---|---|---|---|
| `src/monogrowlab/cli.py` | `bd619aef2cba4f73fa9006177f720f32c28abecf6798a48f0da20d163918905c` | `408ef8a5159cdcf348edbc0bca35269b9de8b237030ec327dba080f9791f98f0` | Added plotting-label plumbing after the run; the runner does not import the CLI module. The frozen file is included as `docs/frozen_sources/test_run_cli.py`. |
| `src/monogrowlab/datasets.py` | `f32e504ae46d7e742cc22027195875c0419279288863507cd6e07e69600080de` | `e5f9ce973504b26db5f1212b20e0c172ccbbe3247e08512f336b2707e2f7aa37` | Release safety check: missing or empty split directories now raise an explicit error instead of producing a zero-record success. The run-time file is included as `docs/frozen_sources/run_datasets.py`. |
| `src/monogrowlab/experiment_schema.py` | `767ce0104bf8faea217e28dfbbd7922cf1c8e34d604f5983b49bad79e5d53b37` for smoke/validation | `808f955b2924317f469ff5bfc9bc42c31ff78b8eb924cc7804d5e494b4759c21` | Updated before the strict-sensitivity and held-out runs; those two metadata files already record the release hash. |
| `src/monogrowlab/reporting.py` | `ce4fe5ecd6b600dd0ae8e2f28ca4d8cb89fe26b08adf56b25824ac4f24a7cf23` for smoke/validation | `28e612cf98ea68ce154ebe967480011e6ec129c174585a7162832dce6dca12a6` | Updated before the strict-sensitivity and held-out runs; those two metadata files already record the release hash. |
| `experiments/analyze_attribution_v2.py` | `6782e3fd63d39b897cc155f8e7caf0702c8c256dbc15da6036b78f8f51b5be53` for validation; `420ad34aed782093d35b1d708ce991b07664cdfd83061ac1e837cc17b476def2` for strict/test | `c3b05b718ca05472eb72775ba7360744cf870e51c334c63ddbd5e3c5baad7048` | Updated report wording to identify validation and held-out roles explicitly. Re-analysis with the release analyzer reproduced all archived paired, image-level, and inference CSV files byte-for-byte. The strict/test analyzer is included as `docs/frozen_sources/strict_test_analyzer.py`. |

The four run ledgers list 14 historical Python files under `legacy_hashes`. The public runtime closure requires six project-owned kernels, all of which are included and indexed in `docs/legacy_source_manifest.csv`. The remaining eight recorded files were historical evaluation or utility modules not imported by the released adapter: `esr.py`, `evaluation_d.py`, `evaluation_dm_new.py`, `evaluation_f.py`, `evaluation_ssim.py`, `ppi.py`, `run_noise_stability_test.py`, and `run_srg_batch_test03.py`.

The v0.1.0 runner remains byte-identical to the runner used for all archived schema-v2 records. Fresh runs must use a copied configuration with a new output path; archived outputs remain immutable provenance objects.

The `path` fields in `docs/test_split_freeze.json` are freeze-time source coordinates. To preserve the ledger byte-for-byte while keeping the recorded sources directly inspectable, the held-out runner, summarizer, and experiment schema are copied to `docs/frozen_sources/heldout_runner.py`, `docs/frozen_sources/heldout_summarizer.py`, and `docs/frozen_sources/heldout_experiment_schema.py`. Their SHA-256 values exactly match the corresponding ledger entries. The already frozen analyzer and CLI remain `docs/frozen_sources/strict_test_analyzer.py` and `docs/frozen_sources/test_run_cli.py`.

## v0.1.1 validation hardening

Version 0.1.1 does not rewrite the archived records or derived tables. It adds three fail-closed checks for future execution and analysis:

- the runner verifies every file declared by the dataset manifest before starting a new run;
- the analyzer reconstructs the complete configured record grid and rejects a condition when both paired modes are absent;
- corruption units are part of the pairing identity, so inconsistent fixed/recomputed units cannot be accepted.

The archived v0.1.0 field `per_file_hashes_verified` was emitted when the manifest index was validated and each consumed input was subsequently checked before decoding. It did not represent an eager scan of unused files from other splits; v0.1.1 records that stronger whole-manifest check explicitly with `verification_scope = "entire_manifest_before_run"` and `verified_file_count`.

## Test-run source to v0.1.1 changes

| File | Test-run SHA-256 | v0.1.1 SHA-256 | Scope |
|---|---|---|---|
| `experiments/run_bsds_robustness_v2.py` | `a96ea48a4a7a5130f70f029dbb575c0b2ea05f52aba652e2e71762fef0838ba6` | `f6d978ef8d9d8f05b8eba72059752012e28a9c2a60e34d1728c3b0b6236940fc` | Added eager verification of every manifest-declared file before a new run starts. The test-run source is `docs/frozen_sources/heldout_runner.py`. |
| `experiments/summarize_results_v2.py` | `31d1236eb4b9252bad6c82852c5a78b375864cc8cf45a89ab9ffe811a136e4fc` | `f548092bdac55782c72cadd3152fafbad5926e7329e3912ba7f984b1b83d6898` | Added complete configured-grid validation before summarization. The test-run source is `docs/frozen_sources/heldout_summarizer.py`. |
| `src/monogrowlab/experiment_schema.py` | `808f955b2924317f469ff5bfc9bc42c31ff78b8eb924cc7804d5e494b4759c21` | `de024278014e21898c8bd4bd22c4ada88e666fcbfc765e012324528930897441` | Added complete-grid validation and corruption units to the pairing identity. The test-run source is `docs/frozen_sources/heldout_experiment_schema.py`. |
| `experiments/analyze_attribution_v2.py` | `420ad34aed782093d35b1d708ce991b07664cdfd83061ac1e837cc17b476def2` | `0c3359151071acfdee8375b3946abfaecdd353a7924d6cd01de15f0ff18f2420` | Added complete configured-grid validation before inference. Re-analysis reproduces the archived paired, image-level, and inference CSV files byte-for-byte; the test-run source is `docs/frozen_sources/strict_test_analyzer.py`. |
| `src/monogrowlab/__init__.py` | `0fdb121bf937733aa0cf919dc387954a36515e652f09a66f1532e53e0c9f2fda` | `9e78d78b9c5290f8cae2ca26e287aafd0e8db92874db0a2ba14c6832ab9c290a` | Version metadata changed from 0.1.0 to 0.1.1; no experiment logic is defined in this file. |

These changes harden future execution and analysis. They do not rewrite the archived JSONL records, derived tables, figures, or held-out decision.
