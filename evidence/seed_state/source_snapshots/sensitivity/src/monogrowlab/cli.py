"""Unified command-line entry point for MonoGrowLab experiment workflows."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


SCRIPTS = {
    "run": "run_bsds_robustness_v2.py",
    "analyze": "analyze_attribution_v2.py",
    "summarize": "summarize_results_v2.py",
    "report": "render_html_report_v2.py",
    "plot": "plot_attribution_v2.py",
}


def _is_project_root(path: Path) -> bool:
    # The optional `plot` entry point is not required: it is only demanded once
    # plotting ships, otherwise a valid checkout would reject its own root.
    return all(
        (path / relative).is_file()
        for relative in (
            "pyproject.toml",
            "experiments/run_bsds_robustness_v2.py",
            "experiments/analyze_attribution_v2.py",
            "experiments/summarize_results_v2.py",
            "experiments/render_html_report_v2.py",
        )
    )


def resolve_project_root(explicit: Path | None) -> Path:
    if explicit is not None:
        requested = explicit.expanduser().resolve()
        if _is_project_root(requested):
            return requested
        raise RuntimeError(f"not a MonoGrowLab project root: {requested}")

    candidates: list[Path] = []
    environment = os.environ.get("MONOGROWLAB_PROJECT_ROOT")
    if environment:
        requested = Path(environment).expanduser().resolve()
        if _is_project_root(requested):
            return requested
        raise RuntimeError(
            f"MONOGROWLAB_PROJECT_ROOT is not a MonoGrowLab project root: {requested}"
        )
    current = Path.cwd().resolve()
    candidates.extend((current, *current.parents))
    source_checkout = Path(__file__).resolve().parents[2]
    candidates.extend((source_checkout, *source_checkout.parents))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if _is_project_root(candidate):
            return candidate
    raise RuntimeError(
        "MonoGrowLab project root was not found. Run from the source checkout, "
        "pass --project-root, or set MONOGROWLAB_PROJECT_ROOT."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monogrowlab")
    parser.add_argument(
        "--project-root",
        type=Path,
        help="source checkout root (normally detected automatically)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run or resume a schema-v2 experiment")
    run.add_argument("--config", type=Path, required=True)

    analyze = subparsers.add_parser(
        "analyze", help="build paired attribution and inference tables"
    )
    analyze.add_argument("--input", type=Path, required=True)
    analyze.add_argument("--output-dir", type=Path, required=True)
    analyze.add_argument("--bootstrap", type=int, default=10_000)
    analyze.add_argument("--permutations", type=int, default=100_000)
    analyze.add_argument("--seed", type=int, default=20260917)
    analyze.add_argument("--primary-variant", action="append", default=[])

    summarize = subparsers.add_parser(
        "summarize", help="build descriptive paired and grouped summaries"
    )
    summarize.add_argument("--input", type=Path, required=True)
    summarize.add_argument("--output-dir", type=Path, required=True)

    report = subparsers.add_parser(
        "report", help="render a standalone HTML experiment report"
    )
    report.add_argument("--analysis-dir", type=Path, required=True)
    report.add_argument("--summary-dir", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)

    plot = subparsers.add_parser(
        "plot", help="generate publication figures from an attribution analysis"
    )
    plot.add_argument("--analysis-dir", type=Path, required=True)
    plot.add_argument("--output-dir", type=Path, required=True)
    plot.add_argument("--label", default="", help="short label used in figure titles")
    return parser


def forwarded_arguments(args: argparse.Namespace) -> list[str]:
    if args.command == "run":
        return ["--config", str(args.config)]
    if args.command == "analyze":
        forwarded = [
            "--input",
            str(args.input),
            "--output-dir",
            str(args.output_dir),
            "--bootstrap",
            str(args.bootstrap),
            "--permutations",
            str(args.permutations),
            "--seed",
            str(args.seed),
        ]
        for variant in args.primary_variant:
            forwarded.extend(("--primary-variant", variant))
        return forwarded
    if args.command == "summarize":
        return ["--input", str(args.input), "--output-dir", str(args.output_dir)]
    if args.command == "report":
        return [
            "--analysis-dir",
            str(args.analysis_dir),
            "--summary-dir",
            str(args.summary_dir),
            "--output",
            str(args.output),
        ]
    if args.command == "plot":
        forwarded = [
            "--analysis-dir",
            str(args.analysis_dir),
            "--output-dir",
            str(args.output_dir),
        ]
        if args.label:
            forwarded.extend(("--label", args.label))
        return forwarded
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        project_root = resolve_project_root(args.project_root)
    except RuntimeError as exc:
        build_parser().error(str(exc))
    script = project_root / "experiments" / SCRIPTS[args.command]
    completed = subprocess.run(
        [sys.executable, str(script), *forwarded_arguments(args)],
        cwd=project_root,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
