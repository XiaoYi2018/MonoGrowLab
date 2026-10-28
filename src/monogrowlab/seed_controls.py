"""Seed diagnostics and cardinality-matched controls for supplementary analyses."""
from __future__ import annotations

import hashlib
import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
from .legacy_adapter import SeedBundle


def validate_bundle(bundle: SeedBundle) -> None:
    n = bundle.count
    if n <= 0:
        raise ValueError('seed bundle is empty')
    if bundle.labels.ndim != 2 or bundle.y.shape != (n,) or bundle.x.shape != (n,) or bundle.statistics.shape != (n, 2):
        raise ValueError('inconsistent seed bundle dimensions')
    h, w = bundle.labels.shape
    if np.any(bundle.y < 0) or np.any(bundle.y >= h) or np.any(bundle.x < 0) or np.any(bundle.x >= w):
        raise ValueError('seed coordinate outside image')
    ids = bundle.labels[bundle.y, bundle.x]
    if not np.array_equal(np.abs(ids), np.arange(1, n + 1)):
        raise ValueError('seed labels must index their coordinate/statistics rows')
    if np.count_nonzero(bundle.labels) != n or not np.isfinite(bundle.statistics).all():
        raise ValueError('duplicate seed coordinates or non-finite statistics')
    if not np.all(bundle.statistics[:, 0] == 1):
        raise ValueError('supplement expects one-pixel extrema seeds')


def subset_bundle(bundle: SeedBundle, indices: np.ndarray) -> SeedBundle:
    """Reindex labels and coordinates together; preserve source intensity state."""
    validate_bundle(bundle)
    indices = np.asarray(indices, dtype=np.int64)
    if indices.ndim != 1 or indices.size == 0 or np.unique(indices).size != indices.size:
        raise ValueError('subset must contain unique, nonempty indices')
    if np.any(indices < 0) or np.any(indices >= bundle.count):
        raise ValueError('subset index outside bundle')
    signs = np.sign(bundle.labels[bundle.y[indices], bundle.x[indices]])
    indices = np.concatenate((np.sort(indices[signs > 0]), np.sort(indices[signs < 0])))
    signs = np.sign(bundle.labels[bundle.y[indices], bundle.x[indices]]).astype(np.int32)
    y, x = bundle.y[indices].copy(), bundle.x[indices].copy()
    labels = np.zeros_like(bundle.labels)
    labels[y, x] = signs * np.arange(1, len(indices) + 1, dtype=np.int32)
    result = SeedBundle(labels, y, x, bundle.statistics[indices].copy(), len(indices))
    validate_bundle(result)
    return result


def matched_bundles(clean: SeedBundle, corrupted: SeedBundle, random_seed: int):
    """Match maxima and minima counts independently; draw without replacement."""
    validate_bundle(clean)
    validate_bundle(corrupted)
    if clean.labels.shape != corrupted.labels.shape:
        raise ValueError('seed image shapes differ')
    rng = np.random.default_rng(random_seed)
    chosen = [[], []]
    counts = {}
    for sign, name in ((1, 'maxima'), (-1, 'minima')):
        indices = [np.flatnonzero(np.sign(b.labels[b.y, b.x]) == sign) for b in (clean, corrupted)]
        k = min(len(indices[0]), len(indices[1]))
        counts[name] = k
        for side in (0, 1):
            chosen[side].extend(np.sort(rng.choice(indices[side], size=k, replace=False)).tolist())
    if sum(counts.values()) == 0:
        raise ValueError('no common nonempty seed cardinality')
    bundles = tuple(subset_bundle(b, np.asarray(ix)) for b, ix in zip((clean, corrupted), chosen))
    assert bundles[0].count == bundles[1].count == sum(counts.values())
    return bundles[0], bundles[1], {'selected_clean_indices': chosen[0], 'selected_recomputed_indices': chosen[1], 'matched_type_counts': counts}


def bundle_hash(bundle: SeedBundle) -> str:
    validate_bundle(bundle)
    h = hashlib.sha256()
    for arr in (bundle.labels, bundle.y, bundle.x, bundle.statistics):
        h.update(str(arr.dtype).encode())
        h.update(str(arr.shape).encode())
        h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()


def seed_diagnostics(clean: SeedBundle, corrupted: SeedBundle, corrupted_image: np.ndarray):
    validate_bundle(clean)
    validate_bundle(corrupted)
    if clean.labels.shape != corrupted.labels.shape or clean.labels.shape != corrupted_image.shape:
        raise ValueError('diagnostic image shapes differ')
    a = clean.labels != 0
    b = corrupted.labels != 0
    intersection, union = np.count_nonzero(a & b), np.count_nonzero(a | b)
    coords_a = np.column_stack((clean.y, clean.x))
    coords_b = np.column_stack((corrupted.y, corrupted.x))
    ab = cKDTree(coords_b).query(coords_a)[0]
    ba = cKDTree(coords_a).query(coords_b)[0]
    same_type = np.sign(clean.labels[clean.y, clean.x]) == np.sign(corrupted.labels[clean.y, clean.x])
    h, w = clean.labels.shape
    def spatial(bundle):
        cells = np.minimum(bundle.y * 4 // h, 3) * 4 + np.minimum(bundle.x * 4 // w, 3)
        mask = bundle.labels != 0
        return {'count': bundle.count, 'maxima': int(np.count_nonzero(bundle.labels[bundle.y, bundle.x] > 0)),
                'minima': int(np.count_nonzero(bundle.labels[bundle.y, bundle.x] < 0)),
                'occupied_4x4_fraction': float(np.unique(cells).size / 16),
                'within_3px_fraction': float(np.mean(distance_transform_edt(~mask) <= 3))}
    return {'clean': spatial(clean), 'recomputed': spatial(corrupted),
            'coordinate_jaccard': float(intersection / union),
            'clean_coordinate_retention': float(intersection / clean.count),
            'clean_same_type_retention': float(np.mean(same_type)),
            'symmetric_nearest_distance_px': float((ab.mean() + ba.mean()) / 2),
            'clean_seed_intensity_change_abs_mean': float(np.mean(np.abs(clean.statistics[:, 1] - corrupted_image[clean.y, clean.x]))),
            'nearest_distance_definition': 'mean of directed nearest-neighbor means; no point identity correspondence'}


def classify_seed_bundle(bundle: SeedBundle) -> str:
    """Distinguish a well-formed empty detector state from malformed input."""
    if bundle.count < 0:
        raise ValueError('negative seed count')
    if bundle.count == 0:
        if (bundle.labels.ndim != 2 or bundle.labels.size == 0 or
            bundle.y.shape != (0,) or bundle.x.shape != (0,) or
            bundle.statistics.shape != (0, 2) or np.count_nonzero(bundle.labels)):
            raise ValueError('malformed empty seed bundle')
        return 'empty'
    validate_bundle(bundle)
    return 'ready'


def sensitivity_seed_status(clean: SeedBundle, candidate: SeedBundle) -> str:
    clean_state = classify_seed_bundle(clean)
    candidate_state = classify_seed_bundle(candidate)
    if clean.labels.shape != candidate.labels.shape:
        raise ValueError('clean and candidate seed grid shapes differ')
    if clean_state == 'empty':
        return 'no_clean_reference'
    return 'no_seeds' if candidate_state == 'empty' else 'ok'
