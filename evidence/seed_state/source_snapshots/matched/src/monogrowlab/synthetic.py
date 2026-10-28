"""Small deterministic fixtures for correctness and smoke testing."""

from __future__ import annotations

import numpy as np


def extrema_fixture(size: int = 49) -> tuple[np.ndarray, np.ndarray]:
    """Create an 8-bit image with several strict extrema and reference basins.

    The label map is a geometric reference partition. It is not intended as a
    claim that any legacy algorithm must recover the partition exactly; it
    provides a stable, documented input for smoke tests and metric checks.
    """

    if size < 17 or size % 2 == 0:
        raise ValueError("size must be an odd integer of at least 17")
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    scale = size / 49.0
    peak_a = 92.0 * np.exp(-((x - 14 * scale) ** 2 + (y - 15 * scale) ** 2) / (2 * (5.2 * scale) ** 2))
    peak_b = 78.0 * np.exp(-((x - 35 * scale) ** 2 + (y - 31 * scale) ** 2) / (2 * (6.0 * scale) ** 2))
    valley = 86.0 * np.exp(-((x - 31 * scale) ** 2 + (y - 13 * scale) ** 2) / (2 * (4.5 * scale) ** 2))
    slope = 0.73 * x + 0.29 * y
    image = np.clip(np.rint(118.0 + slope + peak_a + peak_b - valley), 0, 255).astype(np.uint8)

    centers = np.asarray(
        [[15 * scale, 14 * scale], [31 * scale, 35 * scale], [13 * scale, 31 * scale]],
        dtype=np.float64,
    )
    coordinates = np.stack([y, x], axis=-1)
    distances = ((coordinates[:, :, None, :] - centers[None, None, :, :]) ** 2).sum(axis=-1)
    labels = np.argmin(distances, axis=2).astype(np.int32) + 1
    return image, labels

