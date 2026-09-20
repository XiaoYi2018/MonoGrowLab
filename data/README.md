# Data

This repository contains manifests and derived results; it does not redistribute BSDS500 images.

- `manifests/bsds500_official_2013.json` records the official download URL and archive SHA-256.
- `manifests/bsds500_official_2013_files_v2.json` records the byte size and SHA-256 of every image and human-reference file consumed by the benchmark.
- Raw images are downloaded by `experiments/fetch_bsds500.py` and remain subject to the original BSDS500 terms.
- Derived run records, tables, figures, and reports are under `experiments/runs/`, `reports/generated/`, and `paper/figures/`.

