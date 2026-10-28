import numpy as np
from skimage.color import rgb2gray

# 8-neighborhood offsets for boundary detection / smoothing
_NEIGHBORS_8 = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]


def _smooth_labels_majority(Ms: np.ndarray,
                            iters: int = 1,
                            majority_ratio: float = 0.6) -> np.ndarray:
    """
    Boundary-only 3x3 majority smoothing:
    - Only boundary pixels (having any neighbor with different label) are reconsidered.
    - If a label occupies >= majority_ratio of the 3x3 window (excluding 0), relabel center.
    Helps remove tiny spikes and smooth jagged edges (improves ESR-like metrics).
    """
    Ms = np.asarray(Ms).copy()
    H, W = Ms.shape
    majority_ratio = float(majority_ratio)

    for _ in range(max(int(iters), 0)):
        boundary = np.zeros_like(Ms, dtype=bool)
        for dy, dx in _NEIGHBORS_8:
            y0 = max(0, -dy)
            y1 = min(H, H - dy)
            x0 = max(0, -dx)
            x1 = min(W, W - dx)
            sub = Ms[y0:y1, x0:x1]
            sub_n = Ms[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
            boundary[y0:y1, x0:x1] |= (sub != sub_n)

        Ms_new = Ms.copy()
        ys, xs = np.nonzero(boundary)
        for y, x in zip(ys, xs):
            yy0 = max(0, y - 1)
            yy1 = min(H, y + 2)
            xx0 = max(0, x - 1)
            xx1 = min(W, x + 2)
            window = Ms[yy0:yy1, xx0:xx1]
            vals = window.ravel()
            vals = vals[vals != 0]  # ignore label 0

            if vals.size == 0:
                continue

            labels, counts = np.unique(vals, return_counts=True)
            j = np.argmax(counts)
            maj_label = labels[j]
            if maj_label != Ms[y, x] and counts[j] >= majority_ratio * vals.size:
                Ms_new[y, x] = maj_label

        Ms = Ms_new

    return Ms


def _validate_params(eps: float,
                     smooth_iters: int,
                     majority_ratio: float,
                     max_iter_stage1: int,
                     max_iter_stage2: int) -> None:
    if eps < 0:
        raise ValueError("eps must be non-negative")
    if smooth_iters < 0:
        raise ValueError("smooth_iters must be >= 0")
    if not (0.0 <= majority_ratio <= 1.0):
        raise ValueError("majority_ratio must be in [0,1]")
    if max_iter_stage1 <= 0 or max_iter_stage2 <= 0:
        raise ValueError("max_iter_stage1/2 must be positive integers")


def _stage1_clerg_eps(
    Ms,
    SYe,
    SXe,
    SA,
    SG,
    EN,
    img_gray,
    eps,
    GLOBAL_THRESHOLD,
    max_iter_stage1,
    CHECK,
):
    """Stage1: ε-CLERG monotone growing (with eps tolerance)."""
    H, W = img_gray.shape
    LOCAL_THRESHOLD_MIN = 0.0
    SPEED = []
    loop = 1
    k = 1
    EN2 = 1

    while EN2 > 0 and loop <= max_iter_stage1:
        EN2 = 0
        LOCAL_THRESHOLD = GLOBAL_THRESHOLD
        DeltaE = 0.0
        DeltaN = 0.0

        while k <= EN:
            y = int(SYe[k - 1])
            x = int(SXe[k - 1])

            if not (0 <= y < H and 0 <= x < W):
                k += 1
                continue

            label = int(Ms[y, x])
            if label == 0:
                k += 1
                continue

            index = abs(label)           # 1..N
            EXT = SG[index - 1, 1]
            sgn = 1 if label > 0 else -1

            id1 = 0
            id2 = 0

            for j in (-1, 0, 1):
                for i in (-1, 0, 1):
                    if j == 0 and i == 0:
                        continue
                    y1 = y + j
                    x1 = x + i
                    if 0 <= y1 < H and 0 <= x1 < W and Ms[y1, x1] == 0:
                        id1 += 1
                        avg = SA[index - 1, 1]

                        target = EXT - LOCAL_THRESHOLD_MIN * sgn
                        if abs(img_gray[y1, x1] - target) <= eps:
                            Ms[y1, x1] = label

                            EN += 1
                            if EN > len(SYe):
                                SYe.append(int(y1))
                                SXe.append(int(x1))
                            else:
                                SYe[EN - 1] = int(y1)
                                SXe[EN - 1] = int(x1)

                            idx = SA[index - 1, 0]
                            SA[index - 1, 1] = (avg * idx + img_gray[y1, x1]) / (idx + 1)
                            SA[index - 1, 0] = idx + 1

                            DeltaE += img_gray[y1, x1]
                            DeltaN += 1
                            id2 += 1
                        else:
                            diff = abs(EXT - img_gray[y1, x1])
                            if diff > LOCAL_THRESHOLD_MIN and diff < LOCAL_THRESHOLD:
                                LOCAL_THRESHOLD = diff

            if id1 > id2:
                EN2 += 1
                if EN2 > len(SYe):
                    SYe.append(int(y))
                    SXe.append(int(x))
                else:
                    SYe[EN2 - 1] = int(y)
                    SXe[EN2 - 1] = int(x)

            k += 1

        if (
            EN2 == 0
            or LOCAL_THRESHOLD_MIN >= GLOBAL_THRESHOLD
            or LOCAL_THRESHOLD == GLOBAL_THRESHOLD
            or (loop > 20 and CHECK[loop - 1] == CHECK[loop - 19])
        ):
            break
        else:
            k = 1
            EN = EN2
            if DeltaN != 0:
                SPEED.append(DeltaE / DeltaN)
            LOCAL_THRESHOLD_MIN = LOCAL_THRESHOLD
            loop += 1
            if loop - 1 < CHECK.size:
                CHECK[loop - 1] = EN2

    return Ms, SYe, SXe, SA, EN2, LOCAL_THRESHOLD_MIN, SPEED, loop


def _stage2_adams_tail(
    Ms,
    SYe,
    SXe,
    SA,
    EN2,
    img_gray,
    GLOBAL_THRESHOLD,
    max_iter_stage2,
    initial_loop,
):
    """Stage2: Adams1994-style full-coverage tail phase."""
    H, W = img_gray.shape

    EN = EN2
    LOCAL_THRESHOLD_MIN = 0.0
    k = 1
    EN2 = 1
    SPEED = []
    loop = initial_loop
    iterations = 0

    while EN2 > 0 and iterations < max_iter_stage2:
        EN2 = 0
        LOCAL_THRESHOLD = GLOBAL_THRESHOLD
        DeltaE = 0.0
        DeltaN = 0.0

        while k <= EN:
            y = int(SYe[k - 1])
            x = int(SXe[k - 1])

            if not (0 <= y < H and 0 <= x < W):
                k += 1
                continue

            label = int(Ms[y, x])
            if label == 0:
                k += 1
                continue

            index = abs(label)
            id1 = 0
            id2 = 0

            for j in (-1, 0, 1):
                for i in (-1, 0, 1):
                    if j == 0 and i == 0:
                        continue
                    y1 = y + j
                    x1 = x + i
                    if 0 <= y1 < H and 0 <= x1 < W and Ms[y1, x1] == 0:
                        id1 += 1
                        avg = SA[index - 1, 1]

                        if abs(img_gray[y1, x1] - avg) <= LOCAL_THRESHOLD_MIN:
                            Ms[y1, x1] = label

                            EN += 1
                            if EN > len(SYe):
                                SYe.append(int(y1))
                                SXe.append(int(x1))
                            else:
                                SYe[EN - 1] = int(y1)
                                SXe[EN - 1] = int(x1)

                            idx = SA[index - 1, 0]
                            SA[index - 1, 1] = (avg * idx + img_gray[y1, x1]) / (idx + 1)
                            SA[index - 1, 0] = idx + 1

                            id2 += 1
                            DeltaE += img_gray[y1, x1]
                            DeltaN += 1
                        else:
                            sigs = abs(img_gray[y1, x1] - avg)
                            if sigs < LOCAL_THRESHOLD:
                                LOCAL_THRESHOLD = sigs

            if id1 > id2:
                EN2 += 1
                if EN2 > len(SYe):
                    SYe.append(int(y))
                    SXe.append(int(x))
                else:
                    SYe[EN2 - 1] = int(y)
                    SXe[EN2 - 1] = int(x)

            k += 1

        if EN2 == 0 or LOCAL_THRESHOLD_MIN >= GLOBAL_THRESHOLD:
            break
        else:
            k = 1
            EN = EN2
            if DeltaN != 0:
                SPEED.append(DeltaE / DeltaN)

            if LOCAL_THRESHOLD_MIN >= LOCAL_THRESHOLD:
                LOCAL_THRESHOLD_MIN = LOCAL_THRESHOLD_MIN + 0.3
            else:
                LOCAL_THRESHOLD_MIN = LOCAL_THRESHOLD + 0.1

            loop += 1
            iterations += 1

    return Ms, SYe, SXe, SA, EN2, LOCAL_THRESHOLD_MIN, SPEED, loop


def srg_nguyen2020_clerg_full(
    Ms,
    SYe,
    SXe,
    SG,
    EN,
    img,
    eps: float = 1.0,
    smooth_iters: int = 2,
    majority_ratio: float = 0.6,
    max_iter_stage1: int = 50,
    max_iter_stage2: int = 50,
    return_coverage: bool = False,
):
    """
    Python port of SRG_Nguyen2020_CLERG_full with two practical tweaks:
    1) ε tolerance in CLERG growing: |I - (EXT - thr * sgn)| <= eps (default 1.0 gray level).
    2) Optional 3x3 boundary majority smoothing for jagged edges.

    Added:
    - max_iter_stage1/2: iteration guards for robustness.
    - return_coverage: if True, also returns coverage ratio.
    """
    _validate_params(eps, smooth_iters, majority_ratio, max_iter_stage1, max_iter_stage2)

    eps = float(eps)

    # --- Image preprocessing: grayscale + round(double) ---
    Ms = np.array(Ms, copy=True)
    img = np.asarray(img)

    if img.ndim == 3:
        img_gray = rgb2gray(img)
    else:
        img_gray = img.astype(np.float64)

    img_gray = np.round(img_gray.astype(np.float64))

    # SA = SG copy
    SG = np.asarray(SG, dtype=np.float64)
    SA = np.array(SG, copy=True, dtype=np.float64)

    B = 8
    GLOBAL_THRESHOLD = 2 ** B - 1  # 255

    CHECK = np.zeros(2 ** B - 1, dtype=np.float64)
    CHECK[0] = EN

    # Seeds as lists for dynamic growth
    SYe = list(np.asarray(SYe, dtype=int))
    SXe = list(np.asarray(SXe, dtype=int))
    if len(SYe) < EN:
        SYe += [0] * (EN - len(SYe))
        SXe += [0] * (EN - len(SXe))

    Ms, SYe, SXe, SA, EN2, thr_stage1, SPEED1, loop1 = _stage1_clerg_eps(
        Ms, SYe, SXe, SA, SG, EN, img_gray, eps, GLOBAL_THRESHOLD, max_iter_stage1, CHECK
    )

    Ms, SYe, SXe, SA, EN3, thr_stage2, SPEED2, loop_final = _stage2_adams_tail(
        Ms,
        SYe,
        SXe,
        SA,
        EN2,
        img_gray,
        GLOBAL_THRESHOLD,
        max_iter_stage2,
        initial_loop=loop1,
    )

    if smooth_iters > 0:
        Ms = _smooth_labels_majority(
            Ms, iters=smooth_iters, majority_ratio=majority_ratio
        )

    SPEED = np.asarray([*SPEED1, *SPEED2], dtype=float)
    LOCAL_THRESHOLD_MIN = thr_stage2

    if return_coverage:
        coverage = float((np.abs(Ms) > 0).mean())
        return Ms, loop_final, SA, LOCAL_THRESHOLD_MIN, SPEED, coverage

    return Ms, loop_final, SA, LOCAL_THRESHOLD_MIN, SPEED
