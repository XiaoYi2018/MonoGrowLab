"""Dependency-free standalone HTML reporting for MonoGrowLab outputs."""

from __future__ import annotations

import html
from typing import Any, Iterable


PRIMARY_VARIANTS = (
    "clerg-gaussian1",
    "adams-gaussian2",
    "fan2005-gaussian2",
    "levelset-gaussian2",
)


def _number(value: Any, digits: int = 4) -> str:
    if value in {None, ""}:
        return ""
    number = float(value)
    if number != 0.0 and abs(number) < 10 ** (-digits):
        return f"{number:.2e}"
    return f"{number:.{digits}f}"


def _cell_color(value: float, limit: float = 0.4) -> str:
    magnitude = min(1.0, abs(value) / limit)
    lightness = 98.0 - 27.0 * magnitude
    return f"hsl(216 55% {lightness:.1f}%)"


def _minimum_attainable_p(row: dict[str, Any]) -> float | None:
    recorded = row.get("minimum_attainable_p")
    if recorded not in {None, ""}:
        return float(recorded)
    if row.get("test_method") == "exact":
        n = int(row["n_images"])
        return min(1.0, 2.0 / (2**n))
    return None


def _p_with_marker(value: Any) -> str:
    if value in {None, ""}:
        return ""
    observed = float(value)
    marker = " (n.s.)" if observed >= 0.05 else ""
    return f"{_number(observed)}{marker}"


