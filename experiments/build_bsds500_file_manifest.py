"""Build a deterministic per-file integrity manifest for an extracted BSDS500 tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("train", "val", "test")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(dataset_root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    files = []
    counts = {"images": {}, "ground_truth": {}}
    for split in SPLITS:
        image_paths = sorted((dataset_root / "images" / split).glob("*.jpg"))
        truth_paths = sorted((dataset_root / "groundTruth" / split).glob("*.mat"))
        counts["images"][split] = len(image_paths)
        counts["ground_truth"][split] = len(truth_paths)
        for role, paths in (("image", image_paths), ("ground_truth", truth_paths)):
            for path in paths:
                files.append(
                    {
                        "bytes": path.stat().st_size,
                        "image_id": path.stem,
                        "path": path.relative_to(dataset_root).as_posix(),
                        "role": role,
                        "sha256": file_hash(path),
                        "split": split,
                    }
                )
    return files, counts


def validate_inventory(
    files: list[dict[str, Any]],
    counts: dict[str, dict[str, int]],
    source: dict[str, Any],
) -> None:
    expected = {
        "images": source.get("image_counts"),
        "ground_truth": source.get("ground_truth_counts"),
    }
    if counts != expected:
        raise RuntimeError(f"dataset counts differ from source manifest: {counts} != {expected}")
    image_ids = {(row["split"], row["image_id"]) for row in files if row["role"] == "image"}
    truth_ids = {
        (row["split"], row["image_id"])
        for row in files
        if row["role"] == "ground_truth"
    }
    if image_ids != truth_ids:
        raise RuntimeError(
            "image/ground-truth identifier mismatch: "
            f"images_only={sorted(image_ids - truth_ids)[:5]}, "
            f"truth_only={sorted(truth_ids - image_ids)[:5]}"
        )


def build_manifest(
    dataset_root: Path, source_manifest_path: Path
) -> dict[str, Any]:
    source = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    files, counts = inventory(dataset_root)
    validate_inventory(files, counts, source)
    return {
        "schema_version": 2,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": source.get("name"),
        "release": source.get("release"),
        "dataset_root": dataset_root.relative_to(PROJECT_ROOT).as_posix(),
        "source_manifest": source_manifest_path.relative_to(PROJECT_ROOT).as_posix(),
        "source_manifest_sha256": file_hash(source_manifest_path),
        "archive_relative_path": source.get("archive_relative_path"),
        "archive_sha256": source.get("archive_sha256"),
        "source_url": source.get("source_url"),
        "source_page": source.get("source_page"),
        "citation": source.get("citation"),
        "redistribution_policy": source.get("redistribution_policy"),
        "counts": counts,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    source_manifest = args.source_manifest.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite manifest: {output}")
    payload = build_manifest(dataset_root, source_manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(
        json.dumps(
            {
                "output": str(output),
                "files": len(payload["files"]),
                "sha256": file_hash(output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
