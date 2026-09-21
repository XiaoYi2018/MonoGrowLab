"""Family-aware descriptive summaries for MonoGrowLab schema-v1/v2 records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
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
    normalized_condition,
    pair_records,
    validate_single_run,
    variant_label,
)


CLEAN_FIELDS = (
    "seed_count",
    "regions",
    "seconds",
    "coverage",
    "gt_ari_mean",
    "gt_ari_best",
    "gt_vi_total_mean",
    "gt_boundary_f1_t1_mean",
)
PERTURBED_FIELDS = (
    "seed_count",
    "regions",
    "seconds",
    "coverage",
    "gt_ari_mean",
    "gt_vi_total_mean",
    "gt_boundary_f1_t1_mean",
    "stability_ari",
    "stability_vi_total",
    "stability_boundary_f1_t0",
    "stability_boundary_f1_t1",
)
PAIR_FIELDS = (
    "fixed_seed_count",
    "recomputed_seed_count",
    "recomputed_minus_fixed_seed_count",
    "fixed_stability_ari",
    "recomputed_stability_ari",
    "delta_stability_ari",
    "fixed_stability_vi_total",
    "recomputed_stability_vi_total",
    "fixed_advantage_stability_vi_total",
    "fixed_stability_boundary_f1_t1",
    "recomputed_stability_boundary_f1_t1",
    "delta_stability_boundary_f1_t1",
    "fixed_gt_ari_mean",
    "recomputed_gt_ari_mean",
    "delta_gt_ari_mean",
    "fixed_gt_vi_total_mean",
    "recomputed_gt_vi_total_mean",
    "fixed_advantage_gt_vi_total_mean",
    "fixed_gt_boundary_f1_t1_mean",
    "recomputed_gt_boundary_f1_t1_mean",
    "delta_gt_boundary_f1_t1_mean",
)


def load_records(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid JSON at line {number}: {path}") from exc
    if not rows:
        raise RuntimeError(f"no records: {path}")
    return rows


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_run_context(source: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    metadata_path = source.with_suffix(source.suffix + ".meta.json")
    if not metadata_path.is_file():
        raise RuntimeError(f"missing run metadata: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    config_relative = metadata.get("config_path")
    if not isinstance(config_relative, str):
        raise RuntimeError("run metadata does not identify config_path")
    config = json.loads((PROJECT_ROOT / config_relative).read_text(encoding="utf-8"))
    config_hash = canonical_hash(config)
    if config_hash != metadata.get("config_sha256"):
        raise RuntimeError("configuration hash differs from run metadata")
    validate_single_run(records, config_hash)
    manifest_relative = metadata.get("dataset_manifest")
    if not isinstance(manifest_relative, str):
        raise RuntimeError("run metadata does not identify dataset_manifest")
    manifest_path = (PROJECT_ROOT / manifest_relative).resolve()
    if not manifest_path.is_file():
        raise RuntimeError(f"dataset manifest is missing: {manifest_path}")
    if file_hash(manifest_path) != metadata.get("dataset_manifest_sha256"):
        raise RuntimeError("dataset manifest hash differs from run metadata")
    return {
        "config_path": config_relative,
        "config_sha256": config_hash,
        "dataset_manifest": manifest_relative,
        "dataset_manifest_sha256": metadata["dataset_manifest_sha256"],
        "split": config.get("split"),
        "configured_max_dimension": config.get("max_dimension"),
        "analysis_role": config.get("analysis_role", "primary"),
        "image_count": len({str(record["image_id"]) for record in records}),
        "ground_truth_references_per_image": sorted(
            {
                int(record["gt_reference_count"])
                for record in records
                if record.get("gt_reference_count") is not None
            }
        ),
        "interpretation": metadata.get("interpretation", ""),
    }


def summarize_values(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {"n": len(rows)}
    for field in fields:
        values = [float(row[field]) for row in rows if row.get(field) is not None]
        if values:
            result[f"{field}_mean"] = statistics.fmean(values)
            result[f"{field}_median"] = statistics.median(values)
            result[f"{field}_sd"] = statistics.stdev(values) if len(values) > 1 else 0.0
    return result


def grouped_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    conditions = {}
    for record in records:
        if record.get("status") != "ok":
            continue
        condition = normalized_condition(record)
        key = (
            variant_label(record),
            str(record["mode"]),
            condition["family"],
            condition["severity_id"],
        )
        groups[key].append(record)
        conditions[key] = condition
    result = []
    for (variant, mode, family, severity_id), rows in sorted(groups.items()):
        condition = conditions[(variant, mode, family, severity_id)]
        fields = CLEAN_FIELDS if mode == "clean" else PERTURBED_FIELDS
        result.append(
            {
                "variant": variant,
                "mode": mode,
                "corruption_family": family,
                "severity_id": severity_id,
                "corruption_params": json.dumps(
                    condition["parameters"], sort_keys=True, separators=(",", ":")
                ),
                "corruption_units": condition["units"],
                **summarize_values(rows, fields),
            }
        )
    return result


def paired_summary(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        groups[
            (
                str(pair["variant"]),
                str(pair["corruption_family"]),
                str(pair["severity_id"]),
            )
        ].append(pair)
    result = []
    for (variant, family, severity_id), rows in sorted(groups.items()):
        parameter_values = {str(row["corruption_params"]) for row in rows}
        unit_values = {str(row["corruption_units"]) for row in rows}
        if len(parameter_values) != 1 or len(unit_values) != 1:
            raise RuntimeError(f"condition mismatch: {(variant, family, severity_id)}")
        result.append(
            {
                "variant": variant,
                "corruption_family": family,
                "severity_id": severity_id,
                "corruption_params": next(iter(parameter_values)),
                "corruption_units": next(iter(unit_values)),
                **summarize_values(rows, PAIR_FIELDS),
            }
        )
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"no rows for {path}")
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_report(
    source: Path,
    records: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    paired: list[dict[str, Any]],
    context: dict[str, Any],
) -> str:
    failures = [record for record in records if record.get("status") != "ok"]
    lines = [
        "# Experiment summary",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Source: `{source}`",
        "",
        f"Configuration: `{context['config_path']}`; split: `{context['split']}`; images: {context['image_count']}; configured maximum dimension: {context['configured_max_dimension']}; human references per image: {context['ground_truth_references_per_image']}.",
        "",
        f"Run interpretation: {context['interpretation']}",
        "",
        f"Records: {len(records)}; successful: {len(records) - len(failures)}; failed: {len(failures)}.",
        "",
        "## Clean-image comparison",
        "",
        "| Variant | n | Seeds | Runtime (s) | GT ARI | GT VI | Boundary F1 (t=1) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        if row["mode"] != "clean":
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["variant"]),
                    fmt(row["n"]),
                    fmt(row.get("seed_count_mean", "")),
                    fmt(row.get("seconds_mean", "")),
                    fmt(row.get("gt_ari_mean_mean", "")),
                    fmt(row.get("gt_vi_total_mean_mean", "")),
                    fmt(row.get("gt_boundary_f1_t1_mean_mean", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Strictly paired attribution",
            "",
            "| Corruption | Severity | Variant | Pairs | Fixed stability ARI | Recomputed stability ARI | Stability gap | GT ARI difference | Seed increase |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in paired:
        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["corruption_family"]),
                    fmt(row["severity_id"]),
                    fmt(row["variant"]),
                    fmt(row["n"]),
                    fmt(row.get("fixed_stability_ari_mean", "")),
                    fmt(row.get("recomputed_stability_ari_mean", "")),
                    fmt(row.get("delta_stability_ari_mean", "")),
                    fmt(row.get("delta_gt_ari_mean_mean", "")),
                    fmt(row.get("recomputed_minus_fixed_seed_count_mean", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "These tables describe the configured run only. Development and validation-subset experiments are not test-set benchmark claims. Boundary F1 is the documented MonoGrowLab tolerance metric, not the official BSDS500 boundary benchmark implementation.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source = args.input.resolve()
    destination = args.output_dir.resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to merge into existing directory: {destination}")
    records = load_records(source)
    context = load_run_context(source, records)
    summary = grouped_summary(records)
    paired = paired_summary(pair_records(records))
    destination.mkdir(parents=True)
    write_csv(destination / "group_summary.csv", summary)
    write_csv(destination / "paired_attribution.csv", paired)
    (destination / "summary.md").write_text(
        markdown_report(source, records, summary, paired, context), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "records": len(records),
                "groups": len(summary),
                "paired_groups": len(paired),
                "output_dir": str(destination),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
