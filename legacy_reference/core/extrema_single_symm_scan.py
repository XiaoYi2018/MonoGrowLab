# 文件名：extrema_single_symm_scan.py
import numpy as np

def extrema_single_symm_scan(img):
    """
    8 邻域 single-extrema 提取（近似 Nguyen & Tsviatkou 对称扫描线算法的功能，
    但实现用 NumPy 做了简化：严格局部极大值 / 极小值）。

    Parameters
    ----------
    img : np.ndarray
        2D 灰度图 (H, W) 或 3D RGB 图 (H, W, 3)，dtype 任意，可为 uint8.

    Returns
    -------
    SM  : (H, W) int32
        标签图：局部极大平台为 1..Kmax，局部极小为 -(Kmax+1 .. Kmax+Kmin)，其余为 0
    EN  : int
        极值点总数（极大 + 极小）
    SYe : (EN,) int32
        每个极值点的行坐标（0-based，下同）
    SXe : (EN,) int32
        每个极值点的列坐标
    SE  : (EN, 2) float64
        每个极值的 [像素数(=1), 灰度值]
    SG  : (EN, 2) float64
        与 SE 相同，用来和 SRG 代码接口对齐
    OPP : float
        占位用，不参与后续计算
    """
    # 1) 转灰度，统一为 float64
    if img.ndim == 3:
        # 简单加权灰度
        img_gray = (
            0.2989 * img[..., 0] +
            0.5870 * img[..., 1] +
            0.1140 * img[..., 2]
        ).astype(np.float64)
    else:
        img_gray = img.astype(np.float64)

    H, W = img_gray.shape
    # 边界像素不作为极值点，先截取内部
    center = img_gray[1:-1, 1:-1]

    nbs = [
        img_gray[:-2, :-2], img_gray[:-2, 1:-1], img_gray[:-2, 2:],   # 上三邻
        img_gray[1:-1, :-2],                     img_gray[1:-1, 2:],   # 左右
        img_gray[2:, :-2],  img_gray[2:, 1:-1],  img_gray[2:, 2:]      # 下三邻
    ]

    # 2) 严格局部极大 / 极小（> 所有邻居 或 < 所有邻居）
    is_max = np.ones_like(center, dtype=bool)
    is_min = np.ones_like(center, dtype=bool)
    for nb in nbs:
        is_max &= center > nb
        is_min &= center < nb

    SM = np.zeros((H, W), dtype=np.int32)

    max_coords = np.argwhere(is_max)       # (kmax, 2)，坐标是相对 center 的
    min_coords = np.argwhere(is_min)       # (kmin, 2)

    Kmax = max_coords.shape[0]
    Kmin = min_coords.shape[0]
    EN = Kmax + Kmin

    SYe = np.zeros(EN, dtype=np.int32)
    SXe = np.zeros(EN, dtype=np.int32)
    SE  = np.zeros((EN, 2), dtype=np.float64)
    SG  = np.zeros((EN, 2), dtype=np.float64)

    # 3) 写入极大点：标签 1..Kmax
    for idx, (yy, xx) in enumerate(max_coords):
        y = int(yy + 1)   # 补回边界偏移
        x = int(xx + 1)
        label = idx + 1
        SM[y, x] = label

        SYe[idx] = y
        SXe[idx] = x
        val = float(img_gray[y, x])
        SE[idx, 0] = 1.0
        SE[idx, 1] = val
        SG[idx, 0] = 1.0
        SG[idx, 1] = val

    # 4) 写入极小点：标签 -(Kmax+1 .. Kmax+Kmin)
    for j, (yy, xx) in enumerate(min_coords):
        y = int(yy + 1)
        x = int(xx + 1)
        gidx = Kmax + j          # 0-based 全局索引
        label = -(gidx + 1)      # 变成负号标签
        SM[y, x] = label

        SYe[gidx] = y
        SXe[gidx] = x
        val = float(img_gray[y, x])
        SE[gidx, 0] = 1.0
        SE[gidx, 1] = val
        SG[gidx, 0] = 1.0
        SG[gidx, 1] = val

    OPP = 0.0  # 这里只是占位，不用

    return SM, EN, SYe, SXe, SE, SG, OPP
