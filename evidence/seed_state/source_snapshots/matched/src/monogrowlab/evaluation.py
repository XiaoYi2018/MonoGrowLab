"""Evaluation helpers for datasets with multiple human segmentations."""

from __future__ import annotations

import numpy as np

from .metrics import boundary_scores, partition_scores


def score_against_references(
    candidate: np.ndarray,
    references: tuple[np.ndarray, ...],
    *,
    boundary_tolerances: tuple[int, ...] = (0, 1),
) -> dict[str, float]:
    if not references:
        raise ValueError("at least one reference segmentation is required")
    partitions = [partition_scores(reference, candidate) for reference in references]
    result = {
        "gt_reference_count": float(len(references)),
        "gt_ari_mean": float(np.mean([score["adjusted_rand_index"] for score in partitions])),
        "gt_ari_best": float(np.max([score["adjusted_rand_index"] for score in partitions])),
        "gt_vi_total_mean": float(np.mean([score["vi_total"] for score in partitions])),
        "gt_vi_total_best": float(np.min([score["vi_total"] for score in partitions])),
        "gt_vi_split_mean": float(np.mean([score["vi_split"] for score in partitions])),
        "gt_vi_merge_mean": float(np.mean([score["vi_merge"] for score in partitions])),
    }
    for tolerance in boundary_tolerances:
        values = [
            boundary_scores(reference, candidate, tolerance=tolerance).f1
            for reference in references
        ]
        result[f"gt_boundary_f1_t{tolerance}_mean"] = float(np.mean(values))
        result[f"gt_boundary_f1_t{tolerance}_best"] = float(np.max(values))
    return result


def stability_scores(clean: np.ndarray, perturbed: np.ndarray) -> dict[str, float]:
    partition = partition_scores(clean, perturbed)
    return {
        "stability_ari": partition["adjusted_rand_index"],
        "stability_vi_total": partition["vi_total"],
        "stability_vi_split": partition["vi_split"],
        "stability_vi_merge": partition["vi_merge"],
        "stability_boundary_f1_t0": boundary_scores(clean, perturbed, tolerance=0).f1,
        "stability_boundary_f1_t1": boundary_scores(clean, perturbed, tolerance=1).f1,
    }

