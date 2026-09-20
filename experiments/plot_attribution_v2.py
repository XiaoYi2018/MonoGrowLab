"""Deterministic figures for a completed paired-attribution analysis directory.

Reads `inference.csv` and `analysis_metadata.json` produced by
`analyze_attribution_v2.py` and writes editable vector figures plus a provenance
manifest. No numbers are hard-coded: every value comes from the CSV.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
import numpy as np  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLOT_METRIC = "delta_stability_ari"
GT_METRIC = "delta_gt_ari_mean"
REQUIRED_COLUMNS = frozenset(
    {
        "variant",
        "corruption_family",
        "stratum",
        "metric",
        "mean",
        "ci95_low",
        "ci95_high",
        "sign_flip_p",
        "holm_p",
    }
)
EXPECTED_PRIMARY_VARIANTS = 4
EXPECTED_FAMILIES = 5


@dataclass(frozen=True)
class PlotData:
    rows: list[dict[str, str]]
    variants: list[str]
    families: list[str]
    severity_order: dict[str, list[str]]
    context: dict[str, Any]
    config_path: Path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, columns


def family_rows(rows: list[dict[str, str]], metric: str) -> list[dict[str, str]]:
    return [r for r in rows if r["stratum"] == "family" and r["metric"] == metric]


def severity_rows(rows: list[dict[str, str]], metric: str) -> list[dict[str, str]]:
    return [r for r in rows if r["stratum"].startswith("severity=") and r["metric"] == metric]


def significant(row: dict[str, str]) -> bool:
    holm = row.get("holm_p") or ""
    if holm == "":
        return False
    return float(holm) < 0.05


def raw_significant(row: dict[str, str]) -> bool:
    return float(row["sign_flip_p"]) < 0.05


def canonical_hash(value: Any) -> str:
    serialized = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _unique_nonempty_strings(values: Iterable[Any], label: str) -> list[str]:
    result = [str(value) for value in values]
    if not result or any(value == "" for value in result):
        raise ValueError(f"{label} must be a non-empty list of non-empty strings")
    if len(result) != len(set(result)):
        raise ValueError(f"{label} contains duplicate values: {result}")
    return result


def _index_unique(
    rows: list[dict[str, str]], key_fields: tuple[str, ...], label: str
) -> dict[tuple[str, ...], dict[str, str]]:
    indexed: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key in indexed:
            raise ValueError(f"duplicate {label} cell: {key}")
        indexed[key] = row
    return indexed


def _finite_float(row: dict[str, str], field: str, key: tuple[str, ...]) -> float:
    try:
        value = float(row[field])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric {field} for cell {key}: {row[field]!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"non-finite {field} for cell {key}: {row[field]!r}")
    return value


def _resolve_config(metadata: dict[str, Any]) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    context = metadata.get("run_context")
    if not isinstance(context, dict):
        raise ValueError("analysis_metadata.json must contain a run_context object")
    relative = context.get("config_path")
    if not isinstance(relative, str) or not relative:
        raise ValueError("run_context.config_path must be a non-empty string")
    config_path = (PROJECT_ROOT / relative).resolve()
    try:
        config_path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"configuration path escapes project root: {relative}") from exc
    if not config_path.is_file():
        raise FileNotFoundError(f"configuration file is missing: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_hash = context.get("config_sha256")
    actual_hash = canonical_hash(config)
    if expected_hash not in {None, ""} and expected_hash != actual_hash:
        raise ValueError(
            "configuration canonical SHA-256 differs from analysis metadata: "
            f"{actual_hash} != {expected_hash}"
        )
    return config_path, config, context


def load_plot_data(analysis: Path) -> PlotData:
    inference = analysis / "inference.csv"
    metadata_path = analysis / "analysis_metadata.json"
    if not inference.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(
            "analysis directory must contain inference.csv and analysis_metadata.json"
        )

    rows, columns = read_rows(inference)
    missing_columns = sorted(REQUIRED_COLUMNS - set(columns))
    if missing_columns:
        raise ValueError(
            "inference.csv is missing required columns: " + ", ".join(missing_columns)
        )
    if not rows:
        raise ValueError("inference.csv contains no data rows")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    variants = _unique_nonempty_strings(
        metadata.get("primary_variants", []), "primary_variants"
    )
    if len(variants) != EXPECTED_PRIMARY_VARIANTS:
        raise ValueError(
            f"expected {EXPECTED_PRIMARY_VARIANTS} primary variants, found {len(variants)}"
        )

    config_path, config, context = _resolve_config(metadata)
    configured_variants = {
        str(item.get("id"))
        for item in config.get("variants", [])
        if isinstance(item, dict) and item.get("id") not in {None, ""}
    }
    unknown_variants = sorted(set(variants) - configured_variants)
    if unknown_variants:
        raise ValueError(
            "primary variants are absent from the recorded configuration: "
            + ", ".join(unknown_variants)
        )

    corruptions = config.get("corruptions")
    if not isinstance(corruptions, list):
        raise ValueError("configuration must contain a corruptions list")
    families: list[str] = []
    severity_order: dict[str, list[str]] = {}
    for corruption in corruptions:
        if not isinstance(corruption, dict):
            raise ValueError("each configured corruption must be an object")
        family = str(corruption.get("family", ""))
        if not family:
            raise ValueError("configured corruption family must be non-empty")
        if family in severity_order:
            raise ValueError(f"duplicate configured corruption family: {family}")
        severity_items = corruption.get("severities")
        if not isinstance(severity_items, list):
            raise ValueError(f"configured severities must be a list for family {family}")
        severities = _unique_nonempty_strings(
            [item.get("id", "") if isinstance(item, dict) else "" for item in severity_items],
            f"configured severities for family {family}",
        )
        families.append(family)
        severity_order[family] = severities
    if len(families) != EXPECTED_FAMILIES:
        raise ValueError(
            f"expected {EXPECTED_FAMILIES} configured corruption families, found {len(families)}"
        )

    metric_rows = [row for row in rows if row["metric"] == PLOT_METRIC]
    unexpected_strata = sorted(
        {
            row["stratum"]
            for row in metric_rows
            if row["stratum"] != "family" and not row["stratum"].startswith("severity=")
        }
    )
    if unexpected_strata:
        raise ValueError(
            f"unexpected strata for {PLOT_METRIC}: {unexpected_strata}"
        )
    family_data = [row for row in metric_rows if row["stratum"] == "family"]
    severity_data = [row for row in metric_rows if row["stratum"].startswith("severity=")]

    family_index = _index_unique(
        family_data, ("variant", "corruption_family"), "family-level"
    )
    expected_family_keys = {
        (variant, family) for variant in variants for family in families
    }
    actual_family_keys = set(family_index)
    if len(family_data) != EXPECTED_PRIMARY_VARIANTS * EXPECTED_FAMILIES:
        raise ValueError(
            "family-level row count mismatch: expected "
            f"{EXPECTED_PRIMARY_VARIANTS * EXPECTED_FAMILIES}, found {len(family_data)}"
        )
    if actual_family_keys != expected_family_keys:
        missing = sorted(expected_family_keys - actual_family_keys)
        unexpected = sorted(actual_family_keys - expected_family_keys)
        raise ValueError(
            f"family-level cells do not match variant × family grid; missing={missing}, "
            f"unexpected={unexpected}"
        )

    gt_metric_rows = [row for row in rows if row["metric"] == GT_METRIC]
    gt_unexpected_strata = sorted(
        {
            row["stratum"]
            for row in gt_metric_rows
            if row["stratum"] != "family"
            and not row["stratum"].startswith("severity=")
        }
    )
    if gt_unexpected_strata:
        raise ValueError(f"unexpected strata for {GT_METRIC}: {gt_unexpected_strata}")
    gt_family_data = [row for row in gt_metric_rows if row["stratum"] == "family"]
    gt_family_index = _index_unique(
        gt_family_data, ("variant", "corruption_family"), "GT family-level"
    )
    actual_gt_family_keys = set(gt_family_index)
    if len(gt_family_data) != EXPECTED_PRIMARY_VARIANTS * EXPECTED_FAMILIES:
        raise ValueError(
            "GT family-level row count mismatch: expected "
            f"{EXPECTED_PRIMARY_VARIANTS * EXPECTED_FAMILIES}, "
            f"found {len(gt_family_data)}"
        )
    if actual_gt_family_keys != expected_family_keys:
        missing = sorted(expected_family_keys - actual_gt_family_keys)
        unexpected = sorted(actual_gt_family_keys - expected_family_keys)
        raise ValueError(
            "GT family-level cells do not match variant × family grid; "
            f"missing={missing}, unexpected={unexpected}"
        )

    severity_index: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in severity_data:
        severity = row["stratum"].split("=", 1)[1]
        key = (row["variant"], row["corruption_family"], severity)
        if key in severity_index:
            raise ValueError(f"duplicate severity-level cell: {key}")
        severity_index[key] = row
    expected_severity_keys = {
        (variant, family, severity)
        for variant in variants
        for family in families
        for severity in severity_order[family]
    }
    actual_severity_keys = set(severity_index)
    expected_severity_rows = EXPECTED_PRIMARY_VARIANTS * sum(
        len(severity_order[family]) for family in families
    )
    if len(severity_data) != expected_severity_rows:
        raise ValueError(
            "severity-level row count mismatch: expected "
            f"{expected_severity_rows}, found {len(severity_data)}"
        )
    if actual_severity_keys != expected_severity_keys:
        missing = sorted(expected_severity_keys - actual_severity_keys)
        unexpected = sorted(actual_severity_keys - expected_severity_keys)
        raise ValueError(
            "severity-level cells do not match configured variant × family × severity grid; "
            f"missing={missing}, unexpected={unexpected}"
        )

    for key, row in family_index.items():
        mean = _finite_float(row, "mean", key)
        low = _finite_float(row, "ci95_low", key)
        high = _finite_float(row, "ci95_high", key)
        if low > mean or mean > high:
            raise ValueError(f"invalid confidence interval for family-level cell {key}")
        if row["holm_p"] != "":
            holm = _finite_float(row, "holm_p", key)
            if not 0.0 <= holm <= 1.0:
                raise ValueError(f"Holm p is outside [0, 1] for family-level cell {key}")
    for key, row in gt_family_index.items():
        mean = _finite_float(row, "mean", key)
        low = _finite_float(row, "ci95_low", key)
        high = _finite_float(row, "ci95_high", key)
        if low > mean or mean > high:
            raise ValueError(f"invalid confidence interval for GT family-level cell {key}")
        raw_p = _finite_float(row, "sign_flip_p", key)
        if not 0.0 <= raw_p <= 1.0:
            raise ValueError(
                f"sign-flip p is outside [0, 1] for GT family-level cell {key}"
            )
    for key, row in severity_index.items():
        _finite_float(row, "mean", key)

    return PlotData(
        rows=rows,
        variants=variants,
        families=families,
        severity_order=severity_order,
        context=context,
        config_path=config_path,
    )


def _family_metric_index(
    rows: list[dict[str, str]], metric: str
) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (row["variant"], row["corruption_family"]): row
        for row in family_rows(rows, metric)
    }


def _family_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return _family_metric_index(rows, PLOT_METRIC)


def _severity_index(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (
            row["variant"],
            row["corruption_family"],
            row["stratum"].split("=", 1)[1],
        ): row
        for row in severity_rows(rows, PLOT_METRIC)
    }


def _vector_colorbar(ax: Any, cmap: Any, norm: Normalize, label: str) -> None:
    colorbar_ax = ax.inset_axes([1.04, 0.08, 0.035, 0.84])
    edges = np.linspace(float(norm.vmin), float(norm.vmax), 65)
    for low, high in zip(edges[:-1], edges[1:]):
        colorbar_ax.add_patch(
            Rectangle(
                (0.0, low),
                1.0,
                high - low,
                facecolor=cmap(norm((low + high) / 2.0)),
                edgecolor="none",
            )
        )
    colorbar_ax.set_xlim(0.0, 1.0)
    colorbar_ax.set_ylim(float(norm.vmin), float(norm.vmax))
    colorbar_ax.set_xticks([])
    colorbar_ax.yaxis.tick_right()
    colorbar_ax.yaxis.set_label_position("right")
    colorbar_ax.set_ylabel(label, fontsize=8)
    colorbar_ax.tick_params(axis="y", labelsize=7)


def figure_family_gap(
    rows: list[dict[str, str]],
    variants: list[str],
    families: list[str],
    out: Path,
    title: str,
) -> Path:
    indexed = _family_index(rows)
    positions = np.arange(len(families))
    width = 0.8 / max(len(variants), 1)
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for index, variant in enumerate(variants):
        means, lows, highs, marks = [], [], [], []
        for family in families:
            match = indexed[(variant, family)]
            means.append(float(match["mean"]))
            lows.append(float(match["ci95_low"]))
            highs.append(float(match["ci95_high"]))
            marks.append("*" if significant(match) else "")
        offset = (index - (len(variants) - 1) / 2) * width
        bars = ax.bar(
            positions + offset,
            means,
            width,
            label=variant,
            yerr=[
                np.array(means) - np.array(lows),
                np.array(highs) - np.array(means),
            ],
            capsize=2,
            error_kw={"lw": 0.8},
            color=plt.get_cmap("tab20")(index % 20),
            edgecolor="black",
            linewidth=0.3,
        )
        for bar, mark in zip(bars, marks):
            if mark:
                ax.annotate(
                    mark,
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    textcoords="offset points",
                    xytext=(0, 3 if bar.get_height() >= 0 else -10),
                    ha="center",
                    fontsize=10,
                )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(positions)
    ax.set_xticklabels([f.replace("_", "\n") for f in families], fontsize=8)
    ax.set_ylabel("Seed-attribution gap\n($\\Delta$ stability ARI)", fontsize=9)
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=7, frameon=False, ncol=2)
    ax.tick_params(axis="y", labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    return save(fig, out)


def _context_image_count(context: dict[str, Any], label: str) -> int:
    value = context.get("image_count")
    if isinstance(value, bool):
        raise ValueError(f"{label} image_count must be a positive integer")
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} image_count must be a positive integer") from exc
    if count <= 0 or str(value) not in {str(count), f"{count}.0"}:
        raise ValueError(f"{label} image_count must be a positive integer")
    return count


def _split_panel_label(
    context: dict[str, Any], label: str, explicit_role_label: str = ""
) -> str:
    split = str(context.get("split", "")).strip()
    if not split:
        raise ValueError(f"{label} run_context.split must be non-empty")
    names = {"val": "Validation subset", "test": "Held-out test split"}
    role_label = explicit_role_label.strip()
    if not role_label:
        role = str(context.get("analysis_role", "")).strip()
        if not role:
            raise ValueError(
                f"{label} run_context.analysis_role is absent; provide an explicit role label"
            )
        role_names = {
            "primary": "primary Gaussian-smoothed seed policy",
            "secondary_sensitivity": "raw strict-extrema sensitivity policy",
        }
        role_label = role_names.get(role, role.replace("_", " "))
    return (
        f"{names.get(split, split.replace('_', ' ').title())} "
        f"(n = {_context_image_count(context, label)})\n{role_label}"
    )


def validate_two_split_data(left: PlotData, right: PlotData) -> None:
    if left.variants != right.variants:
        raise ValueError(
            "two-split primary variant order differs: "
            f"left={left.variants}, right={right.variants}"
        )
    if left.families != right.families:
        raise ValueError(
            "two-split corruption family order differs: "
            f"left={left.families}, right={right.families}"
        )
    left_split = str(left.context.get("split", "")).strip()
    right_split = str(right.context.get("split", "")).strip()
    if not left_split or not right_split:
        raise ValueError("two-split inputs must record non-empty split names")
    if left_split == right_split:
        raise ValueError(f"two-split inputs record the same split: {left_split}")
    _context_image_count(left.context, "left")
    _context_image_count(right.context, "right")


def _draw_family_gap_panel(
    ax: Any,
    rows: list[dict[str, str]],
    variants: list[str],
    families: list[str],
    panel_title: str,
) -> None:
    indexed = _family_index(rows)
    positions = np.arange(len(families))
    width = 0.8 / max(len(variants), 1)
    for index, variant in enumerate(variants):
        means, lows, highs, marks = [], [], [], []
        for family in families:
            match = indexed[(variant, family)]
            means.append(float(match["mean"]))
            lows.append(float(match["ci95_low"]))
            highs.append(float(match["ci95_high"]))
            marks.append("*" if significant(match) else "")
        offset = (index - (len(variants) - 1) / 2) * width
        bars = ax.bar(
            positions + offset,
            means,
            width,
            label=variant,
            yerr=[
                np.array(means) - np.array(lows),
                np.array(highs) - np.array(means),
            ],
            capsize=2,
            error_kw={"lw": 0.8},
            color=plt.get_cmap("tab20")(index % 20),
            edgecolor="black",
            linewidth=0.3,
        )
        for bar, mark in zip(bars, marks):
            if mark:
                ax.annotate(
                    mark,
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    textcoords="offset points",
                    xytext=(0, 3 if bar.get_height() >= 0 else -10),
                    ha="center",
                    fontsize=10,
                )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(positions)
    ax.set_xticklabels([f.replace("_", "\n") for f in families], fontsize=8)
    ax.set_title(panel_title, fontsize=10)
    ax.tick_params(axis="y", labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def figure_family_gap_two_split(
    left: PlotData,
    right: PlotData,
    out: Path,
    title: str,
    left_role_label: str = "",
    right_role_label: str = "",
) -> Path:
    validate_two_split_data(left, right)
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 3.8), sharey=True)
    _draw_family_gap_panel(
        axes[0],
        left.rows,
        left.variants,
        left.families,
        _split_panel_label(left.context, "left", left_role_label),
    )
    _draw_family_gap_panel(
        axes[1],
        right.rows,
        right.variants,
        right.families,
        _split_panel_label(right.context, "right", right_role_label),
    )
    axes[0].set_ylabel("Seed-attribution gap\n($\\Delta$ stability ARI)", fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        fontsize=7,
        frameon=False,
        ncol=len(left.variants),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.005),
    )
    fig.suptitle(
        title + "\n(* = Holm-corrected p < 0.05 within the family)", fontsize=10
    )
    fig.tight_layout(rect=(0.0, 0.10, 1.0, 0.91))
    return save(fig, out)


def figure_severity(
    rows: list[dict[str, str]],
    variants: list[str],
    families: list[str],
    severity_order: dict[str, list[str]],
    out: Path,
    title: str,
) -> Path:
    indexed = _severity_index(rows)
    fig, axes = plt.subplots(
        1, len(families), figsize=(2.6 * len(families), 2.8), sharey=True
    )
    if len(families) == 1:
        axes = [axes]
    for ax, family in zip(axes, families):
        severities = severity_order[family]
        for index, variant in enumerate(variants):
            means = []
            for severity in severities:
                match = indexed[(variant, family, severity)]
                means.append(float(match["mean"]))
            ax.plot(
                range(len(severities)),
                means,
                marker="o",
                markersize=3,
                linewidth=1.2,
                label=variant,
                color=plt.get_cmap("tab20")(index % 20),
            )
        ax.axhline(0, color="black", linewidth=0.7)
        ax.set_xticks(range(len(severities)))
        ax.set_xticklabels(severities, rotation=30, ha="right", fontsize=7)
        ax.set_title(family.replace("_", " "), fontsize=8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
    axes[0].set_ylabel("$\\Delta$ stability ARI", fontsize=8)
    axes[0].legend(fontsize=6, frameon=False)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    return save(fig, out)


def figure_heatmap(
    rows: list[dict[str, str]],
    variants: list[str],
    families: list[str],
    out: Path,
    title: str,
) -> Path:
    indexed = _family_index(rows)
    matrix = np.empty((len(variants), len(families)), dtype=float)
    for i, variant in enumerate(variants):
        for j, family in enumerate(families):
            matrix[i, j] = float(indexed[(variant, family)]["mean"])
    limit = max(float(np.max(np.abs(matrix))), np.finfo(float).eps)
    norm = Normalize(vmin=-limit, vmax=limit)
    cmap = plt.get_cmap("RdBu_r")
    fig, ax = plt.subplots(
        figsize=(1.35 * len(families) + 2.2, 0.5 * len(variants) + 1.8)
    )
    for i, variant in enumerate(variants):
        for j, family in enumerate(families):
            value = matrix[i, j]
            ax.add_patch(
                Rectangle(
                    (j, i),
                    1.0,
                    1.0,
                    facecolor=cmap(norm(value)),
                    edgecolor="white",
                    linewidth=0.8,
                )
            )
            match = indexed[(variant, family)]
            text = f"{value:+.2f}" + ("*" if significant(match) else "")
            ax.text(
                j + 0.5,
                i + 0.5,
                text,
                ha="center",
                va="center",
                fontsize=7,
                color="black" if abs(value) < 0.6 * limit else "white",
            )
    ax.set_xlim(0, len(families))
    ax.set_ylim(len(variants), 0)
    ax.set_aspect("auto")
    ax.set_xticks(np.arange(len(families)) + 0.5)
    ax.set_xticklabels([f.replace("_", "\n") for f in families], fontsize=8)
    ax.set_yticks(np.arange(len(variants)) + 0.5)
    ax.set_yticklabels(variants, fontsize=8)
    ax.set_title(title + "\n(* = Holm-corrected p < 0.05 within the family)", fontsize=9)
    _vector_colorbar(ax, cmap, norm, "$\\Delta$ stability ARI")
    fig.tight_layout()
    return save(fig, out)


def figure_gt_contrast(
    rows: list[dict[str, str]],
    variants: list[str],
    families: list[str],
    out: Path,
    title: str,
) -> Path:
    stability = _family_metric_index(rows, PLOT_METRIC)
    human = _family_metric_index(rows, GT_METRIC)
    markers = ["o", "s", "^", "D"]
    family_colors = {
        family: plt.get_cmap("tab10")(index % 10)
        for index, family in enumerate(families)
    }
    fig, ax = plt.subplots(figsize=(7.3, 4.8))
    for variant_index, variant in enumerate(variants):
        for family in families:
            key = (variant, family)
            x_row = stability[key]
            y_row = human[key]
            x = float(x_row["mean"])
            y = float(y_row["mean"])
            xerr = np.array(
                [[x - float(x_row["ci95_low"])], [float(x_row["ci95_high"]) - x]]
            )
            yerr = np.array(
                [[y - float(y_row["ci95_low"])], [float(y_row["ci95_high"]) - y]]
            )
            color = family_colors[family]
            ax.errorbar(
                x,
                y,
                xerr=xerr,
                yerr=yerr,
                fmt=markers[variant_index],
                markersize=5.5,
                markerfacecolor=color,
                markeredgecolor="black",
                markeredgewidth=0.5,
                ecolor=color,
                elinewidth=0.75,
                capsize=2,
                alpha=0.9,
            )
            mark = ("*" if significant(x_row) else "") + (
                "†" if raw_significant(y_row) else ""
            )
            if mark:
                ax.annotate(
                    mark,
                    (x, y),
                    textcoords="offset points",
                    xytext=(4, 4),
                    fontsize=7,
                )
    ax.axvline(0, color="0.35", linewidth=0.7, linestyle="--")
    ax.axhline(0, color="0.35", linewidth=0.7, linestyle="--")
    ax.set_xlabel("Seed-attribution gap ($\\Delta$ stability ARI)", fontsize=9)
    ax.set_ylabel("Human-reference contrast ($\\Delta$ GT ARI)", fontsize=9)
    ax.set_title(
        title
        + "\n(* stability: Holm p < 0.05; † human reference: raw sign-flip p < 0.05)",
        fontsize=9,
    )
    variant_handles = [
        Line2D(
            [0],
            [0],
            marker=markers[index],
            color="none",
            markerfacecolor="0.75",
            markeredgecolor="black",
            markersize=5.5,
            label=variant,
        )
        for index, variant in enumerate(variants)
    ]
    family_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=family_colors[family],
            markeredgecolor="black",
            markersize=5.5,
            label=family,
        )
        for family in families
    ]
    first_legend = ax.legend(
        handles=variant_handles,
        title="Variant (marker)",
        fontsize=6.5,
        title_fontsize=7,
        frameon=False,
        loc="upper left",
    )
    ax.add_artist(first_legend)
    ax.legend(
        handles=family_handles,
        title="Corruption family (color)",
        fontsize=6.5,
        title_fontsize=7,
        frameon=False,
        loc="lower right",
    )
    ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    return save(fig, out)


def save(fig, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".pdf", ".svg"):
        fig.savefig(out.with_suffix(suffix), dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out.with_suffix(".pdf")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Figures for a paired-attribution analysis directory"
    )
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument(
        "--heldout-analysis-dir",
        type=Path,
        help="optional second split used for the shared-axis family-gap panel",
    )
    parser.add_argument(
        "--analysis-role-label",
        default="",
        help="explicit policy label for the left split when metadata lacks analysis_role",
    )
    parser.add_argument(
        "--heldout-role-label",
        default="",
        help="optional explicit policy label for the held-out split",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    analysis = args.analysis_dir.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to merge into existing directory: {output}")
    inference = analysis / "inference.csv"
    metadata_path = analysis / "analysis_metadata.json"
    plot_data = load_plot_data(analysis)
    heldout_analysis = (
        args.heldout_analysis_dir.resolve() if args.heldout_analysis_dir else None
    )
    heldout_data = load_plot_data(heldout_analysis) if heldout_analysis else None
    if heldout_data is not None:
        validate_two_split_data(plot_data, heldout_data)
    rows = plot_data.rows
    variants = plot_data.variants
    families = plot_data.families
    context = plot_data.context
    label = args.label or str(context.get("analysis_role", "analysis"))
    title_prefix = (
        f"{label}: {context.get('split', '')} split, "
        f"{context.get('image_count', '')} images"
    )

    output.mkdir(parents=True, exist_ok=True)
    produced = [
        figure_family_gap(
            rows,
            variants,
            families,
            output / "fig_family_gap",
            f"{title_prefix} — family-level gap",
        ),
        figure_severity(
            rows,
            variants,
            families,
            plot_data.severity_order,
            output / "fig_severity_trends",
            f"{title_prefix} — severity trends",
        ),
        figure_heatmap(
            rows,
            variants,
            families,
            output / "fig_gap_heatmap",
            f"{title_prefix} — family × variant gap",
        ),
        figure_gt_contrast(
            rows,
            variants,
            families,
            output / "fig_gt_contrast",
            f"{title_prefix} — stability gap vs human-reference contrast",
        ),
    ]
    if heldout_data is not None and heldout_analysis is not None:
        produced.append(
            figure_family_gap_two_split(
                plot_data,
                heldout_data,
                output / "fig_family_gap_two_split",
                f"{label}: family-level gap across splits",
                args.analysis_role_label,
                args.heldout_role_label,
            )
        )
    manifest = {
        "analysis_dir": str(analysis),
        "inference_csv_sha256": file_hash(inference),
        "analysis_metadata_sha256": file_hash(metadata_path),
        "primary_variants": variants,
        "family_order": families,
        "severity_order": plot_data.severity_order,
        "figures": [str(p) for p in produced],
        "formats": [".png", ".pdf", ".svg"],
        "heatmap_rendering": "editable vector rectangles",
        "gt_contrast": {
            "x_metric": PLOT_METRIC,
            "x_axis": "family-level mean seed-attribution gap in stability ARI",
            "x_significance": "Holm-adjusted p < 0.05",
            "y_metric": GT_METRIC,
            "y_axis": "family-level mean human-reference contrast in GT ARI",
            "y_significance": "raw two-sided sign-flip p < 0.05",
            "point_count": len(variants) * len(families),
            "source_inference_csv_sha256": file_hash(inference),
            "rendering": "editable vector markers and error bars",
        },
    }
    if heldout_data is not None and heldout_analysis is not None:
        heldout_inference = heldout_analysis / "inference.csv"
        heldout_metadata = heldout_analysis / "analysis_metadata.json"
        manifest["two_split_family_gap"] = {
            "figure": str(output / "fig_family_gap_two_split.pdf"),
            "left": {
                "split": str(context.get("split", "")),
                "image_count": _context_image_count(context, "left"),
                "inference_csv_sha256": file_hash(inference),
                "analysis_metadata_sha256": file_hash(metadata_path),
                "policy_label": args.analysis_role_label
                or str(context.get("analysis_role", "")),
            },
            "right": {
                "split": str(heldout_data.context.get("split", "")),
                "image_count": _context_image_count(heldout_data.context, "right"),
                "inference_csv_sha256": file_hash(heldout_inference),
                "analysis_metadata_sha256": file_hash(heldout_metadata),
                "policy_label": args.heldout_role_label
                or str(heldout_data.context.get("analysis_role", "")),
            },
            "shared_y_axis": True,
            "confidence_intervals": "image-level bootstrap 95% CI",
            "significance": "Holm-adjusted p < 0.05 within each corruption family",
            "rendering": "editable vector bars and error bars",
        }
    (output / "figures_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
