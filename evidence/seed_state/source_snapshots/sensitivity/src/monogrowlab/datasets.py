"""Dataset readers used by MonoGrowLab experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from skimage.io import imread
from skimage.transform import resize


@dataclass(frozen=True)
class SegmentationSample:
    image_id: str
    image: np.ndarray
    references: tuple[np.ndarray, ...]
    image_path: Path
    ground_truth_path: Path


def list_bsds500_ids(data_root: Path, split: str) -> list[str]:
    if split not in {"train", "val", "test"}:
        raise ValueError("split must be train, val, or test")
    image_root = data_root / "images" / split
    truth_root = data_root / "groundTruth" / split
    if not image_root.is_dir() or not truth_root.is_dir():
        raise FileNotFoundError(
            "BSDS500 split directories are missing for "
            f"{split!r} under {data_root}. Fetch or unpack BSDS500 before running."
        )
    image_ids = {path.stem for path in image_root.glob("*.jpg")}
    truth_ids = {path.stem for path in truth_root.glob("*.mat")}
    missing_truth = sorted(image_ids - truth_ids)
    missing_images = sorted(truth_ids - image_ids)
    if missing_truth or missing_images:
        raise RuntimeError(
            f"BSDS500 pairing mismatch: missing_truth={missing_truth[:5]}, "
            f"missing_images={missing_images[:5]}"
        )
    if not image_ids:
        raise FileNotFoundError(
            "no BSDS500 image/ground-truth pairs found for "
            f"{split!r} under {data_root}. Fetch or unpack BSDS500 before running."
        )
    return sorted(image_ids)


def load_bsds500_sample(data_root: Path, split: str, image_id: str) -> SegmentationSample:
    image_path = data_root / "images" / split / f"{image_id}.jpg"
    truth_path = data_root / "groundTruth" / split / f"{image_id}.mat"
    if not image_path.is_file() or not truth_path.is_file():
        raise FileNotFoundError(f"missing BSDS500 pair for {split}/{image_id}")
    image = np.asarray(imread(image_path))
    raw = loadmat(truth_path, simplify_cells=True)["groundTruth"]
    if isinstance(raw, dict):
        raw = [raw]
    references = tuple(np.asarray(item["Segmentation"], dtype=np.int32) for item in raw)
    if not references:
        raise RuntimeError(f"no ground-truth segmentations in {truth_path}")
    if any(reference.shape != image.shape[:2] for reference in references):
        raise RuntimeError(f"ground-truth shape mismatch in {truth_path}")
    return SegmentationSample(image_id, image, references, image_path, truth_path)


def resize_sample(sample: SegmentationSample, max_dimension: int | None) -> SegmentationSample:
    if max_dimension is None:
        return sample
    if max_dimension < 16:
        raise ValueError("max_dimension must be at least 16")
    height, width = sample.image.shape[:2]
    if max(height, width) <= max_dimension:
        return sample
    scale = max_dimension / max(height, width)
    shape = (max(1, round(height * scale)), max(1, round(width * scale)))
    if sample.image.ndim == 3:
        image_shape = (*shape, sample.image.shape[2])
    else:
        image_shape = shape
    image = resize(
        sample.image,
        image_shape,
        order=1,
        preserve_range=True,
        anti_aliasing=True,
    ).astype(sample.image.dtype)
    references = tuple(
        resize(reference, shape, order=0, preserve_range=True, anti_aliasing=False).astype(np.int32)
        for reference in sample.references
    )
    return SegmentationSample(
        sample.image_id,
        image,
        references,
        sample.image_path,
        sample.ground_truth_path,
    )
