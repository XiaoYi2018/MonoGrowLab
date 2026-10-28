"""Label-invariant region and tolerance-aware boundary metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.ndimage import binary_dilation, generate_binary_structure


@dataclass(frozen=True)
class BoundaryScores:
    """Precision, recall, and F-score for two segmentation boundaries."""

    precision: float
    recall: float
    f1: float
    reference_pixels: int
    candidate_pixels: int
    tolerance: int

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def _validate_pair(reference: np.ndarray, candidate: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ref = np.asarray(reference)
    cand = np.asarray(candidate)
    if ref.ndim != 2 or cand.ndim != 2:
        raise ValueError("reference and candidate must both be two-dimensional label maps")
    if ref.shape != cand.shape:
        raise ValueError("reference and candidate must have identical shapes")
    if ref.size == 0:
        raise ValueError("empty label maps are not supported")
    return ref, cand


def boundary_map(labels: np.ndarray, connectivity: int = 1) -> np.ndarray:
    """Return an internal boundary map for a 2-D integer label image.

    ``connectivity=1`` compares horizontal and vertical neighbors. With
    ``connectivity=2``, both diagonal directions are included as well. Each
    label transition marks both pixels adjacent to the transition, which makes
    the result symmetric with respect to label ordering.
    """

    arr = np.asarray(labels)
    if arr.ndim != 2:
        raise ValueError("labels must be a two-dimensional array")
    if connectivity not in (1, 2):
        raise ValueError("connectivity must be 1 or 2")

    result = np.zeros(arr.shape, dtype=bool)

    horizontal = arr[:, 1:] != arr[:, :-1]
    result[:, 1:] |= horizontal
    result[:, :-1] |= horizontal

    vertical = arr[1:, :] != arr[:-1, :]
    result[1:, :] |= vertical
    result[:-1, :] |= vertical

    if connectivity == 2:
        diagonal_down = arr[1:, 1:] != arr[:-1, :-1]
        result[1:, 1:] |= diagonal_down
        result[:-1, :-1] |= diagonal_down

        diagonal_up = arr[1:, :-1] != arr[:-1, 1:]
        result[1:, :-1] |= diagonal_up
        result[:-1, 1:] |= diagonal_up

    return result


def _dilated(boundary: np.ndarray, tolerance: int, connectivity: int) -> np.ndarray:
    if tolerance == 0:
        return boundary
    structure = generate_binary_structure(2, connectivity)
    return binary_dilation(boundary, structure=structure, iterations=tolerance)


def boundary_scores(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    tolerance: int = 0,
    connectivity: int = 1,
) -> BoundaryScores:
    """Compute symmetric tolerance-aware boundary precision, recall, and F1.

    Candidate boundary pixels are counted as precise when they fall within the
    dilated reference boundary. Reference pixels are recalled when they fall
    within the dilated candidate boundary. This is label-invariant and avoids
    treating a one-pixel registration shift as total failure.
    """

    ref, cand = _validate_pair(reference, candidate)
    if not isinstance(tolerance, (int, np.integer)) or tolerance < 0:
        raise ValueError("tolerance must be a non-negative integer")
    if connectivity not in (1, 2):
        raise ValueError("connectivity must be 1 or 2")

    ref_boundary = boundary_map(ref, connectivity=connectivity)
    cand_boundary = boundary_map(cand, connectivity=connectivity)
    n_ref = int(ref_boundary.sum())
    n_cand = int(cand_boundary.sum())

    if n_ref == 0 and n_cand == 0:
        return BoundaryScores(1.0, 1.0, 1.0, 0, 0, int(tolerance))
    if n_cand == 0:
        return BoundaryScores(0.0, 0.0, 0.0, n_ref, 0, int(tolerance))
    if n_ref == 0:
        return BoundaryScores(0.0, 0.0, 0.0, 0, n_cand, int(tolerance))

    dilated_ref = _dilated(ref_boundary, int(tolerance), connectivity)
    dilated_cand = _dilated(cand_boundary, int(tolerance), connectivity)
    precision = float(np.logical_and(cand_boundary, dilated_ref).sum() / n_cand)
    recall = float(np.logical_and(ref_boundary, dilated_cand).sum() / n_ref)
    denominator = precision + recall
    f1 = 0.0 if denominator == 0.0 else float(2.0 * precision * recall / denominator)
    return BoundaryScores(precision, recall, f1, n_ref, n_cand, int(tolerance))


def _comb2(values: np.ndarray | float) -> np.ndarray | float:
    return values * (values - 1.0) / 2.0


def _contingency(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    ref, cand = _validate_pair(reference, candidate)
    _, ref_inverse = np.unique(ref.ravel(), return_inverse=True)
    _, cand_inverse = np.unique(cand.ravel(), return_inverse=True)
    n_cand = int(cand_inverse.max()) + 1
    joint = ref_inverse.astype(np.int64) * n_cand + cand_inverse.astype(np.int64)
    return np.bincount(joint, minlength=(int(ref_inverse.max()) + 1) * n_cand).reshape(-1, n_cand)


def adjusted_rand_index(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Compute the adjusted Rand index without requiring scikit-learn."""

    table = _contingency(reference, candidate).astype(np.float64)
    n = float(table.sum())
    if n < 2:
        return 1.0
    row = table.sum(axis=1)
    column = table.sum(axis=0)
    observed = float(_comb2(table).sum())
    row_pairs = float(_comb2(row).sum())
    column_pairs = float(_comb2(column).sum())
    total_pairs = float(_comb2(n))
    expected = row_pairs * column_pairs / total_pairs
    maximum = 0.5 * (row_pairs + column_pairs)
    denominator = maximum - expected
    if denominator == 0.0:
        return 1.0 if observed == maximum else 0.0
    return float((observed - expected) / denominator)


def variation_of_information(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    """Return split, merge, and total variation of information in nats."""

    table = _contingency(reference, candidate).astype(np.float64)
    probability = table / table.sum()
    p_ref = probability.sum(axis=1)
    p_cand = probability.sum(axis=0)
    rows, columns = np.nonzero(probability)
    joint = probability[rows, columns]
    split = float(np.sum(joint * (np.log(p_ref[rows]) - np.log(joint))))
    merge = float(np.sum(joint * (np.log(p_cand[columns]) - np.log(joint))))
    return {"split": split, "merge": merge, "total": split + merge}


def partition_scores(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    """Return label-invariant region agreement scores."""

    vi = variation_of_information(reference, candidate)
    return {
        "adjusted_rand_index": adjusted_rand_index(reference, candidate),
        "vi_split": vi["split"],
        "vi_merge": vi["merge"],
        "vi_total": vi["total"],
    }

