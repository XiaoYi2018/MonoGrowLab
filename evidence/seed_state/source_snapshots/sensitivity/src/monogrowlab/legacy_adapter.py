"""Narrow adapter around the hash-pinned historical implementations."""

from __future__ import annotations

import importlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.color import rgb2gray
from skimage.measure import label as connected_components
from skimage.morphology import h_maxima, h_minima


@dataclass(frozen=True)
class SeedBundle:
    labels: np.ndarray
    y: np.ndarray
    x: np.ndarray
    statistics: np.ndarray
    count: int


@dataclass(frozen=True)
class AlgorithmResult:
    labels: np.ndarray
    seconds: float
    loops: int
    threshold: float
    coverage: float
    regions: int


class LegacyAdapter:
    def __init__(self, legacy_root: Path):
        self.legacy_root = legacy_root.resolve()
        if not self.legacy_root.is_dir():
            raise FileNotFoundError(self.legacy_root)
        if str(self.legacy_root) not in sys.path:
            sys.path.insert(0, str(self.legacy_root))
        self.extrema = importlib.import_module("extrema_single_symm_scan").extrema_single_symm_scan
        self.clerg = importlib.import_module("clerg_e").srg_nguyen2020_clerg_full
        self.adams = importlib.import_module("srg_adams1994_full_quasi").srg_adams1994_full_quasi
        self.fan2005 = importlib.import_module("srg_fan2005_regular").srg_fan2005_regular
        self.fan2015 = importlib.import_module("srg_fan2015_stabilized").srg_fan2015_stabilized
        self.levelset = importlib.import_module("srg_2004_level_set").srg_2004_level_set

    @staticmethod
    def to_gray_uint8(image: np.ndarray) -> np.ndarray:
        arr = np.asarray(image)
        if arr.ndim == 3:
            arr = rgb2gray(arr[..., :3])
        arr = arr.astype(np.float64)
        minimum = float(arr.min())
        maximum = float(arr.max())
        if maximum > minimum:
            arr = (arr - minimum) / (maximum - minimum)
        else:
            arr = np.zeros_like(arr)
        return np.rint(arr * 255.0).astype(np.uint8)

    @staticmethod
    def _regional_extrema_bundle(image: np.ndarray, height: float) -> SeedBundle:
        if height <= 0:
            raise ValueError("h-extrema height must be positive")
        maxima = connected_components(h_maxima(image, height), connectivity=2)
        minima = connected_components(h_minima(image, height), connectivity=2)
        maximum_count = int(maxima.max())
        minimum_count = int(minima.max())
        count = maximum_count + minimum_count
        labels = np.zeros(image.shape, dtype=np.int32)
        y = np.zeros(count, dtype=np.int32)
        x = np.zeros(count, dtype=np.int32)
        statistics = np.zeros((count, 2), dtype=np.float64)

        for component in range(1, maximum_count + 1):
            coordinates = np.argwhere(maxima == component)
            values = image[coordinates[:, 0], coordinates[:, 1]]
            location = coordinates[int(np.argmax(values))]
            index = component - 1
            y[index], x[index] = int(location[0]), int(location[1])
            labels[y[index], x[index]] = component
            statistics[index] = (1.0, float(image[y[index], x[index]]))

        for component in range(1, minimum_count + 1):
            coordinates = np.argwhere(minima == component)
            values = image[coordinates[:, 0], coordinates[:, 1]]
            location = coordinates[int(np.argmin(values))]
            global_label = maximum_count + component
            index = global_label - 1
            y[index], x[index] = int(location[0]), int(location[1])
            labels[y[index], x[index]] = -global_label
            statistics[index] = (1.0, float(image[y[index], x[index]]))

        return SeedBundle(labels, y, x, statistics, count)

    def extract_seeds(
        self,
        image: np.ndarray,
        strategy: dict[str, object] | None = None,
    ) -> SeedBundle:
        strategy = strategy or {"name": "strict"}
        name = str(strategy.get("name", "strict"))
        if name == "h_extrema":
            return self._regional_extrema_bundle(image, float(strategy.get("height", 4.0)))
        if name == "strict":
            detection_image = image
        elif name == "gaussian_strict":
            sigma = float(strategy.get("sigma", 1.0))
            if sigma <= 0:
                raise ValueError("gaussian seed sigma must be positive")
            detection_image = np.clip(
                np.rint(gaussian_filter(image.astype(np.float64), sigma=sigma)), 0, 255
            ).astype(np.uint8)
        else:
            raise ValueError(f"unknown seed strategy: {name}")

        labels, count, y, x, _, statistics, _ = self.extrema(detection_image)
        statistics = np.asarray(statistics, dtype=np.float64)
        y = np.asarray(y, dtype=np.int32)
        x = np.asarray(x, dtype=np.int32)
        if count:
            statistics[:, 0] = 1.0
            statistics[:, 1] = image[y, x]
        return SeedBundle(
            labels=np.asarray(labels, dtype=np.int32),
            y=y,
            x=x,
            statistics=statistics,
            count=int(count),
        )

    def run(
        self,
        algorithm: str,
        seeds: SeedBundle,
        image: np.ndarray,
        *,
        eps: float = 1.0,
        smooth_iters: int = 0,
        fan2015_l: float = 15.0,
    ) -> AlgorithmResult:
        arguments = (
            seeds.labels.copy(),
            seeds.y.copy(),
            seeds.x.copy(),
            seeds.statistics.copy(),
            seeds.count,
            image,
        )
        start = time.perf_counter()
        if algorithm == "clerg":
            labels, loops, _, threshold, _ = self.clerg(
                *arguments,
                eps=float(eps),
                smooth_iters=int(smooth_iters),
                max_iter_stage1=50,
                max_iter_stage2=50,
            )
        elif algorithm == "adams1994":
            labels, loops, _, threshold, _ = self.adams(*arguments)
        elif algorithm == "fan2005":
            labels, loops, _, threshold, _ = self.fan2005(*arguments)
        elif algorithm == "fan2015":
            labels, loops, _, threshold, _ = self.fan2015(*arguments, float(fan2015_l))
        elif algorithm == "levelset2004":
            labels, loops, _, threshold, _ = self.levelset(*arguments, method="non-Eulerian")
        else:
            raise ValueError(f"unknown legacy algorithm: {algorithm}")
        seconds = time.perf_counter() - start
        labels = np.abs(np.asarray(labels, dtype=np.int64))
        nonzero = labels[labels != 0]
        return AlgorithmResult(
            labels=labels,
            seconds=seconds,
            loops=int(loops),
            threshold=float(threshold),
            coverage=float(np.count_nonzero(labels) / labels.size),
            regions=int(np.unique(nonzero).size) if nonzero.size else 0,
        )
