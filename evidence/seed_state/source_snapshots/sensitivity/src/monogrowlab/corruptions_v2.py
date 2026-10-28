"""Version-2 corruption operators with explicit, auditable parameters."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter


RANDOM_FAMILIES = frozenset({"gaussian_noise", "salt_pepper"})
DETERMINISTIC_FAMILIES = frozenset(
    {"gaussian_blur", "jpeg", "brightness_scale"}
)
SUPPORTED_FAMILIES = RANDOM_FAMILIES | DETERMINISTIC_FAMILIES


def _uint8_gray(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.dtype != np.uint8:
        raise ValueError("corruptions require a uint8 image")
    if array.ndim != 2:
        raise ValueError("corruptions require a two-dimensional grayscale image")
    return array


def normalize_parameters(family: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Validate a family-specific mapping and return its canonical representation."""

    if family not in SUPPORTED_FAMILIES:
        raise ValueError(f"unsupported corruption family: {family}")
    if not isinstance(parameters, dict):
        raise ValueError("corruption parameters must be an object")

    expected = {
        "gaussian_noise": {"sigma"},
        "gaussian_blur": {"sigma_px", "truncate", "boundary_mode"},
        "salt_pepper": {"amount", "salt_fraction", "sampling"},
        "jpeg": {"quality", "subsampling", "optimize", "progressive"},
        "brightness_scale": {"factor", "rounding", "clipping"},
    }[family]
    if set(parameters) != expected:
        raise ValueError(
            f"{family} parameters must be exactly {sorted(expected)}; "
            f"received {sorted(parameters)}"
        )

    if family == "gaussian_noise":
        sigma = float(parameters["sigma"])
        if sigma <= 0:
            raise ValueError("gaussian_noise sigma must be positive")
        return {"sigma": sigma}

    if family == "gaussian_blur":
        sigma = float(parameters["sigma_px"])
        truncate = float(parameters["truncate"])
        boundary_mode = str(parameters["boundary_mode"])
        if sigma <= 0 or truncate <= 0:
            raise ValueError("gaussian_blur sigma_px and truncate must be positive")
        if boundary_mode != "reflect":
            raise ValueError("gaussian_blur boundary_mode must be reflect")
        return {
            "sigma_px": sigma,
            "truncate": truncate,
            "boundary_mode": boundary_mode,
        }

    if family == "salt_pepper":
        amount = float(parameters["amount"])
        salt_fraction = float(parameters["salt_fraction"])
        sampling = str(parameters["sampling"])
        if not 0.0 < amount <= 1.0:
            raise ValueError("salt_pepper amount must be in (0, 1]")
        if not 0.0 <= salt_fraction <= 1.0:
            raise ValueError("salt_pepper salt_fraction must be in [0, 1]")
        if sampling != "without_replacement":
            raise ValueError("salt_pepper sampling must be without_replacement")
        return {
            "amount": amount,
            "salt_fraction": salt_fraction,
            "sampling": sampling,
        }

    if family == "jpeg":
        quality = int(parameters["quality"])
        subsampling = int(parameters["subsampling"])
        optimize = parameters["optimize"]
        progressive = parameters["progressive"]
        if not 1 <= quality <= 100:
            raise ValueError("jpeg quality must be in [1, 100]")
        if subsampling != 0:
            raise ValueError("jpeg subsampling must be 0")
        if not isinstance(optimize, bool) or not isinstance(progressive, bool):
            raise ValueError("jpeg optimize and progressive must be booleans")
        if optimize or progressive:
            raise ValueError("jpeg optimize and progressive must both be false")
        return {
            "quality": quality,
            "subsampling": subsampling,
            "optimize": optimize,
            "progressive": progressive,
        }

    factor = float(parameters["factor"])
    rounding = str(parameters["rounding"])
    clipping = str(parameters["clipping"])
    if factor <= 0:
        raise ValueError("brightness_scale factor must be positive")
    if factor == 1.0:
        raise ValueError("brightness_scale factor=1 is the clean identity and must be bypassed")
    if rounding != "nearest_even" or clipping != "uint8_0_255":
        raise ValueError(
            "brightness_scale requires rounding=nearest_even and clipping=uint8_0_255"
        )
    return {"factor": factor, "rounding": rounding, "clipping": clipping}


def apply_corruption(
    image: np.ndarray,
    family: str,
    parameters: dict[str, Any],
    *,
    seed: int | None,
) -> np.ndarray:
    """Apply one schema-v2 corruption and return uint8 grayscale output."""

    array = _uint8_gray(image)
    params = normalize_parameters(family, parameters)
    if family in RANDOM_FAMILIES and seed is None:
        raise ValueError(f"random corruption {family} requires a seed")
    if family in DETERMINISTIC_FAMILIES and seed is not None:
        raise ValueError(f"deterministic corruption {family} requires seed=None")

    if family == "gaussian_noise":
        generator = np.random.default_rng(seed)
        output = array.astype(np.float64) + generator.normal(
            0.0, params["sigma"], size=array.shape
        )
        return np.clip(np.rint(output), 0, 255).astype(np.uint8)

    if family == "gaussian_blur":
        output = gaussian_filter(
            array.astype(np.float64),
            sigma=params["sigma_px"],
            mode=params["boundary_mode"],
            truncate=params["truncate"],
        )
        return np.clip(np.rint(output), 0, 255).astype(np.uint8)

    if family == "salt_pepper":
        generator = np.random.default_rng(seed)
        pixel_count = array.size
        changed_count = min(pixel_count, int(round(params["amount"] * pixel_count)))
        salt_count = int(round(params["salt_fraction"] * changed_count))
        pepper_count = changed_count - salt_count
        selected = generator.choice(pixel_count, size=changed_count, replace=False)
        output = array.copy().reshape(-1)
        output[selected[:salt_count]] = 255
        output[selected[salt_count : salt_count + pepper_count]] = 0
        return output.reshape(array.shape)

    if family == "jpeg":
        buffer = BytesIO()
        Image.fromarray(array, mode="L").save(
            buffer,
            format="JPEG",
            quality=params["quality"],
            subsampling=params["subsampling"],
            optimize=params["optimize"],
            progressive=params["progressive"],
        )
        buffer.seek(0)
        with Image.open(buffer) as decoded:
            return np.asarray(decoded.convert("L"), dtype=np.uint8).copy()

    if family == "brightness_scale":
        output = array.astype(np.float64) * params["factor"]
        return np.clip(np.rint(output), 0, 255).astype(np.uint8)

    raise AssertionError(f"unreachable family: {family}")
