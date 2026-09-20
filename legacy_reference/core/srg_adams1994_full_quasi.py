import numpy as np
from skimage.color import rgb2gray


def srg_adams1994_full_quasi(Ms, SYe, SXe, SG, EN, img):
    """
    Python 版 SRG_Adams1994_full_quasi (+LE)

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

    # 拷贝，避免修改外部变量
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

    # 初始 seeds_current：SYe/SXe 前 EN 个（0 基坐标）
    SYe = np.asarray(SYe, dtype=int)
    SXe = np.asarray(SXe, dtype=int)
    seeds_current = [(int(SYe[k]), int(SXe[k])) for k in range(EN)]

    # Adams1994 + LE：一个阶段的迭代
    while len(seeds_current) > 0:
        EN2 = 0
        LOCAL_THRESHOLD = 2**B - 1
        DeltaE = 0.0
        DeltaN = 0
        DelNMAX = 0   # 保留变量以贴合原代码
        DelNMIN = 0

        seeds_next = []

        # 当前 LOCAL_THRESHOLD_MIN 下的区域生长：
        # queue 模拟 MATLAB 中 “k<=EN 且 EN 动态增加”
        queue = list(seeds_current)
        q_idx = 0

        while q_idx < len(queue):
            y, x = queue[q_idx]
            q_idx += 1

            label = int(Ms[y, x])
            if label == 0:
                continue
            index = abs(label)     # 区域编号（1..N）→ SA[index-1, :]

            id1 = 0               # 邻居候选数
            id2 = 0               # 真正吸收的邻居数

            for j in (-1, 0, 1):
                for i in (-1, 0, 1):
                    if j == 0 and i == 0:
                        continue
                    y1 = y + j
                    x1 = x + i
                    if 0 <= y1 < H and 0 <= x1 < W and Ms[y1, x1] == 0:
                        id1 += 1
                        avg = SA[index - 1, 1]

                        # 主条件：|I(y1,x1) - avg| <= LOCAL_THRESHOLD_MIN
                        if abs(img_gray[y1, x1] - avg) <= LOCAL_THRESHOLD_MIN:
                            Ms[y1, x1] = label
                            # 新像素加入本轮 queue，在当前阈值下继续扩展
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
                            # Adams1994 + LE：局部阈值 = |I(y1,x1) - avg|
                            sigs = abs(img_gray[y1, x1] - avg)
                            if sigs < LOCAL_THRESHOLD:
                                LOCAL_THRESHOLD = sigs

            # 若还有未吸收的邻居候选，则下轮继续保留这个种子
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