def _table(headers: list[str], rows: Iterable[list[Any]], classes: str = "") -> str:
    header = "".join(f"<th>{html.escape(str(item))}</th>" for item in headers)
    body = []
    for row in rows:
        cells = []
        for value in row:
            if isinstance(value, tuple):
                text, style = value
                cells.append(
                    f'<td style="{html.escape(str(style), quote=True)}">'
                    f"{html.escape(str(text))}</td>"
                )
            else:
                cells.append(f"<td>{html.escape(str(value))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f'<div class="table-wrap"><table class="{html.escape(classes, quote=True)}">'
        f"<thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def render_html(
    context: dict[str, Any],
    inference: list[dict[str, Any]],
    paired: list[dict[str, Any]],
    grouped: list[dict[str, Any]],
    primary_variants: Iterable[str] = PRIMARY_VARIANTS,
) -> str:
    primary_variant_set = frozenset(str(item) for item in primary_variants)
    if not primary_variant_set:
        raise ValueError("primary_variants must not be empty")
    family_rows = [
        row
        for row in inference
        if row.get("stratum") == "family"
        and row.get("metric") == "delta_stability_ari"
        and row.get("variant") in primary_variant_set
    ]
    quality = {
        (row.get("corruption_family"), row.get("variant")): row
        for row in inference
        if row.get("stratum") == "family"
        and row.get("metric") == "delta_gt_ari_mean"
        and row.get("variant") in primary_variant_set
    }
    primary_table = []
    for row in sorted(
        family_rows,
        key=lambda item: (str(item["corruption_family"]), str(item["variant"])),
    ):
        effect = float(row["mean"])
        quality_row = quality.get((row["corruption_family"], row["variant"]))
        primary_table.append(
            [
                row["corruption_family"],
                row["variant"],
                row["n_images"],
                (_number(effect), f"background:{_cell_color(effect)}"),
                f"[{_number(row['ci95_low'])}, {_number(row['ci95_high'])}]",
                _number(row["holm_p"]),
                _number(quality_row["mean"]) if quality_row else "",
                (
                    f"[{_number(quality_row['ci95_low'])}, "
                    f"{_number(quality_row['ci95_high'])}]"
                    if quality_row
                    else ""
                ),
                _p_with_marker(quality_row["sign_flip_p"]) if quality_row else "",
            ]
        )

    sensitivity_table = []
    for row in sorted(
        (
            item
            for item in inference
            if item.get("stratum") == "family"
            and item.get("metric") == "delta_stability_ari"
            and item.get("variant") not in primary_variant_set
        ),
        key=lambda item: (str(item["corruption_family"]), str(item["variant"])),
    ):
        effect = float(row["mean"])
        sensitivity_table.append(
            [
                row["corruption_family"],
                row["variant"],
                row["n_images"],
                (_number(effect), f"background:{_cell_color(effect)}"),
                f"[{_number(row['ci95_low'])}, {_number(row['ci95_high'])}]",
                _p_with_marker(row["sign_flip_p"]),
            ]
        )

    severity_table = []
    for row in sorted(
        (
            item
            for item in inference
            if str(item.get("stratum", "")).startswith("severity=")
            and item.get("metric") == "delta_stability_ari"
            and item.get("variant") in primary_variant_set
        ),
        key=lambda item: (
            str(item["corruption_family"]),
            str(item["stratum"]),
            str(item["variant"]),
        ),
    ):
        effect = float(row["mean"])
        severity_table.append(
            [
                row["corruption_family"],
                str(row["stratum"]).removeprefix("severity="),
                row["variant"],
                (_number(effect), f"background:{_cell_color(effect)}"),
                f"[{_number(row['ci95_low'])}, {_number(row['ci95_high'])}]",
            ]
        )

    clean_table = []
    for row in sorted(
        (item for item in grouped if item.get("mode") == "clean"),
        key=lambda item: str(item["variant"]),
    ):
        clean_table.append(
            [
                row["variant"],
                row["n"],
                _number(row.get("seed_count_mean"), 1),
                _number(row.get("regions_mean"), 1),
                _number(row.get("seconds_mean")),
                _number(row.get("gt_ari_mean_mean")),
                _number(row.get("gt_boundary_f1_t1_mean_mean")),
            ]
        )

    paired_count = sum(int(row.get("n", 0)) for row in paired)
    interpretation = html.escape(str(context.get("interpretation", "")))
    configuration = html.escape(str(context.get("config_path", "")))
    split = html.escape(str(context.get("split", "")))
    image_count = html.escape(str(context.get("image_count", "")))
    max_dimension = html.escape(str(context.get("configured_max_dimension", "")))
    analysis_role = str(context.get("analysis_role", "primary"))
    analysis_role_label = {
        "primary": "Primary analysis",
        "secondary_sensitivity": "Prespecified secondary sensitivity",
        "primary_with_prespecified_sensitivity": "Primary analysis with prespecified sensitivity variants",
    }.get(analysis_role, analysis_role.replace("_", " ").title())
    analysis_role_label = html.escape(analysis_role_label)
    family_heading = (
        "Secondary sensitivity: family-level attribution"
        if analysis_role == "secondary_sensitivity"
        else "Family-level attribution"
    )
    minimum_p_values = sorted(
        {
            value
            for row in family_rows
            if (value := _minimum_attainable_p(row)) is not None
        }
    )
    minimum_p = ", ".join(_number(value) for value in minimum_p_values) or "n/a"
    low_information = any(value >= 0.05 for value in minimum_p_values)
    inference_note = (
        " Under the recorded exact or Monte Carlo test method, the minimum attainable two-sided sign-flip p value "
        "is not below 0.05, so inferential p values are diagnostic only."
        if low_information
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MonoGrowLab experiment report</title>
<style>
:root {{ color-scheme: light; font-family: Inter, Segoe UI, sans-serif; line-height: 1.45; }}
body {{ margin: 0; color: #172033; background: #f5f7fb; }}
main {{ max-width: 1180px; margin: 0 auto; padding: 32px 22px 64px; }}
h1 {{ margin-bottom: 6px; }} h2 {{ margin-top: 36px; }}
.meta {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(170px,1fr)); gap: 12px; margin: 22px 0; }}
.card {{ background: white; border: 1px solid #dce2ec; border-radius: 12px; padding: 14px 16px; box-shadow: 0 2px 10px #1f2a4410; }}
.label {{ color: #65718a; font-size: .82rem; text-transform: uppercase; letter-spacing: .05em; }}
.value {{ font-size: 1.12rem; font-weight: 650; overflow-wrap: anywhere; }}
.table-wrap {{ overflow-x: auto; background: white; border: 1px solid #dce2ec; border-radius: 12px; }}
table {{ border-collapse: collapse; width: 100%; font-size: .91rem; }}
th, td {{ padding: 9px 11px; border-bottom: 1px solid #e7ebf2; text-align: right; white-space: nowrap; }}
th {{ background: #edf2f9; color: #34405a; position: sticky; top: 0; }}
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
.note {{ border-left: 4px solid #5875c5; padding: 10px 14px; background: #eef3ff; }}
code {{ background: #e9edf5; padding: 2px 5px; border-radius: 4px; }}
</style>
</head>
<body><main>
<h1>MonoGrowLab experiment report</h1>
<p>{interpretation}</p>
<section class="meta">
  <div class="card"><div class="label">Configuration</div><div class="value">{configuration}</div></div>
  <div class="card"><div class="label">Split</div><div class="value">{split}</div></div>
  <div class="card"><div class="label">Images</div><div class="value">{image_count}</div></div>
  <div class="card"><div class="label">Maximum dimension</div><div class="value">{max_dimension}</div></div>
  <div class="card"><div class="label">Analysis role</div><div class="value">{analysis_role_label}</div></div>
  <div class="card"><div class="label">Strict pairs summarized</div><div class="value">{paired_count}</div></div>
</section>
<p class="note">Positive stability gaps indicate that reusing clean-image seeds retained more of the clean segmentation than recomputing seeds after corruption. This is an attribution result, not automatically an accuracy advantage. The ground-truth contrast is shown with its confidence interval and unadjusted sign-flip p value. Minimum attainable two-sided sign-flip p under the recorded test method: {minimum_p}.{inference_note}</p>
<h2>{family_heading}</h2>
{_table(["Corruption", "Variant", "Images", "Stability ARI gap", "95% CI", "Holm p", "GT ARI difference", "GT 95% CI", "GT exact p"], primary_table)}
<h2>Seed-policy sensitivity variants</h2>
<p>These non-primary variants are sensitivity analyses. Their exact p values are descriptive and are not included in the primary Holm family.</p>
{_table(["Corruption", "Variant", "Images", "Stability ARI gap", "95% CI", "Exact p"], sensitivity_table)}
<h2>Severity-level effects</h2>
{_table(["Corruption", "Severity", "Variant", "Stability ARI gap", "95% CI"], severity_table)}
<h2>Clean-image operating points</h2>
{_table(["Variant", "n", "Seeds", "Regions", "Runtime (s)", "GT ARI", "Boundary F1 (t=1)"], clean_table)}
<h2>Interpretation boundary</h2>
<p>Results describe the recorded configuration and dataset split only. Development and validation-subset runs are not official BSDS500 test-set benchmark claims. Boundary F1 is the documented MonoGrowLab tolerance metric, not the official BSDS500 boundary benchmark implementation. For asymmetric families such as brightness scaling, severity-level rows preserve direction-specific effects; the family-level mean is only the configured average across darkening and brightening conditions.</p>
</main></body></html>
"""
