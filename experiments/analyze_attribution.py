"""Paired image-level inference for seed-versus-growth attribution experiments."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


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
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_records(path: Path) -> list[dict[str, object]]:
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


def build_pairs(records: list[dict[str, object]]) -> list[dict[str, object]]:
    failures = [record for record in records if record.get("status") != "ok"]
    if failures:
        raise RuntimeError(f"input contains {len(failures)} failed records")

    grouped: dict[tuple[object, ...], dict[str, dict[str, object]]] = defaultdict(dict)
    for record in records:
        mode = str(record["mode"])
        if mode == "clean":
            continue
        if mode not in {"fixed_clean", "recomputed"}:
            raise RuntimeError(f"unexpected mode: {mode}")
        key = (
            record.get("variant_id"),
            record["image_id"],
            float(record["sigma"]),
            int(record["replicate"]),
        )
        if mode in grouped[key]:
            raise RuntimeError(f"duplicate paired mode {mode}: {key}")
        grouped[key][mode] = record

    pairs = []
    for key, modes in sorted(grouped.items(), key=lambda item: tuple(str(x) for x in item[0])):
        missing = {"fixed_clean", "recomputed"} - set(modes)
        if missing:
            raise RuntimeError(f"incomplete pair {key}; missing {sorted(missing)}")
        fixed = modes["fixed_clean"]
        recomputed = modes["recomputed"]
        pairs.append(
            {
                "variant": str(key[0]),
                "image_id": str(key[1]),
                "sigma": float(key[2]),
                "replicate": int(key[3]),
                "fixed_stability_ari": float(fixed["stability_ari"]),
                "recomputed_stability_ari": float(recomputed["stability_ari"]),
                "delta_stability_ari": float(fixed["stability_ari"])
                - float(recomputed["stability_ari"]),
                "fixed_stability_vi_total": float(fixed["stability_vi_total"]),
                "recomputed_stability_vi_total": float(recomputed["stability_vi_total"]),
                "fixed_advantage_stability_vi_total": float(recomputed["stability_vi_total"])
                - float(fixed["stability_vi_total"]),
                "fixed_stability_boundary_f1_t1": float(fixed["stability_boundary_f1_t1"]),
                "recomputed_stability_boundary_f1_t1": float(
                    recomputed["stability_boundary_f1_t1"]
                ),
                "delta_stability_boundary_f1_t1": float(
                    fixed["stability_boundary_f1_t1"]
                )
                - float(recomputed["stability_boundary_f1_t1"]),
                "fixed_seed_count": int(fixed["seed_count"]),
                "recomputed_seed_count": int(recomputed["seed_count"]),
                "recomputed_minus_fixed_seed_count": int(recomputed["seed_count"])
                - int(fixed["seed_count"]),
            }
        )
    if not pairs:
        raise RuntimeError("no perturbed pairs")
    return pairs


def mean(values: list[float]) -> float:
    return statistics.fmean(values)


def aggregate_images(pairs: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, float], list[dict[str, object]]] = defaultdict(list)
    for row in pairs:
        groups[(str(row["variant"]), str(row["image_id"]), float(row["sigma"]))].append(row)
    result = []
    for (variant, image_id, sigma), rows in sorted(groups.items()):
        result.append(
            {
                "variant": variant,
                "image_id": image_id,
                "sigma": sigma,
                "replicates": len(rows),
                **{
                    field: mean([float(row[field]) for row in rows])
                    for field in EFFECT_FIELDS
                },
            }
        )
    return result


def percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("empty values")
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
    if iterations <= 0:
        raise ValueError("bootstrap iterations must be positive")
    n = len(values)
    estimates = sorted(mean([values[rng.randrange(n)] for _ in range(n)]) for _ in range(iterations))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def sign_flip_p(values: list[float], permutations: int, rng: random.Random) -> tuple[float, str]:
    observed = abs(mean(values))
    n = len(values)
    tolerance = 1e-15
    if n <= 18:
        extreme = 0
        total = 1 << n
        for mask in range(total):
            statistic = abs(
                mean([value if mask & (1 << index) else -value for index, value in enumerate(values)])
            )
            if statistic + tolerance >= observed:
                extreme += 1
        return extreme / total, "exact"
    if permutations <= 0:
        raise ValueError("permutations must be positive")
    extreme = 0
    for _ in range(permutations):
        statistic = abs(mean([value if rng.random() < 0.5 else -value for value in values]))
        if statistic + tolerance >= observed:
            extreme += 1
    return (extreme + 1) / (permutations + 1), "monte_carlo"


def holm_adjust(rows: list[dict[str, object]]) -> None:
    ordered = sorted(enumerate(rows), key=lambda item: float(item[1]["sign_flip_p"]))
    count = len(ordered)
    running = 0.0
    adjusted: dict[int, float] = {}
    for rank, (index, row) in enumerate(ordered):
        candidate = min(1.0, (count - rank) * float(row["sign_flip_p"]))
        running = max(running, candidate)
        adjusted[index] = running
    for index, value in adjusted.items():
        rows[index]["holm_p"] = value


def infer(
    image_rows: list[dict[str, object]],
    primary_variants: tuple[str, ...],
    bootstrap: int,
    permutations: int,
    seed: int,
) -> list[dict[str, object]]:
    rng = random.Random(seed)
    by_variant_image: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in image_rows:
        by_variant_image[(str(row["variant"]), str(row["image_id"]))].append(row)

    overall: dict[str, list[dict[str, object]]] = defaultdict(list)
    for (variant, image_id), rows in by_variant_image.items():
        overall[variant].append(
            {
                "variant": variant,
                "image_id": image_id,
                **{
                    field: mean([float(row[field]) for row in rows])
                    for field in EFFECT_FIELDS
                },
            }
        )

    inference = []
    for variant in sorted(overall):
        for metric in EFFECT_FIELDS:
            values = [float(row[metric]) for row in overall[variant]]
            low, high = bootstrap_mean_ci(values, bootstrap, rng)
            p_value, method = sign_flip_p(values, permutations, rng)
            inference.append(
                {
                    "variant": variant,
                    "stratum": "overall",
                    "metric": metric,
                    "n_images": len(values),
                    "mean": mean(values),
                    "median": statistics.median(values),
                    "ci95_low": low,
                    "ci95_high": high,
                    "sign_flip_p": p_value,
                    "test_method": method,
                    "holm_p": "",
                }
            )

    severity_groups: dict[tuple[str, float], list[dict[str, object]]] = defaultdict(list)
    for row in image_rows:
        severity_groups[(str(row["variant"]), float(row["sigma"]))].append(row)
    for (variant, sigma), rows in sorted(severity_groups.items()):
        for metric in EFFECT_FIELDS:
            values = [float(row[metric]) for row in rows]
            low, high = bootstrap_mean_ci(values, bootstrap, rng)
            p_value, method = sign_flip_p(values, permutations, rng)
            inference.append(
                {
                    "variant": variant,
                    "stratum": f"sigma={sigma:g}",
                    "metric": metric,
                    "n_images": len(values),
                    "mean": mean(values),
                    "median": statistics.median(values),
                    "ci95_low": low,
                    "ci95_high": high,
                    "sign_flip_p": p_value,
                    "test_method": method,
                    "holm_p": "",
                }
            )

    primary = [
        row
        for row in inference
        if row["stratum"] == "overall"
        and row["metric"] == "delta_stability_ari"
        and row["variant"] in primary_variants
    ]
    missing = sorted(set(primary_variants) - {str(row["variant"]) for row in primary})
    if missing:
        raise RuntimeError(f"missing primary variants: {missing}")
    holm_adjust(primary)
    corrected = {str(row["variant"]): row["holm_p"] for row in primary}
    for row in inference:
        if (
            row["stratum"] == "overall"
            and row["metric"] == "delta_stability_ari"
            and row["variant"] in corrected
        ):
            row["holm_p"] = corrected[str(row["variant"])]
    return inference


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"no rows for {path}")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def report(inference: list[dict[str, object]], primary_variants: tuple[str, ...]) -> str:
    primary = [
        row
        for row in inference
        if row["stratum"] == "overall"
        and row["metric"] == "delta_stability_ari"
        and row["variant"] in primary_variants
    ]
    lines = [
        "# Seed-versus-growth attribution analysis",
        "",
        "Positive values mean that holding clean seeds fixed retained more of the clean segmentation than recomputing seeds after corruption.",
        "",
        "| Variant | Images | Mean ARI gap | Median | 95% bootstrap CI | Sign-flip p | Holm p |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in primary:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["variant"]),
                    str(row["n_images"]),
                    fmt(row["mean"]),
                    fmt(row["median"]),
                    f"[{fmt(row['ci95_low'])}, {fmt(row['ci95_high'])}]",
                    fmt(row["sign_flip_p"]),
                    fmt(row["holm_p"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Inference uses images as experimental units. Replicates and corruption severities are averaged within image for the primary comparison. The current validation-subset run is a development result, not a frozen test-set claim.",
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
    destination.mkdir(parents=True)

    primary_variants = tuple(args.primary_variant or DEFAULT_PRIMARY_VARIANTS)
    records = load_records(source)
    pairs = build_pairs(records)
    image_rows = aggregate_images(pairs)
    inference = infer(
        image_rows,
        primary_variants,
        args.bootstrap,
        args.permutations,
        args.seed,
    )
    write_csv(destination / "paired_records.csv", pairs)
    write_csv(destination / "image_level_effects.csv", image_rows)
    write_csv(destination / "inference.csv", inference)
    (destination / "report.md").write_text(report(inference, primary_variants), encoding="utf-8")
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(source),
        "input_sha256": sha256_file(source),
        "analysis_script_sha256": sha256_file(Path(__file__)),
        "records": len(records),
        "pairs": len(pairs),
        "image_level_rows": len(image_rows),
        "primary_variants": primary_variants,
        "bootstrap_iterations": args.bootstrap,
        "sign_flip_permutations": args.permutations,
        "random_seed": args.seed,
    }
    (destination / "analysis_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
