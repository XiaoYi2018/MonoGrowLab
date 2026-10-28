"""Deterministic image perturbations."""

from __future__ import annotations

import numpy as np


def gaussian_noise(image: np.ndarray, sigma: float, seed: int) -> np.ndarray:
    """Add zero-mean Gaussian noise in 8-bit intensity units."""

    if sigma < 0:
        raise ValueError("sigma must be non-negative")
    arr = np.asarray(image)
    if arr.dtype != np.uint8:
        raise ValueError("gaussian_noise expects a uint8 image")
    generator = np.random.default_rng(seed)
    noisy = arr.astype(np.float64) + generator.normal(0.0, float(sigma), size=arr.shape)
    return np.clip(np.rint(noisy), 0, 255).astype(np.uint8)

