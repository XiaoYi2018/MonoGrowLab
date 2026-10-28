# Setup

Use Python 3.10.12 or newer. The archived supplementary runs used Python 3.13.5, NumPy 2.1.3, SciPy 1.15.3, Pillow 11.1.0 and scikit-image 0.25.0. Existing archived baseline metadata records its own environment.

From a virtual environment in the checkout, run `python -m pip install -e ".[test,analysis]"`. Installation and dataset preparation commands are in README.md. Raw BSDS500 data must be fetched separately; the per-file manifest verifies all 1,000 declared images and annotations.

For analysis of shipped records, no dataset download or segmentation run is required. Run the commands in docs/SEED_STATE_ANALYSES.md with new output directories. A new segmentation run requires the data and an unused output path. Archived outputs are immutable and are not resumed by a newer source tree.

With the virtual environment activated, run `python apps\local-web-v0.1\server.py --project-root . --open-browser` from the checkout after dataset preparation. The existing one-click launcher uses the registered Python 3.13 interpreter and its dependencies. The command-line workflow also supports Linux and macOS; the one-click launcher is Windows-specific.
