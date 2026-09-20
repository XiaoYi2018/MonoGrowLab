import numpy as np
from skimage.color import rgb2gray


def srg_fan2005_regular(Ms, SYe, SXe, SG, EN, img):
    """
    Python 版 SRG_Fan2005_regular

    Parameters
    ----------
    Ms : (H, W) ndarray, int
        初始种子标记图，标签为 ±1, ±2, ...，其余为 0。
    SYe, SXe : 1D ndarray 或 list
        种子坐标（0 基），长度至少 EN，只使用前 EN 个。
    SG : (EN, 2) ndarray
        区域统计初始化：
          SG[k, 0] = 区域 k+1 初始像素数（plateau 大小）
          SG[k, 1] = 区域 k+1 初始灰度（极值灰度）
    EN : int
        初始种子数量。
    img : ndarray
        输入图像，灰度或 RGB。

    Returns
    -------
    Ms_out : (H, W) ndarray, int
        完整分割标签图。
    loop : int
        外层阈值迭代次数。
    SA : (EN, 2) ndarray
        最终每个区域的 [像素数, 平均灰度]。
    LOCAL_THRESHOLD_MIN : float
        最终局部阈值。
    SPEED : (K,) ndarray
        每轮 DeltaE/DeltaN 的记录。
    """

    # 拷贝，避免修改外部数据
    Ms = np.array(Ms, copy=True)
    img = np.asarray(img)

    # 转灰度 + round(double)
    if img.ndim == 3:
        img_gray = rgb2gray(img)
    else:
        img_gray = img.astype(np.float64)
    img_gray = np.round(img_gray.astype(np.float64))

    H, W = img_gray.shape

    # SA = SG
    SA = np.array(SG, copy=True, dtype=np.float64)

    B = 8
    GLOBAL_THRESHOLD = 2**B - 1      # 255
    LOCAL_THRESHOLD_MIN = 0.0

    SPEED_list = []
    loop = 1

    # 初始 seeds_current：SYe/SXe 前 EN 个
    SYe = np.asarray(SYe, dtype=int)
    SXe = np.asarray(SXe, dtype=int)
    seeds_current = [(int(SYe[k]), int(SXe[k])) for k in range(EN)]

    # Fan2005 regular：只有一阶段，不再有后续 Adams 收尾
    while len(seeds_current) > 0:
        EN2 = 0
        LOCAL_THRESHOLD = 2**B - 1
        DeltaE = 0.0
        DeltaN = 0
        DelNMAX = 0  # 为保持与原代码一致保留此变量
        DelNMIN = 0

        seeds_next = []

        # 当前 LOCAL_THRESHOLD_MIN 下的区域生长：
        # queue 模拟 MATLAB 中 k<=EN & EN 动态增大
        queue = list(seeds_current)
        q_idx = 0

        while q_idx < len(queue):
            y, x = queue[q_idx]
            q_idx += 1

            label = int(Ms[y, x])
            if label == 0:
                continue
            index = abs(label)           # 对应 SA 行 index-1

            id1 = 0      # 邻居候选数
            id2 = 0      # 真正吸收的邻居数

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
                            # 新点在本轮同一阈值下继续作为“边界点”
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
                            # Fan2005 regular 的局部阈值估计：
                            # 注意：与原 MATLAB 一样，这里没有除以 id（邻居数）
                            sigs = 0.0
                            id_loc = 0
                            for u in (-1, 0, 1):
                                for v in (-1, 0, 1):
                                    if u == 0 and v == 0:
                                        continue
                                    yy = y + u
                                    xx = x + v
                                    if (
                                        0 <= yy < H
                                        and 0 <= xx < W
                                        and Ms[yy, xx] == 0
                                    ):
                                        id_loc += 1
                                        sigs += abs(
                                            img_gray[yy, xx] - img_gray[y, x]
                                        )

                            # 与原代码保持完全一致：不除以 id_loc
                            if sigs < LOCAL_THRESHOLD:
                                LOCAL_THRESHOLD = sigs

            # 这一像素作为种子时，若还有“未吸收”的邻居候选，则下一轮保留
            if id1 > id2:
                seeds_next.append((y, x))
                EN2 += 1

        # 终止条件
        if EN2 == 0 or LOCAL_THRESHOLD_MIN >= GLOBAL_THRESHOLD:
            break
        else:
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
