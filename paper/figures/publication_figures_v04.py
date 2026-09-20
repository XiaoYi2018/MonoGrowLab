"""Publication-sized MonoGrowLab result figures for manuscript v0.4.

The script reads validated analysis outputs through ``plot_attribution_v2``.
It changes layout and typography only; no measured value is embedded here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
import numpy as np  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_PATH = PROJECT_ROOT / "experiments" / "plot_attribution_v2.py"


def load_pipeline():
    spec = importlib.util.spec_from_file_location("plot_attribution_v2", PIPELINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load plotting pipeline: {PIPELINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save(fig, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".pdf", ".svg", ".png"):
        fig.savefig(out.with_suffix(suffix), dpi=300, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def display(text: str) -> str:
    return text.replace("_", " ").replace("gaussian1", "G1")


def family_label(text: str) -> str:
    return text.replace("_", "\n")


def severity_label(text: str) -> str:
    return re.sub(r"(?<=\d)p(?=\d)", ".", text.replace("_", " "))


def family_index(module, rows, metric):
    return {
        (row["variant"], row["corruption_family"]): row
        for row in module.family_rows(rows, metric)
    }


def draw_gap_panel(module, ax, data, title: str) -> None:
    indexed = family_index(module, data.rows, module.PLOT_METRIC)
    positions = np.arange(len(data.families))
    width = 0.80 / len(data.variants)
    for idx, variant in enumerate(data.variants):
        rows = [indexed[(variant, family)] for family in data.families]
        means = np.array([float(row["mean"]) for row in rows])
        lows = np.array([float(row["ci95_low"]) for row in rows])
        highs = np.array([float(row["ci95_high"]) for row in rows])
        offset = (idx - (len(data.variants) - 1) / 2) * width
        bars = ax.bar(
            positions + offset,
            means,
            width,
            label=display(variant),
            yerr=[means - lows, highs - means],
            capsize=2.5,
            error_kw={"lw": 1.0},
            color=plt.get_cmap("tab20")(idx),
            edgecolor="black",
            linewidth=0.45,
        )
        for bar, row in zip(bars, rows):
            if module.significant(row):
                ax.annotate(
                    "*",
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    textcoords="offset points",
                    xytext=(0, 4 if bar.get_height() >= 0 else -13),
                    ha="center",
                    fontsize=12,
                )
    ax.axhline(0, color="black", linewidth=0.9)
    ax.set_xticks(positions)
    ax.set_xticklabels([family_label(x) for x in data.families], fontsize=10)
    ax.tick_params(axis="y", labelsize=10)
    ax.set_title(title, fontsize=11.5, pad=7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def plot_family_gap(module, validation, heldout, out: Path) -> None:
    module.validate_two_split_data(validation, heldout)
    fig, axes = plt.subplots(2, 1, figsize=(7.4, 7.0), sharex=True, sharey=True)
    draw_gap_panel(module, axes[0], validation, "Validation subset (n = 10)")
    draw_gap_panel(module, axes[1], heldout, "Held-out test split (n = 200)")
    axes[0].set_ylabel("Seed-attribution gap\n($\\Delta$ stability ARI)", fontsize=11)
    axes[1].set_ylabel("Seed-attribution gap\n($\\Delta$ stability ARI)", fontsize=11)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 0.988),
               fontsize=9.5, frameon=False)
    fig.suptitle("Primary Gaussian-smoothed seed policy (* Holm-adjusted p < 0.05)",
                 fontsize=12, y=1.025)
    fig.tight_layout(rect=(0, 0, 1, 0.96), h_pad=1.0)
    save(fig, out)


def plot_heatmap(module, data, out: Path) -> None:
    indexed = family_index(module, data.rows, module.PLOT_METRIC)
    matrix = np.array([
        [float(indexed[(variant, family)]["mean"]) for family in data.families]
        for variant in data.variants
    ])
    limit = max(float(np.max(np.abs(matrix))), np.finfo(float).eps)
    norm = Normalize(vmin=-limit, vmax=limit)
    cmap = plt.get_cmap("RdBu_r")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for i, variant in enumerate(data.variants):
        for j, family in enumerate(data.families):
            value = matrix[i, j]
            row = indexed[(variant, family)]
            ax.add_patch(Rectangle((j, i), 1, 1, facecolor=cmap(norm(value)),
                                   edgecolor="white", linewidth=1.0))
            label = f"{value:+.2f}" + ("*" if module.significant(row) else "")
            ax.text(j + 0.5, i + 0.5, label, ha="center", va="center", fontsize=10.5,
                    color="white" if abs(value) > 0.6 * limit else "black")
    ax.set_xlim(0, len(data.families))
    ax.set_ylim(len(data.variants), 0)
    ax.set_xticks(np.arange(len(data.families)) + 0.5)
    ax.set_xticklabels([family_label(x) for x in data.families], fontsize=10)
    ax.set_yticks(np.arange(len(data.variants)) + 0.5)
    ax.set_yticklabels([display(x) for x in data.variants], fontsize=10)
    ax.set_title("Validation subset: family × variant attribution gap\n"
                 "(* Holm-adjusted p < 0.05)", fontsize=12, pad=8)
    color_ax = ax.inset_axes([1.03, 0.06, 0.035, 0.88])
    edges = np.linspace(-limit, limit, 81)
    for low, high in zip(edges[:-1], edges[1:]):
        color_ax.add_patch(Rectangle((0, low), 1, high - low,
                                     facecolor=cmap(norm((low + high) / 2)), edgecolor="none"))
    color_ax.set_xlim(0, 1)
    color_ax.set_ylim(-limit, limit)
    color_ax.set_xticks([])
    color_ax.yaxis.tick_right()
    color_ax.tick_params(axis="y", labelsize=9)
    color_ax.set_ylabel("$\\Delta$ stability ARI", fontsize=10)
    color_ax.yaxis.set_label_position("right")
    fig.tight_layout(rect=(0, 0, 0.93, 1))
    save(fig, out)


def plot_severity(module, data, out: Path) -> None:
    indexed = module._severity_index(data.rows)
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 6.2), sharey=True)
    axes = list(axes.flat)
    for ax, family in zip(axes, data.families):
        severities = data.severity_order[family]
        for idx, variant in enumerate(data.variants):
            rows = [indexed[(variant, family, severity)] for severity in severities]
            values = np.array([float(row["mean"]) for row in rows])
            lows = np.array([float(row["ci95_low"]) for row in rows])
            highs = np.array([float(row["ci95_high"]) for row in rows])
            ax.errorbar(range(len(severities)), values,
                        yerr=[values - lows, highs - values], marker="o", markersize=4,
                        linewidth=1.4, elinewidth=0.9, capsize=2.5,
                        label=display(variant), color=plt.get_cmap("tab20")(idx))
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(range(len(severities)))
        ax.set_xticklabels([severity_label(x) for x in severities], rotation=25,
                           ha="right", fontsize=9)
        ax.tick_params(axis="y", labelsize=9)
        ax.set_title(display(family), fontsize=10.5)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
    axes[0].set_ylabel("$\\Delta$ stability ARI", fontsize=10.5)
    axes[3].set_ylabel("$\\Delta$ stability ARI", fontsize=10.5)
    axes[-1].axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    axes[-1].legend(handles, labels, loc="center", fontsize=9.5, frameon=False,
                    title="Segmentation variant", title_fontsize=10)
    fig.suptitle("Validation subset: attribution gap across corruption severity",
                 fontsize=12, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.965), h_pad=1.0, w_pad=0.8)
    save(fig, out)


def plot_gt(module, data, out: Path) -> None:
    stability = family_index(module, data.rows, module.PLOT_METRIC)
    human = family_index(module, data.rows, module.GT_METRIC)
    markers = ["o", "s", "^", "D"]
    colors = {family: plt.get_cmap("tab10")(idx) for idx, family in enumerate(data.families)}
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    for variant_idx, variant in enumerate(data.variants):
        for family in data.families:
            key = (variant, family)
            xr, yr = stability[key], human[key]
            x, y = float(xr["mean"]), float(yr["mean"])
            xerr = [[x - float(xr["ci95_low"])], [float(xr["ci95_high"]) - x]]
            yerr = [[y - float(yr["ci95_low"])], [float(yr["ci95_high"]) - y]]
            ax.errorbar(x, y, xerr=xerr, yerr=yerr, fmt=markers[variant_idx],
                        markersize=6.5, markerfacecolor=colors[family], markeredgecolor="black",
                        markeredgewidth=0.6, ecolor=colors[family], elinewidth=0.9,
                        capsize=2.5, alpha=0.92)
            mark = ("*" if module.significant(xr) else "") + ("†" if module.raw_significant(yr) else "")
            if mark:
                ax.annotate(mark, (x, y), textcoords="offset points", xytext=(5, 5), fontsize=9.5)
    ax.axvline(0, color="0.35", linewidth=0.8, linestyle="--")
    ax.axhline(0, color="0.35", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Seed-attribution gap ($\\Delta$ stability ARI)", fontsize=11)
    ax.set_ylabel("Human-reference contrast ($\\Delta$ GT ARI)", fontsize=11)
    ax.set_title("Validation subset: stability gap vs human-reference contrast\n"
                 "(* Holm-adjusted stability; † unadjusted human-reference p < 0.05)",
                 fontsize=11.5, pad=8)
    variant_handles = [Line2D([0], [0], marker=markers[i], color="none", markerfacecolor="0.75",
                              markeredgecolor="black", markersize=6.5, label=display(v))
                       for i, v in enumerate(data.variants)]
    family_handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor=colors[f],
                             markeredgecolor="black", markersize=6.5, label=display(f))
                      for f in data.families]
    first = ax.legend(handles=variant_handles, title="Variant", fontsize=8.5,
                      title_fontsize=9, frameon=False, loc="upper left")
    ax.add_artist(first)
    ax.legend(handles=family_handles, title="Corruption family", fontsize=8.5,
              title_fontsize=9, frameon=False, loc="lower right")
    ax.tick_params(labelsize=10)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    save(fig, out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--heldout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to merge into existing directory: {args.output_dir}")
    module = load_pipeline()
    validation = module.load_plot_data(args.validation.resolve())
    heldout = module.load_plot_data(args.heldout.resolve())
    args.output_dir.mkdir(parents=True)
    plot_family_gap(module, validation, heldout, args.output_dir / "fig3_family_gap")
    plot_heatmap(module, validation, args.output_dir / "fig4_gap_heatmap")
    plot_severity(module, validation, args.output_dir / "fig5_severity_trends")
    plot_gt(module, validation, args.output_dir / "fig6_gt_contrast")
    manifest = {
        "generator": str(Path(__file__).relative_to(PROJECT_ROOT)),
        "generator_sha256": sha256(Path(__file__)),
        "validation_inference_sha256": sha256(args.validation / "inference.csv"),
        "heldout_inference_sha256": sha256(args.heldout / "inference.csv"),
        "layout": "publication v0.4; typography enlarged; values unchanged",
        "outputs": ["fig3_family_gap", "fig4_gap_heatmap", "fig5_severity_trends", "fig6_gt_contrast"],
    }
    (args.output_dir / "publication_figures_v04_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
