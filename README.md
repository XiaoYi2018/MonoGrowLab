# MonoGrowLab

MonoGrowLab is a reproducible workbench for separating seed-instability effects from growth-stage effects in seeded region-growing segmentation under image corruption.

For each corrupted image, algorithm, parameter set, and random realization, the workbench evaluates two paired modes:

- `fixed_clean`: seeds are extracted from the clean image and reused on its corrupted counterpart;
- `recomputed`: seeds are extracted again from the corrupted image.

Their paired difference, `delta_stability_ari`, is the seed-attribution gap. The same records also retain agreement with human reference segmentations, allowing stability and segmentation quality to be inspected together.

## Highlights

- Five deterministic corruption families with explicit units: Gaussian noise, Gaussian blur, salt-and-pepper noise, JPEG compression, and multiplicative brightness scaling.
- Matched corruption realizations across seed policies, verified by clean- and corrupted-image hashes.
- A fail-closed schema that rejects missing, duplicated, failed, or hash-inconsistent pairs.
- Dataset manifests with byte sizes and SHA-256 hashes for every input image and reference segmentation.
- Resumable experiment execution with immutable configuration, dependency, source, and manifest checks.
- Image-level paired bootstrap intervals, sign-flip permutation tests, and Holm correction within each corruption family.
- CSV, SVG/PDF/PNG, and standalone HTML outputs.
- A loopback-only local web workbench for configuring exploratory evaluations and inspecting their results.

## Requirements

- Python 3.10.12 or newer; Python 3.13 is used for the archived results.
- Windows, Linux, or macOS for the command-line workflow. The included one-click web launcher targets Windows; the server itself is Python-based.
- The BSDS500 dataset for the supplied benchmark configurations. Raw BSDS500 images are not redistributed.

## Installation

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test,analysis]"
```

On Linux or macOS, replace the activation command with `source .venv/bin/activate` and use `python3` where appropriate.

## Dataset setup

```powershell
python experiments\fetch_bsds500.py --project-root .
python experiments\build_bsds500_file_manifest.py `
  --dataset-root data\raw\BSDS500_official_2013\BSR\BSDS500\data `
  --source-manifest data\manifests\bsds500_official_2013.json `
  --output data\manifests\bsds500_official_2013_files_v2.json
```

The download URL and archive checksum are recorded in `data/manifests/bsds500_official_2013.json`. The runner verifies the per-file manifest before starting a schema-v2 experiment.

## Command-line workflow

The archived configurations point to immutable published outputs. Copy a configuration and assign a new output path before re-execution:

```powershell
Copy-Item configs\bsds500_multicorruption_v2_smoke_2x96_r2.json configs\local_smoke.json
# In configs\local_smoke.json, set "output" to "experiments/runs/local_smoke.jsonl".
monogrowlab run --config configs\local_smoke.json
```

Running an archived configuration against its archived output is an integrity check: the runner intentionally refuses to resume when the current package differs from the recorded package. See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) and [`docs/ARCHIVED_RUN_PROVENANCE.md`](docs/ARCHIVED_RUN_PROVENANCE.md).

Build the paired analysis, descriptive summary, HTML report, and figures:

```powershell
monogrowlab analyze `
  --input experiments\runs\bsds500_multicorruption_v2_smoke_2x96_r2.jsonl `
  --output-dir reports\generated\smoke-attribution

monogrowlab summarize `
  --input experiments\runs\bsds500_multicorruption_v2_smoke_2x96_r2.jsonl `
  --output-dir reports\generated\smoke-summary

monogrowlab report `
  --analysis-dir reports\generated\smoke-attribution `
  --summary-dir reports\generated\smoke-summary `
  --output reports\generated\smoke-report.html

monogrowlab plot `
  --analysis-dir reports\generated\smoke-attribution `
  --output-dir reports\generated\smoke-figures `
  --label "Smoke evaluation"
```

Run `monogrowlab --help` to list all commands.

## Local web workbench

After installing the package and preparing BSDS500, double-click:

```text
apps\local-web-v0.1\start.cmd
```

The launcher opens `http://127.0.0.1:8767/`. The interface creates isolated exploratory jobs under `ui_runs/`, calls the same schema-v2 runner and analysis scripts as the CLI, and exposes the exact configuration and output tables. It binds only to loopback and is not intended for public hosting. See `apps/local-web-v0.1/README.md` for scope and security details.

## Archived experiment configurations

| Stage | Configuration | Expected records |
|---|---|---:|
| Validation, primary policies | `configs/bsds500_multicorruption_v2_validation_10x160_r2.json` | 1,160 |
| Validation, raw strict-extrema sensitivity | `configs/bsds500_multicorruption_v2_validation_10x160_strict_sensitivity_r1.json` | 1,160 |
| Held-out test split | `configs/bsds500_multicorruption_v2_test_200x160_r1.json` | 23,200 |

The corresponding run records and derived tables are included under `experiments/runs/` and `reports/generated/`. See `docs/REPRODUCIBILITY.md` for the artifact map and verification commands.

The held-out decision rule was frozen before the test split was inspected. The public pre-registration, freeze ledger, and acceptance record are provided in [`docs/PREREGISTRATION.md`](docs/PREREGISTRATION.md), [`docs/test_split_freeze.json`](docs/test_split_freeze.json), and [`docs/heldout_acceptance.json`](docs/heldout_acceptance.json).

## Tests

```powershell
python -m pytest -q -p no:cacheprovider
Push-Location apps\local-web-v0.1
python -m unittest test_server -v
Pop-Location
```

The current release contains 58 core tests and 15 web-workbench tests.

## Repository structure

- `src/monogrowlab/`: package code, schemas, metrics, corruption operators, reporting, and CLI.
- `legacy_reference/core/`: project-owned region-growing kernels used by the adapter layer.
- `experiments/`: reproducible runners, analyzers, report generation, and archived run records.
- `configs/`: versioned benchmark configurations.
- `apps/local-web-v0.1/`: local browser interface.
- `tests/`: unit, security-boundary, and invariant tests.
- `data/manifests/`: dataset provenance and per-file integrity manifests.
- `reports/generated/`: archived analysis tables, summaries, and HTML reports.
- `paper/figures/`: figure-generation code and publication graphics.
- `docs/`: analysis, corruption, metric, pre-registration, provenance, and reproducibility protocols.

## Data and citation

BSDS500 remains governed by its original distribution terms and is not redistributed here. Derived tables and figures are project outputs. If you use MonoGrowLab, cite the accompanying SoftwareX article after publication and the method and dataset sources cited there.

## License

MonoGrowLab is released under the MIT License. See [`LICENSE`](LICENSE).
