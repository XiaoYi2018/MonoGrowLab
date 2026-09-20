"""Publication-sized editable architecture diagram for MonoGrowLab v0.4."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402


INK = "#1a202c"
EDGE = "#4a5568"


def box(ax, x, y, w, h, lines, *, face="#f2f4f8", fs=9.0, lh=0.31):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.010,rounding_size=0.03",
        linewidth=1.0, edgecolor=EDGE, facecolor=face,
    ))
    y0 = y + h / 2 + (len(lines) - 1) * lh / 2
    for idx, line in enumerate(lines):
        ax.text(x + w / 2, y0 - idx * lh, line, ha="center", va="center",
                fontsize=fs, color=INK)


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10,
                                 linewidth=1.1, color=EDGE))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to merge into existing directory: {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    fig, ax = plt.subplots(figsize=(7.3, 4.4))
    ax.set_xlim(0, 11.6)
    ax.set_ylim(0.75, 6.45)
    ax.axis("off")

    box(ax, 0.15, 4.65, 2.05, 1.25,
        ["Dataset adapter", "BSDS500 split", "image + human", "references"], fs=8.6, lh=0.27)
    box(ax, 0.15, 3.10, 2.05, 1.25, ["Corruption registry", "five families", "normalised units"])
    box(ax, 0.15, 1.55, 2.05, 1.25, ["Configuration", "split, variants", "seed modes"])

    ax.add_patch(FancyBboxPatch(
        (2.65, 1.55), 2.80, 4.35, boxstyle="round,pad=0.010,rounding_size=0.03",
        linewidth=1.1, edgecolor=EDGE, facecolor="#e8f0fe",
    ))
    ax.text(4.05, 5.48, "Schema-v2 runner", ha="center", va="center", fontsize=10.0, color=INK)
    bullets = [
        "• fail-closed manifest",
        "  verification",
        "• condition-coordinate",
        "  seeding",
        "• resumable run keys",
        "• immutable metadata",
        "  config / dependencies",
        "  package hashes",
        "• schema-v2 records",
    ]
    for idx, line in enumerate(bullets):
        ax.text(2.82, 4.98 - idx * 0.40, line, ha="left", va="center", fontsize=8.5, color=INK)

    box(ax, 6.20, 4.45, 2.15, 1.15, ["fixed_clean", "clean-image", "seeds"], fs=8.7, lh=0.27)
    box(ax, 6.20, 3.00, 2.15, 1.15, ["recomputed", "corrupted-image", "seeds"], fs=8.7, lh=0.27)
    box(ax, 9.00, 3.35, 2.45, 2.25,
        ["Paired inference", "image-level units", "bootstrap CI", "sign-flip tests", "Holm per family"])
    box(ax, 9.00, 1.35, 2.45, 1.30,
        ["Reports", "CSV + standalone", "HTML report", "provenance ledger"], fs=8.6, lh=0.27)

    arrow(ax, (2.20, 5.27), (2.65, 5.05))
    arrow(ax, (2.20, 3.72), (2.65, 3.55))
    arrow(ax, (2.20, 2.17), (2.65, 2.25))
    arrow(ax, (5.45, 5.05), (6.20, 5.00))
    arrow(ax, (5.45, 3.55), (6.20, 3.58))
    arrow(ax, (8.35, 5.00), (9.00, 4.65))
    arrow(ax, (8.35, 3.58), (9.00, 4.05))
    arrow(ax, (10.22, 3.35), (10.22, 2.65))

    ax.text(5.80, 6.20,
            "Corrupted pixels and growth rule stay fixed; only the seed source changes",
            ha="center", va="center", fontsize=10.0, color=INK)
    fig.tight_layout(pad=0.05)
    out = args.output_dir / "fig1_architecture"
    for suffix in (".pdf", ".svg", ".png"):
        fig.savefig(out.with_suffix(suffix), dpi=300, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
