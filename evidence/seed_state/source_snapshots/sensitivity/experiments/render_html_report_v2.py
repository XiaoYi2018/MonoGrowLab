"""Render a standalone HTML report from v2 analysis and summary directories."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from monogrowlab.reporting import render_html  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--summary-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    analysis = args.analysis_dir.resolve()
    summary = args.summary_dir.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite HTML report: {output}")
    metadata = json.loads(
        (analysis / "analysis_metadata.json").read_text(encoding="utf-8")
    )
    context = metadata.get("run_context")
    if not isinstance(context, dict):
        raise RuntimeError(
            "analysis metadata lacks run_context; rerun analyze_attribution_v2.py "
            "with the current analysis code"
        )
    primary_variants = metadata.get("primary_variants")
    if not isinstance(primary_variants, list) or not all(
        isinstance(item, str) and item for item in primary_variants
    ):
        raise RuntimeError(
            "analysis metadata lacks a valid primary_variants list; rerun "
            "analyze_attribution_v2.py with the current analysis code"
        )
    document = render_html(
        context,
        read_csv(analysis / "inference.csv"),
        read_csv(summary / "paired_attribution.csv"),
        read_csv(summary / "group_summary.csv"),
        primary_variants,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(document)
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"output": str(output), "bytes": output.stat().st_size}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
