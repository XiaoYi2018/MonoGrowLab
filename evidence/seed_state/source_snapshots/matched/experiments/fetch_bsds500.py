"""Fetch and inventory the official January 2013 BSDS500 release."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_URL = "https://www2.eecs.berkeley.edu/Research/Projects/CS/vision/grouping/BSR/BSR_bsds500.tgz"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing archive: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "MonoGrowLab/0.1 dataset fetcher"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("xb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)


def validate_members(archive: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"archive member escapes destination: {member.name}")
        if member.issym() or member.islnk():
            raise ValueError(f"links are not accepted in the dataset archive: {member.name}")


def extract(archive_path: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"refusing to merge into existing dataset directory: {destination}")
    destination.mkdir(parents=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        validate_members(archive, destination)
        archive.extractall(destination, filter="data")


def count_files(root: Path, suffix: str) -> dict[str, int]:
    result = {}
    for split in ("train", "val", "test"):
        directory = root / split
        result[split] = sum(1 for path in directory.glob(f"*{suffix}") if path.is_file())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--existing-archive", type=Path)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    archive_path = project_root / "data" / "cache" / "BSR_bsds500.tgz"
    extraction_root = project_root / "data" / "raw" / "BSDS500_official_2013"
    manifest_path = project_root / "data" / "manifests" / "bsds500_official_2013.json"
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite existing manifest: {manifest_path}")

    if args.existing_archive is None:
        temporary_root = Path(tempfile.mkdtemp(prefix="monogrow-bsds500-"))
        temporary_archive = temporary_root / "BSR_bsds500.tgz"
        download(args.url, temporary_archive)
    else:
        temporary_archive = args.existing_archive.resolve()
        temporary_root = temporary_archive.parent
        if not temporary_archive.is_file():
            raise FileNotFoundError(temporary_archive)
    archive_sha256 = hash_file(temporary_archive)
    archive_bytes = temporary_archive.stat().st_size
    if archive_path.exists():
        raise FileExistsError(f"archive appeared during download: {archive_path}")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(temporary_archive, archive_path)
    extract(archive_path, extraction_root)

    data_root = extraction_root / "BSR" / "BSDS500" / "data"
    image_counts = count_files(data_root / "images", ".jpg")
    ground_truth_counts = count_files(data_root / "groundTruth", ".mat")
    expected = {"train": 200, "val": 100, "test": 200}
    if image_counts != expected or ground_truth_counts != expected:
        raise RuntimeError(
            f"unexpected split counts: images={image_counts}, ground_truth={ground_truth_counts}"
        )

    payload = {
        "schema_version": 1,
        "name": "Berkeley Segmentation Data Set and Benchmarks 500",
        "release": "January 2013 resource update",
        "source_url": args.url,
        "source_page": "https://www2.eecs.berkeley.edu/Research/Projects/CS/vision/grouping/resources.html",
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "archive_relative_path": archive_path.relative_to(project_root).as_posix(),
        "archive_bytes": archive_bytes,
        "archive_sha256": archive_sha256,
        "extracted_relative_path": extraction_root.relative_to(project_root).as_posix(),
        "image_counts": image_counts,
        "ground_truth_counts": ground_truth_counts,
        "benchmark_rule": "Tune only on train/validation; run fixed parameters once on test; report the complete selected metric set.",
        "citation": {
            "authors": "P. Arbelaez, M. Maire, C. Fowlkes, and J. Malik",
            "title": "Contour Detection and Hierarchical Image Segmentation",
            "journal": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "volume": 33,
            "issue": 5,
            "pages": "898-916",
            "year": 2011,
            "doi": "10.1109/TPAMI.2010.161",
        },
        "redistribution_policy": "Dataset files stay in ignored local data directories; only this manifest is versioned.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"temporary source retained for audit: {temporary_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
