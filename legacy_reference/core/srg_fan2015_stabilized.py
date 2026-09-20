import numpy as np
from skimage.color import rgb2gray


def srg_fan2015_stabilized(Ms, SYe, SXe, SG, EN, img, L):
    """
    Python 版 SRG_Fan2015_Stabilized

    Parameters
    ----------
    Ms : (H, W) ndarray, int
        初始种子标记图，标签为 ±1, ±2, ..., 其余为 0。
    SYe, SXe : 1D ndarray 或 list
        种子坐标，长度至少 EN，0 基索引：0 <= y < H, 0 <= x < W。
        只使用前 EN 个。
    SG : (EN, 2) ndarray
        极值平台 / 区域统计：
          SG[k, 0] = 区域 k+1 的初始像素数
          SG[k, 1] = 区域 k+1 的初始灰度（极值灰度）
    EN : int
        初始种子数量。
    img : ndarray
        输入图像，灰度或 RGB。
    L : int/float
        Fan 2015 稳定化的窗口半径（L 像素）。

    Returns
    -------
    Ms_out : (H, W) ndarray, int
        完整分割标签图。
    loop : int
        外层阈值迭代次数。
    SA : (EN, 2) ndarray
        区域最终统计 [像素数, 平均灰度]。
        注意：长度仍为初始 EN，某些区域可能未被使用。
    LOCAL_THRESHOLD_MIN : float
        最终局部阈值。
    SPEED : (K,) ndarray
        每次迭代 DeltaE/DeltaN 的记录。
    """

    # 拷贝，避免原数组在外面被改
    Ms = np.array(Ms, copy=True)
    img = np.asarray(img)

    # 转灰度 + round(double)
    if img.ndim == 3:
        img_gray = rgb2gray(img)
    else:
        img_gray = img.astype(np.float64)
    img_gray = np.round(img_gray.astype(np.float64))

    H, W = img_gray.shape

    # L 为窗口半径
    L = int(round(float(L)))

    # SA 初始化为 SG（[像素数, 平均灰度]）
    SA = np.array(SG, copy=True, dtype=np.float64)

    B = 8
    GLOBAL_THRESHOLD = 2**B - 1   # 255
    LOCAL_THRESHOLD_MIN = 0.0

    SPEED_list = []
    loop = 1

    # 初始外层种子集合（当前阈值下的“活跃边界点”）
    SYe = np.asarray(SYe, dtype=int)
    SXe = np.asarray(SXe, dtype=int)
    seeds_current = [(int(SYe[k]), int(SXe[k])) for k in range(EN)]

    # Fan 2015 只有一个阶段（基于 Adams 的 SRG，加稳定化窗口）
    while len(seeds_current) > 0:
        EN2 = 0
        LOCAL_THRESHOLD = 2**B - 1
        DeltaE = 0.0
        DeltaN = 0
        DelNMAX = 0  # 保留变量（与 MATLAB 同名），虽然后面不用
        DelNMIN = 0

        seeds_next = []

        # 在当前 LOCAL_THRESHOLD_MIN 下，做一次完整的区域生长
        # 使用队列 queue 实现“k<=EN 时 EN 动态增长”的效果
        queue = list(seeds_current)
        q_idx = 0

        while q_idx < len(queue):
            y, x = queue[q_idx]
            q_idx += 1

            label = int(Ms[y, x])
            if label == 0:
                continue
            index = abs(label)  # 对应 SA 行号 index-1

            id1 = 0  # 考察邻居数
            id2 = 0  # 真正吸收成功的邻居数

            for j in (-1, 0, 1):
                for i in (-1, 0, 1):
                    if j == 0 and i == 0:
                        continue
                    y1 = y + j
                    x1 = x + i
                    if 0 <= y1 < H and 0 <= x1 < W and Ms[y1, x1] == 0:
                        id1 += 1
                        avg = SA[index - 1, 1]

                        # 主条件：|avg - I(y1,x1)| <= LOCAL_THRESHOLD_MIN
                        if abs(avg - img_gray[y1, x1]) <= LOCAL_THRESHOLD_MIN:
                            Ms[y1, x1] = label
                            # 新像素也成为本轮的边界点（同一阈值下继续扩展）
                            queue.append((y1, x1))

                            count = SA[index - 1, 0]
                            SA[index - 1, 1] = (
                                avg * count + img_gray[y1, x1]
                            ) / (count + 1)
                            SA[index - 1, 0] = count + 1

                            id2 += 1
                            DeltaE += img_gray[y1, x1]
                            DeltaN += 1
                            DelNMAX += int(np.sign(np.sign(label) + 1))
                            DelNMIN += int(np.sign(1 - np.sign(label)))
                        else:
                            # Fan2015 稳定化：用 L×L 窗内的平均偏差估一个局部阈值
                            sigs_sum = 0.0
                            cnt = 0

                            for u in range(-L, L + 1):
                                for v in range(-L, L + 1):
                                    yy = y1 + u
                                    xx = x1 + v
                                    if (
                                        0 <= yy < H
                                        and 0 <= xx < W
                                        and Ms[yy, xx] == 0
                                    ):
                                        cnt += 1
                                        sigs_sum += abs(
                                            img_gray[yy, xx] - avg
                                        )

                            if cnt > 0:
                                sigs = sigs_sum / cnt
                                if sigs < LOCAL_THRESHOLD:
                                    LOCAL_THRESHOLD = sigs

            # 如果这个种子有邻居候选（id1）但实际只吸收了部分（id2），
            # 说明还存在未满足当前阈值的潜在邻居，下轮继续保留为种子
            if id1 > id2:
                seeds_next.append((y, x))
                EN2 += 1

        # 终止条件
        if EN2 == 0 or LOCAL_THRESHOLD_MIN >= GLOBAL_THRESHOLD:
            break
        else:
            # 下一轮的初始种子
            seeds_current = seeds_next

            if DeltaN != 0:
                SPEED_list.append(DeltaE / DeltaN)

            # 更新 LOCAL_THRESHOLD_MIN
            if LOCAL_THRESHOLD_MIN >= LOCAL_THRESHOLD:
                LOCAL_THRESHOLD_MIN = LOCAL_THRESHOLD_MIN + 0.3
            else:
                LOCAL_THRESHOLD_MIN = LOCAL_THRESHOLD + 0.1

            loop += 1

    SPEED = np.asarray(SPEED_list, dtype=float)
    return Ms, loop, SA, LOCAL_THRESHOLD_MIN, SPEED
