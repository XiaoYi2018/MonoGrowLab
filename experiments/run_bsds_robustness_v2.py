"""Schema-v2 resumable BSDS500 seed-versus-growth robustness experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import PIL
import scipy
import skimage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from monogrowlab.corruptions_v2 import (  # noqa: E402
    DETERMINISTIC_FAMILIES,
    RANDOM_FAMILIES,
    apply_corruption,
    normalize_parameters,
)
from monogrowlab.datasets import list_bsds500_ids, load_bsds500_sample, resize_sample  # noqa: E402
from monogrowlab.evaluation import score_against_references, stability_scores  # noqa: E402
from monogrowlab.experiment_schema import array_sha256, canonical_hash, canonical_json  # noqa: E402
from monogrowlab.legacy_adapter import AlgorithmResult, LegacyAdapter  # noqa: E402


SCHEMA_VERSION = 2
SEVERITY_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
CORRUPTION_UNITS = {
    "gaussian_noise": "8-bit intensity standard deviation",
    "gaussian_blur": "pixels",
    "salt_pepper": "fraction of image pixels",
    "jpeg": "JPEG quality index",
    "brightness_scale": "multiplicative intensity factor",
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(PROJECT_ROOT).as_posix(): file_hash(path)
        for path in sorted(root.rglob("*.py"))
        if path.is_file()
    }


def dataset_file_index(
    payload: dict[str, Any], expected_dataset_root: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    schema_version = int(payload.get("schema_version", 0))
    if schema_version != 2:
        raise ValueError(
            "v2 experiments require dataset manifest schema_version=2 with per-file hashes; "
            f"observed {schema_version}"
        )
    if payload.get("dataset_root") != expected_dataset_root:
        raise ValueError(
            "dataset manifest root differs from config: "
            f"{payload.get('dataset_root')!r} != {expected_dataset_root!r}"
        )
    rows = payload.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("schema-v2 dataset manifest requires a non-empty files list")
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("dataset manifest file rows must be objects")
        path = str(row.get("path", ""))
        digest = str(row.get("sha256", ""))
        role = str(row.get("role", ""))
        size = row.get("bytes")
        if not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError(f"unsafe dataset manifest path: {path!r}")
        if path in index:
            raise ValueError(f"duplicate dataset manifest path: {path}")
        if role not in {"image", "ground_truth"}:
            raise ValueError(f"invalid dataset manifest role: {role!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid dataset manifest hash: {path}")
        if not isinstance(size, int) or size < 0:
            raise ValueError(f"invalid dataset manifest size: {path}")
        index[path] = row
    return index, {
        "manifest_schema_version": 2,
        "per_file_hashes_verified": True,
        "file_count": len(index),
    }


def verified_dataset_hash(
    path: Path,
    dataset_root: Path,
    index: dict[str, dict[str, Any]],
    expected_role: str,
) -> str:
    digest = file_hash(path)
    relative = path.relative_to(dataset_root).as_posix()
    row = index.get(relative)
    if row is None:
        raise RuntimeError(f"dataset file is absent from manifest: {relative}")
    if row["role"] != expected_role:
        raise RuntimeError(
            f"dataset manifest role mismatch for {relative}: {row['role']} != {expected_role}"
        )
    if int(row["bytes"]) != path.stat().st_size:
        raise RuntimeError(f"dataset file size differs from manifest: {relative}")
    if row["sha256"] != digest:
        raise RuntimeError(f"dataset file hash differs from manifest: {relative}")
    return digest


def stable_seed(
    base_seed: int,
    image_id: str,
    family: str,
    severity_id: str,
    parameters: dict[str, Any],
    replicate: int,
) -> int:
    material = {
        "base_seed": int(base_seed),
        "image_id": str(image_id),
        "family": family,
        "severity_id": severity_id,
        "parameters": parameters,
        "replicate": int(replicate),
    }
    return int.from_bytes(hashlib.sha256(canonical_json(material).encode("utf-8")).digest()[:8], "little")


def normalize_corruption_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw = config.get("corruptions")
    if not isinstance(raw, list) or not raw:
        raise ValueError("schema-v2 corruptions must be a non-empty list")
    normalized = []
    identities = set()
    for specification in raw:
        if not isinstance(specification, dict):
            raise ValueError("each corruption specification must be an object")
        family = str(specification.get("family", ""))
        replicates = int(specification.get("replicates", 1))
        base_seed = int(specification.get("base_seed", 20260917))
        severities = specification.get("severities")
        if family not in RANDOM_FAMILIES | DETERMINISTIC_FAMILIES:
            raise ValueError(f"unsupported corruption family: {family}")
        if replicates <= 0:
            raise ValueError(f"replicates must be positive for {family}")
        if family in DETERMINISTIC_FAMILIES and replicates != 1:
            raise ValueError(f"deterministic family {family} must use one replicate")
        if not isinstance(severities, list) or not severities:
            raise ValueError(f"{family} requires a non-empty severities list")
        normalized_severities = []
        for severity in severities:
            if not isinstance(severity, dict):
                raise ValueError(f"{family} severity must be an object")
            severity_id = str(severity.get("id", ""))
            if not SEVERITY_ID.fullmatch(severity_id):
                raise ValueError(f"invalid severity id: {severity_id!r}")
            parameters = normalize_parameters(family, severity.get("params"))
            identity = (family, severity_id)
            if identity in identities:
                raise ValueError(f"duplicate corruption severity: {identity}")
            identities.add(identity)
            normalized_severities.append({"id": severity_id, "params": parameters})
        normalized.append(
            {
                "family": family,
                "replicates": replicates,
                "base_seed": base_seed,
                "severities": normalized_severities,
            }
        )
    return normalized


def diagnostics(result: AlgorithmResult) -> dict[str, float | int]:
    return {
        "seconds": result.seconds,
        "loops": result.loops,
        "threshold": result.threshold,
        "coverage": result.coverage,
        "regions": result.regions,
    }


def execute_algorithm(adapter, algorithm_config, seeds, image):
    return adapter.run(
        algorithm_config["name"],
        seeds,
        image,
        eps=float(algorithm_config.get("eps", 1.0)),
        smooth_iters=int(algorithm_config.get("smooth_iters", 0)),
        fan2015_l=float(algorithm_config.get("fan2015_l", 15.0)),
    )


def immutable_metadata(
    config_path: Path,
    config: dict[str, Any],
    dataset_root: Path,
    dataset_manifest: Path,
    legacy_root: Path,
    dataset_integrity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "config_path": config_path.relative_to(PROJECT_ROOT).as_posix(),
        "config_sha256": canonical_hash(config),
        "dataset_root": dataset_root.relative_to(PROJECT_ROOT).as_posix(),
        "dataset_manifest": dataset_manifest.relative_to(PROJECT_ROOT).as_posix(),
        "dataset_manifest_sha256": file_hash(dataset_manifest),
        "dataset_integrity": dataset_integrity,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_image": skimage.__version__,
            "pillow": PIL.__version__,
        },
        "legacy_hashes": {
            path.name: file_hash(path) for path in sorted(legacy_root.glob("*.py"))
        },
        "package_hashes": source_hashes(PROJECT_ROOT / "src"),
        "runner_sha256": file_hash(Path(__file__)),
        "interpretation": config.get(
            "interpretation",
            "schema-v2 development experiment; not an official BSDS500 benchmark result",
        ),
    }


def prepare_metadata(path: Path, immutable: dict[str, Any], output_path: Path) -> None:
    if path.exists():
        if not output_path.exists():
            raise RuntimeError("metadata exists but result JSONL is missing")
        existing = json.loads(path.read_text(encoding="utf-8"))
        observed = {key: existing.get(key) for key in immutable}
        if observed != immutable:
            changed = sorted(key for key in immutable if observed.get(key) != immutable[key])
            raise RuntimeError(
                "refusing cross-version resume; immutable metadata changed: " + ", ".join(changed)
            )
        return
    if output_path.exists() and output_path.stat().st_size != 0:
        raise RuntimeError("non-empty result JSONL exists without schema-v2 metadata")
    payload = {**immutable, "created_utc": datetime.now(timezone.utc).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create the result file first.  If the process stops before metadata is
    # committed, a zero-byte JSONL is unambiguously safe to resume; a non-empty
    # metadata-free JSONL is always rejected above.
    if not output_path.exists():
        with output_path.open("x", encoding="utf-8", newline="\n"):
            pass
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def existing_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys = set()
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid JSON at line {number}: {path}") from exc
            if record.get("schema_version") != SCHEMA_VERSION:
                raise RuntimeError(f"non-v2 record at line {number}: {path}")
            key = record.get("run_key")
            if not key or key in keys:
                raise RuntimeError(f"missing or duplicate run_key at line {number}: {path}")
            keys.add(str(key))
    return keys


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("v2 runner requires config schema_version=2")
    dataset_root = (PROJECT_ROOT / config["dataset_root"]).resolve()
    dataset_manifest = (PROJECT_ROOT / config["dataset_manifest"]).resolve()
    output_path = (PROJECT_ROOT / config["output"]).resolve()
    metadata_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    legacy_root = PROJECT_ROOT / "legacy_reference" / "core"
    if not dataset_manifest.is_file():
        raise FileNotFoundError(dataset_manifest)
    dataset_manifest_payload = json.loads(dataset_manifest.read_text(encoding="utf-8"))
    dataset_index, dataset_integrity = dataset_file_index(
        dataset_manifest_payload, Path(config["dataset_root"]).as_posix()
    )

    adapter = LegacyAdapter(legacy_root)
    corruption_specs = normalize_corruption_specs(config)
    seed_modes = config.get("seed_modes")
    if (
        not isinstance(seed_modes, list)
        or len(seed_modes) != 2
        or set(seed_modes) != {"fixed_clean", "recomputed"}
    ):
        raise ValueError(
            "schema-v2 seed_modes must contain fixed_clean and recomputed exactly once"
        )
    metadata = immutable_metadata(
        config_path,
        config,
        dataset_root,
        dataset_manifest,
        legacy_root,
        dataset_integrity,
    )
    prepare_metadata(metadata_path, metadata, output_path)
    completed = existing_keys(output_path)

    image_ids = list_bsds500_ids(dataset_root, config["split"])
    if config.get("image_ids"):
        requested = list(config["image_ids"])
        unknown = sorted(set(requested) - set(image_ids))
        if unknown:
            raise ValueError(f"unknown image ids: {unknown}")
        image_ids = requested
    if config.get("limit") is not None:
        image_ids = image_ids[: int(config["limit"])]

    variants = list(config.get("variants", []))
    if not variants:
        raise ValueError("v2 runner requires explicit variants")
    variant_ids = set()
    for variant in variants:
        if not {"id", "algorithm", "seed_strategy"}.issubset(variant):
            raise ValueError("each variant requires id, algorithm, and seed_strategy")
        if variant["id"] in variant_ids:
            raise ValueError(f"duplicate variant id: {variant['id']}")
        variant_ids.add(variant["id"])

    total_written = 0
    total_skipped = 0
    for image_id in image_ids:
        sample = resize_sample(
            load_bsds500_sample(dataset_root, config["split"], image_id),
            config.get("max_dimension"),
        )
        clean_image = adapter.to_gray_uint8(sample.image)
        clean_hash = array_sha256(clean_image)
        source_image_hash = verified_dataset_hash(
            sample.image_path, dataset_root, dataset_index, "image"
        )
        ground_truth_hash = verified_dataset_hash(
            sample.ground_truth_path, dataset_root, dataset_index, "ground_truth"
        )
        clean_seed_cache = {}

        for variant in variants:
            algorithm_config = variant["algorithm"]
            seed_strategy = variant["seed_strategy"]
            seed_cache_key = canonical_hash(seed_strategy)
            if seed_cache_key not in clean_seed_cache:
                clean_seed_cache[seed_cache_key] = adapter.extract_seeds(clean_image, seed_strategy)
            clean_seeds = clean_seed_cache[seed_cache_key]
            if clean_seeds.count == 0:
                raise RuntimeError(f"no clean seeds for {image_id} using {seed_strategy}")

            clean_identity = {
                "schema_version": SCHEMA_VERSION,
                "config": metadata["config_sha256"],
                "variant_id": variant["id"],
                "image_id": image_id,
                "algorithm": algorithm_config,
                "seed_strategy": seed_strategy,
                "mode": "clean",
                "corruption_family": "clean",
                "severity_id": "clean",
                "corruption_params": {},
                "corruption_units": "none",
                "replicate": 0,
            }
            clean_key = canonical_hash(clean_identity)[:24]
            clean_result = execute_algorithm(
                adapter, algorithm_config, clean_seeds, clean_image
            )
            if clean_key in completed:
                total_skipped += 1
            else:
                append_record(
                    output_path,
                    {
                        "run_key": clean_key,
                        **clean_identity,
                        "status": "ok",
                        "created_utc": datetime.now(timezone.utc).isoformat(),
                        "height": int(clean_image.shape[0]),
                        "width": int(clean_image.shape[1]),
                        "random_seed": None,
                        "clean_image_sha256": clean_hash,
                        "corrupted_image_sha256": clean_hash,
                        "source_image_sha256": source_image_hash,
                        "ground_truth_sha256": ground_truth_hash,
                        "seed_count": clean_seeds.count,
                        **diagnostics(clean_result),
                        **score_against_references(clean_result.labels, sample.references),
                    },
                )
                completed.add(clean_key)
                total_written += 1

            for corruption in corruption_specs:
                family = corruption["family"]
                units = CORRUPTION_UNITS[family]
                for severity in corruption["severities"]:
                    severity_id = severity["id"]
                    parameters = severity["params"]
                    for replicate in range(corruption["replicates"]):
                        random_seed = (
                            stable_seed(
                                corruption["base_seed"],
                                image_id,
                                family,
                                severity_id,
                                parameters,
                                replicate,
                            )
                            if family in RANDOM_FAMILIES
                            else None
                        )
                        perturbed_image = apply_corruption(
                            clean_image,
                            family,
                            parameters,
                            seed=random_seed,
                        )
                        perturbed_hash = array_sha256(perturbed_image)

                        for mode in seed_modes:
                            identity = {
                                "schema_version": SCHEMA_VERSION,
                                "config": metadata["config_sha256"],
                                "variant_id": variant["id"],
                                "image_id": image_id,
                                "algorithm": algorithm_config,
                                "seed_strategy": seed_strategy,
                                "mode": mode,
                                "corruption_family": family,
                                "severity_id": severity_id,
                                "corruption_params": parameters,
                                "corruption_units": units,
                                "replicate": replicate,
                            }
                            key = canonical_hash(identity)[:24]
                            if key in completed:
                                total_skipped += 1
                                continue
                            try:
                                if mode == "fixed_clean":
                                    seeds = clean_seeds
                                elif mode == "recomputed":
                                    seeds = adapter.extract_seeds(perturbed_image, seed_strategy)
                                else:
                                    raise ValueError(f"unknown seed mode: {mode}")
                                if seeds.count == 0:
                                    raise RuntimeError("corruption produced zero seeds")
                                result = execute_algorithm(
                                    adapter, algorithm_config, seeds, perturbed_image
                                )
                                record = {
                                    "run_key": key,
                                    **identity,
                                    "status": "ok",
                                    "created_utc": datetime.now(timezone.utc).isoformat(),
                                    "height": int(perturbed_image.shape[0]),
                                    "width": int(perturbed_image.shape[1]),
                                    "random_seed": random_seed,
                                    "clean_image_sha256": clean_hash,
                                    "corrupted_image_sha256": perturbed_hash,
                                    "source_image_sha256": source_image_hash,
                                    "ground_truth_sha256": ground_truth_hash,
                                    "seed_count": seeds.count,
                                    **diagnostics(result),
                                    **score_against_references(result.labels, sample.references),
                                    **stability_scores(clean_result.labels, result.labels),
                                }
                            except Exception as exc:
                                record = {
                                    "run_key": key,
                                    **identity,
                                    "status": "failed",
                                    "created_utc": datetime.now(timezone.utc).isoformat(),
                                    "height": int(perturbed_image.shape[0]),
                                    "width": int(perturbed_image.shape[1]),
                                    "random_seed": random_seed,
                                    "clean_image_sha256": clean_hash,
                                    "corrupted_image_sha256": perturbed_hash,
                                    "source_image_sha256": source_image_hash,
                                    "ground_truth_sha256": ground_truth_hash,
                                    "error_type": type(exc).__name__,
                                    "error": str(exc),
                                }
                            append_record(output_path, record)
                            completed.add(key)
                            total_written += 1

    print(
        json.dumps(
            {
                "output": str(output_path),
                "written": total_written,
                "skipped": total_skipped,
                "total_records": len(completed),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
