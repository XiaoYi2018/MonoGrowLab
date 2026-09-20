"""Schema normalization and strict pairing for MonoGrowLab experiment records."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Iterable


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def array_sha256(array: Any) -> str:
    """Hash dtype, shape, and contiguous bytes rather than bytes alone."""

    contiguous = array.copy(order="C")
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("ascii"))
    digest.update(canonical_json(list(contiguous.shape)).encode("ascii"))
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def variant_label(record: dict[str, Any]) -> str:
    if record.get("variant_id") not in {None, ""}:
        return str(record["variant_id"])
    algorithm = record.get("algorithm")
    seed_strategy = record.get("seed_strategy", {"name": "legacy-default"})
    if not isinstance(algorithm, dict):
        raise RuntimeError("record without variant_id requires an algorithm object")
    return f"{algorithm.get('name', 'unknown')}|{canonical_json(seed_strategy)}"


def normalized_condition(record: dict[str, Any]) -> dict[str, Any]:
    """Read schema-v2 fields or map a schema-v1 Gaussian record without changing it."""

    if "corruption_family" in record:
        family = str(record["corruption_family"])
        severity_id = str(record["severity_id"])
        parameters = record.get("corruption_params")
        if not isinstance(parameters, dict):
            raise RuntimeError("schema-v2 corruption_params must be an object")
        return {
            "schema_version": int(record.get("schema_version", 2)),
            "family": family,
            "severity_id": severity_id,
            "parameters": parameters,
            "units": str(record.get("corruption_units", "")),
        }

    if "sigma" in record:
        sigma = float(record["sigma"])
        if str(record.get("mode")) == "clean":
            return {
                "schema_version": 1,
                "family": "clean",
                "severity_id": "clean",
                "parameters": {},
                "units": "none",
            }
        return {
            "schema_version": 1,
            "family": "gaussian_noise",
            "severity_id": f"sigma_{sigma:g}",
            "parameters": {"sigma": sigma},
            "units": "8-bit intensity standard deviation",
        }
    raise RuntimeError("record has neither schema-v2 corruption fields nor legacy sigma")


def validate_single_run(
    records: Iterable[dict[str, Any]], expected_config_hash: str | None = None
) -> str:
    """Reject record collections assembled from multiple experiment configs."""

    records = list(records)
    if any(record.get("config") in {None, ""} for record in records):
        raise RuntimeError("input contains records without a configuration hash")
    config_hashes = {str(record["config"]) for record in records}
    if len(config_hashes) != 1:
        raise RuntimeError(
            f"refusing records from multiple experiment configs: {sorted(config_hashes)}"
        )
    observed = next(iter(config_hashes))
    if expected_config_hash is not None and observed != expected_config_hash:
        raise RuntimeError(
            "record configuration hash differs from run metadata: "
            f"{observed} != {expected_config_hash}"
        )
    return observed


def pair_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return strict fixed/recomputed pairs, failing on missing or inconsistent records."""

    records = list(records)
    validate_single_run(records)
    failures = [record for record in records if record.get("status") != "ok"]
    if failures:
        raise RuntimeError(f"input contains {len(failures)} failed records")
    schema_versions = {
        int(record.get("schema_version", 2 if "corruption_family" in record else 1))
        for record in records
    }
    if not schema_versions.issubset({1, 2}):
        raise RuntimeError(f"unsupported record schema versions: {sorted(schema_versions)}")
    if len(schema_versions) != 1:
        raise RuntimeError(
            f"refusing mixed record schema versions: {sorted(schema_versions)}"
        )

    grouped: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    conditions: dict[tuple[Any, ...], dict[str, Any]] = {}
    clean_records: dict[tuple[str, str, int], dict[str, Any]] = {}
    for record in records:
        mode = str(record.get("mode"))
        if mode == "clean":
            condition = normalized_condition(record)
            clean_key = (
                variant_label(record),
                str(record["image_id"]),
                condition["schema_version"],
            )
            if clean_key in clean_records:
                raise RuntimeError(f"duplicate clean record: {clean_key}")
            clean_records[clean_key] = record
            continue
        if mode not in {"fixed_clean", "recomputed"}:
            raise RuntimeError(f"unexpected mode: {mode}")
        condition = normalized_condition(record)
        key = (
            variant_label(record),
            str(record["image_id"]),
            condition["family"],
            condition["severity_id"],
            canonical_json(condition["parameters"]),
            int(record["replicate"]),
            condition["schema_version"],
        )
        if mode in grouped[key]:
            raise RuntimeError(f"duplicate paired mode {mode}: {key}")
        grouped[key][mode] = record
        conditions[key] = condition

    paired = []
    for key, modes in sorted(grouped.items(), key=lambda item: tuple(str(x) for x in item[0])):
        missing = {"fixed_clean", "recomputed"} - set(modes)
        if missing:
            raise RuntimeError(f"incomplete pair {key}; missing {sorted(missing)}")
        fixed = modes["fixed_clean"]
        recomputed = modes["recomputed"]
        condition = conditions[key]
        clean_key = (str(key[0]), str(key[1]), int(condition["schema_version"]))
        clean = clean_records.get(clean_key)
        if clean is None:
            raise RuntimeError(f"missing clean record for pair: {key}")

        exact_fields = (
            "config",
            "image_id",
            "algorithm",
            "seed_strategy",
            "height",
            "width",
            "replicate",
            "random_seed",
            "clean_image_sha256",
            "corrupted_image_sha256",
            "source_image_sha256",
            "ground_truth_sha256",
        )
        for field in exact_fields:
            fixed_value = fixed.get(field)
            recomputed_value = recomputed.get(field)
            if field.endswith("_sha256") and condition["schema_version"] == 1:
                continue
            if fixed_value != recomputed_value:
                raise RuntimeError(f"pair mismatch in {field}: {key}")

        clean_link_fields = (
            "config",
            "image_id",
            "algorithm",
            "seed_strategy",
            "height",
            "width",
            "clean_image_sha256",
            "source_image_sha256",
            "ground_truth_sha256",
        )
        for field in clean_link_fields:
            if field.endswith("_sha256") and condition["schema_version"] == 1:
                continue
            if fixed.get(field) != clean.get(field):
                raise RuntimeError(f"clean-record mismatch in {field}: {key}")
        if condition["schema_version"] == 2 and (
            clean.get("corrupted_image_sha256") != clean.get("clean_image_sha256")
        ):
            raise RuntimeError(f"clean record has inconsistent image hashes: {clean_key}")

        paired.append(
            {
                "schema_version": condition["schema_version"],
                "variant": key[0],
                "image_id": key[1],
                "corruption_family": condition["family"],
                "severity_id": condition["severity_id"],
                "corruption_params": canonical_json(condition["parameters"]),
                "corruption_units": condition["units"],
                "replicate": key[5],
                "random_seed": fixed.get("random_seed"),
                "corrupted_image_sha256": fixed.get("corrupted_image_sha256", ""),
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
                "fixed_gt_ari_mean": float(fixed["gt_ari_mean"]),
                "recomputed_gt_ari_mean": float(recomputed["gt_ari_mean"]),
                "delta_gt_ari_mean": float(fixed["gt_ari_mean"])
                - float(recomputed["gt_ari_mean"]),
                "fixed_gt_vi_total_mean": float(fixed["gt_vi_total_mean"]),
                "recomputed_gt_vi_total_mean": float(recomputed["gt_vi_total_mean"]),
                "fixed_advantage_gt_vi_total_mean": float(
                    recomputed["gt_vi_total_mean"]
                )
                - float(fixed["gt_vi_total_mean"]),
                "fixed_gt_boundary_f1_t1_mean": float(
                    fixed["gt_boundary_f1_t1_mean"]
                ),
                "recomputed_gt_boundary_f1_t1_mean": float(
                    recomputed["gt_boundary_f1_t1_mean"]
                ),
                "delta_gt_boundary_f1_t1_mean": float(
                    fixed["gt_boundary_f1_t1_mean"]
                )
                - float(recomputed["gt_boundary_f1_t1_mean"]),
                "fixed_seed_count": int(fixed["seed_count"]),
                "recomputed_seed_count": int(recomputed["seed_count"]),
                "recomputed_minus_fixed_seed_count": int(recomputed["seed_count"])
                - int(fixed["seed_count"]),
            }
        )
    if not paired:
        raise RuntimeError("no perturbed pairs")
    return paired
