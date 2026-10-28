"""Family-aware paired image-level inference for MonoGrowLab records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from monogrowlab.experiment_schema import (  # noqa: E402
    canonical_hash,
    pair_records,
    validate_expected_record_grid,
    validate_single_run,
)


DEFAULT_PRIMARY_VARIANTS = (
    "clerg-gaussian1",
    "adams-gaussian2",
    "fan2005-gaussian2",
    "levelset-gaussian2",
)
EFFECT_FIELDS = (
    "delta_stability_ari",
    "fixed_advantage_stability_vi_total",
    "delta_stability_boundary_f1_t1",
    "recomputed_minus_fixed_seed_count",
    "delta_gt_ari_mean",
    "fixed_advantage_gt_vi_total_mean",
    "delta_gt_boundary_f1_t1_mean",
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid JSON at line {line_number}: {path}") from exc
    if not records:
        raise RuntimeError(f"no records: {path}")
    return records


def load_run_context(source: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    metadata_path = source.with_suffix(source.suffix + ".meta.json")
    if not metadata_path.is_file():
        raise RuntimeError(f"missing run metadata: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    config_relative = metadata.get("config_path")
    if not isinstance(config_relative, str):
        raise RuntimeError("run metadata does not identify config_path")
    config_path = (PROJECT_ROOT / config_relative).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    observed_config_hash = canonical_hash(config)
    if observed_config_hash != metadata.get("config_sha256"):
        raise RuntimeError("configuration hash differs from run metadata")
    validate_single_run(records, observed_config_hash)
    manifest_relative = metadata.get("dataset_manifest")
    if not isinstance(manifest_relative, str):
        raise RuntimeError("run metadata does not identify dataset_manifest")
    manifest_path = (PROJECT_ROOT / manifest_relative).resolve()
    if not manifest_path.is_file():
        raise RuntimeError(f"dataset manifest is missing: {manifest_path}")
    if file_hash(manifest_path) != metadata.get("dataset_manifest_sha256"):
        raise RuntimeError("dataset manifest hash differs from run metadata")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_expected_record_grid(records, config, manifest)
    shapes = sorted(
        {
            (int(record["height"]), int(record["width"]))
            for record in records
            if record.get("height") is not None and record.get("width") is not None
        }
    )
    reference_counts = sorted(
        {
            int(record["gt_reference_count"])
            for record in records
            if record.get("gt_reference_count") is not None
        }
    )
    return {
        "config_path": config_relative,
        "config_sha256": observed_config_hash,
        "dataset_manifest": manifest_relative,
        "dataset_manifest_sha256": metadata["dataset_manifest_sha256"],
        "split": config.get("split"),
        "configured_max_dimension": config.get("max_dimension"),
        "analysis_role": config.get("analysis_role", "primary"),
        "image_count": len({str(record["image_id"]) for record in records}),
        "actual_shapes": [[height, width] for height, width in shapes],
        "ground_truth_references_per_image": reference_counts,
        "interpretation": metadata.get("interpretation", ""),
    }


def fmean(values: list[float]) -> float:
    return statistics.fmean(values)


def aggregate_images(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pairs:
        groups[
            (
                str(row["variant"]),
                str(row["image_id"]),
                str(row["corruption_family"]),
                str(row["severity_id"]),
            )
        ].append(row)
    result = []
    for (variant, image_id, family, severity_id), rows in sorted(groups.items()):
        parameter_values = {str(row["corruption_params"]) for row in rows}
        unit_values = {str(row["corruption_units"]) for row in rows}
        if len(parameter_values) != 1 or len(unit_values) != 1:
            raise RuntimeError(
                f"inconsistent condition metadata: {(variant, image_id, family, severity_id)}"
            )
        result.append(
            {
                "variant": variant,
                "image_id": image_id,
                "corruption_family": family,
                "severity_id": severity_id,
                "corruption_params": next(iter(parameter_values)),
                "corruption_units": next(iter(unit_values)),
                "replicates": len(rows),
                **{
                    field: fmean([float(row[field]) for row in rows])
                    for field in EFFECT_FIELDS
                },
            }
        )
    return result


def percentile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def bootstrap_mean_ci(
    values: list[float], iterations: int, rng: random.Random
) -> tuple[float, float]:
    if not values or iterations <= 0:
        raise ValueError("bootstrap requires non-empty values and positive iterations")
    n = len(values)
    estimates = sorted(
        fmean([values[rng.randrange(n)] for _ in range(n)]) for _ in range(iterations)
    )
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def sign_flip_p(
    values: list[float], permutations: int, rng: random.Random
) -> tuple[float, str]:
    observed = abs(fmean(values))
    tolerance = 1e-15
    count = len(values)
    if count <= 18:
        extreme = 0
        total = 1 << count
        for mask in range(total):
            statistic = abs(
                fmean(
                    [
                        value if mask & (1 << index) else -value
                        for index, value in enumerate(values)
                    ]
                )
            )
            if statistic + tolerance >= observed:
                extreme += 1
        return extreme / total, "exact"
    if permutations <= 0:
        raise ValueError("permutations must be positive")
    extreme = 0
    for _ in range(permutations):
        statistic = abs(
            fmean([value if rng.random() < 0.5 else -value for value in values])
        )
        if statistic + tolerance >= observed:
            extreme += 1
    return (extreme + 1) / (permutations + 1), "monte_carlo"


def holm_adjust(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(enumerate(rows), key=lambda item: float(item[1]["sign_flip_p"]))
    running = 0.0
    adjusted = {}
    total = len(ordered)
    for rank, (index, row) in enumerate(ordered):
        candidate = min(1.0, (total - rank) * float(row["sign_flip_p"]))
        running = max(running, candidate)
        adjusted[index] = running
    for index, value in adjusted.items():
        rows[index]["holm_p"] = value


def inference_row(
    variant: str,
    family: str,
    stratum: str,
    metric: str,
    values: list[float],
    bootstrap: int,
    permutations: int,
    rng: random.Random,
) -> dict[str, Any]:
    low, high = bootstrap_mean_ci(values, bootstrap, rng)
    p_value, test_method = sign_flip_p(values, permutations, rng)
    minimum_attainable_p = (
        min(1.0, 2.0 / (2 ** len(values)))
        if test_method == "exact"
        else 1.0 / (permutations + 1)
    )
    return {
        "variant": variant,
        "corruption_family": family,
        "stratum": stratum,
        "metric": metric,
        "n_images": len(values),
        "mean": fmean(values),
        "median": statistics.median(values),
        "ci95_low": low,
        "ci95_high": high,
        "sign_flip_p": p_value,
        "test_method": test_method,
        "minimum_attainable_p": minimum_attainable_p,
        "holm_p": "",
    }


def infer(
    image_rows: list[dict[str, Any]],
    primary_variants: tuple[str, ...],
    bootstrap: int,
    permutations: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    inference = []

    by_variant_family_image: dict[
        tuple[str, str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for row in image_rows:
        by_variant_family_image[
            (
                str(row["variant"]),
                str(row["corruption_family"]),
                str(row["image_id"]),
            )
        ].append(row)

    family_image_rows: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for (variant, family, image_id), rows in by_variant_family_image.items():
        family_image_rows[(variant, family)].append(
            {
                "image_id": image_id,
                **{
                    field: fmean([float(row[field]) for row in rows])
                    for field in EFFECT_FIELDS
                },
            }
        )

    for (variant, family), rows in sorted(family_image_rows.items()):
        for metric in EFFECT_FIELDS:
            inference.append(
                inference_row(
                    variant,
                    family,
                    "family",
                    metric,
                    [float(row[metric]) for row in rows],
                    bootstrap,
                    permutations,
                    rng,
                )
            )

    severity_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in image_rows:
        severity_groups[
            (
                str(row["variant"]),
                str(row["corruption_family"]),
                str(row["severity_id"]),
            )
        ].append(row)
    for (variant, family, severity_id), rows in sorted(severity_groups.items()):
        for metric in EFFECT_FIELDS:
            inference.append(
                inference_row(
                    variant,
                    family,
                    f"severity={severity_id}",
                    metric,
                    [float(row[metric]) for row in rows],
                    bootstrap,
                    permutations,
                    rng,
                )
            )

    families = sorted({str(row["corruption_family"]) for row in image_rows})
    for family in families:
        primary = [
            row
            for row in inference
            if row["corruption_family"] == family
            and row["stratum"] == "family"
            and row["metric"] == "delta_stability_ari"
            and row["variant"] in primary_variants
        ]
        missing = sorted(set(primary_variants) - {str(row["variant"]) for row in primary})
        if missing:
            raise RuntimeError(f"{family} missing primary variants: {missing}")
        holm_adjust(primary)
        corrected = {str(row["variant"]): row["holm_p"] for row in primary}
        for row in inference:
            if (
                row["corruption_family"] == family
                and row["stratum"] == "family"
                and row["metric"] == "delta_stability_ari"
                and row["variant"] in corrected
            ):
                row["holm_p"] = corrected[str(row["variant"])]
    return inference


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"no rows for {path}")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any) -> str:
    if not isinstance(value, float):
        return str(value)
    if value != 0.0 and abs(value) < 1e-4:
        return f"{value:.2e}"
    return f"{value:.4f}"


def recorded_minimum_p(row: dict[str, Any]) -> float | None:
    recorded = row.get("minimum_attainable_p")
    if recorded not in {None, ""}:
        return float(recorded)
    if row.get("test_method") == "exact":
        return min(1.0, 2.0 / (2 ** int(row["n_images"])))
    return None


def report(
    inference: list[dict[str, Any]],
    primary_variants: tuple[str, ...],
    context: dict[str, Any],
) -> str:
    if context["split"] == "test":
        scope_sentence = (
            "This held-out result evaluates the frozen protocol on the reserved test split."
        )
    else:
        scope_sentence = (
            "This result supports configuration development on the designated non-test split."
        )
    primary = sorted(
        [
        row
        for row in inference
        if row["stratum"] == "family"
        and row["metric"] == "delta_stability_ari"
        and row["variant"] in primary_variants
        ],
        key=lambda row: (str(row["corruption_family"]), str(row["variant"])),
    )
    minimum_values = sorted(
        {
            value
            for row in primary
            if (value := recorded_minimum_p(row)) is not None
        }
    )
    minimum_text = ", ".join(fmt(value) for value in minimum_values) or "n/a"
    low_information = any(value >= 0.05 for value in minimum_values)
    lines = [
        "# Seed-versus-growth attribution analysis",
        "",
        f"Configuration: `{context['config_path']}`; split: `{context['split']}`; images: {context['image_count']}; configured maximum dimension: {context['configured_max_dimension']}; human references per image: {context['ground_truth_references_per_image']}.",
        "",
        f"Run interpretation: {context['interpretation']}",
        "",
        "Positive ARI gaps mean that holding clean seeds fixed retained more of the clean segmentation than recomputing seeds after corruption.",
        "",
        f"Minimum attainable two-sided sign-flip p under the recorded exact or Monte Carlo test method: {minimum_text}."
        + (
            " At this sample size, p values are diagnostic only because the minimum attainable value is not below 0.05."
            if low_information
            else ""
        ),
        "",
        "| Corruption | Variant | Images | Mean ARI gap | Median | 95% bootstrap CI | Sign-flip p | Holm p | Minimum possible p |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in primary:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["corruption_family"]),
                    str(row["variant"]),
                    str(row["n_images"]),
                    fmt(row["mean"]),
                    fmt(row["median"]),
                    f"[{fmt(row['ci95_low'])}, {fmt(row['ci95_high'])}]",
                    fmt(row["sign_flip_p"]),
                    fmt(row["holm_p"]),
                    fmt(recorded_minimum_p(row)) if recorded_minimum_p(row) is not None else "n/a",
                ]
            )
            + " |"
        )
    sensitivity = sorted(
        [
            row
            for row in inference
            if row["stratum"] == "family"
            and row["metric"] == "delta_stability_ari"
            and row["variant"] not in primary_variants
        ],
        key=lambda row: (str(row["corruption_family"]), str(row["variant"])),
    )
    lines.extend(
        [
            "",
            "## Seed-policy sensitivity variants",
            "",
            "These non-primary variants are descriptive sensitivity analyses and are not included in the primary Holm family.",
            "",
            "| Corruption | Variant | Images | Mean ARI gap | 95% bootstrap CI | Sign-flip p |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in sensitivity:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["corruption_family"]),
                    str(row["variant"]),
                    str(row["n_images"]),
                    fmt(row["mean"]),
                    f"[{fmt(row['ci95_low'])}, {fmt(row['ci95_high'])}]",
                    fmt(row["sign_flip_p"]),
                ]
            )
            + " |"
        )
    quality = {
        (str(row["corruption_family"]), str(row["variant"])): row
        for row in inference
        if row["stratum"] == "family"
        and row["metric"] == "delta_gt_ari_mean"
        and row["variant"] in primary_variants
    }
    lines.extend(
        [
            "",
            "## Ground-truth quality contrast",
            "",
            "Positive values mean that the fixed-clean-seed execution had higher mean ARI against the human references than the recomputed-seed execution on the same corrupted images. This contrast is secondary and prevents a stability advantage from being interpreted automatically as an accuracy advantage.",
            "",
            "| Corruption | Variant | Mean GT ARI difference | 95% bootstrap CI | Sign-flip p |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for key in sorted(quality):
        row = quality[key]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["corruption_family"]),
                    str(row["variant"]),
                    fmt(row["mean"]),
                    f"[{fmt(row['ci95_low'])}, {fmt(row['ci95_high'])}]",
                    fmt(row["sign_flip_p"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Inference uses images as experimental units. Replicates are averaged within image and severity, then severities are averaged within image and corruption family. Holm correction is applied separately within each family across the four primary variants. For asymmetric families such as brightness scaling, severity-level results preserve the direction-specific effects; the family row is only the configured average across darkening and brightening. "
            + scope_sentence,
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=10_000)
    parser.add_argument("--permutations", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument("--primary-variant", action="append")
    args = parser.parse_args()

    source = args.input.resolve()
    destination = args.output_dir.resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to merge into existing directory: {destination}")

    primary_variants = tuple(args.primary_variant or DEFAULT_PRIMARY_VARIANTS)
    records = load_records(source)
    context = load_run_context(source, records)
    pairs = pair_records(records)
    image_rows = aggregate_images(pairs)
    inference = infer(
        image_rows,
        primary_variants,
        args.bootstrap,
        args.permutations,
        args.seed,
    )
    destination.mkdir(parents=True)
    write_csv(destination / "paired_records.csv", pairs)
    write_csv(destination / "image_level_effects.csv", image_rows)
    write_csv(destination / "inference.csv", inference)
    (destination / "report.md").write_text(
        report(inference, primary_variants, context), encoding="utf-8"
    )
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(source),
        "input_sha256": file_hash(source),
        "analysis_script_sha256": file_hash(Path(__file__)),
        "record_schema_versions": sorted(
            {int(record.get("schema_version", 1)) for record in records}
        ),
        "records": len(records),
        "pairs": len(pairs),
        "image_level_rows": len(image_rows),
        "primary_variants": primary_variants,
        "bootstrap_iterations": args.bootstrap,
        "sign_flip_permutations": args.permutations,
        "random_seed": args.seed,
        "run_context": context,
    }
    (destination / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
