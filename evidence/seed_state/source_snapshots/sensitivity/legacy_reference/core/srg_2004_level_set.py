import numpy as np
from skimage.color import rgb2gray


def srg_2004_level_set(Ms, SYe, SXe, SG, EN, img, method="non-Eulerian"):
    """
    Python 版 SRG_2004_Level_Set (+LE)

    对应 MATLAB: SRG_2004_Level_Set.m

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
    method : {'non-Eulerian', 'Eulerian'}
        对应 MATLAB 的 method：
          - 'non-Eulerian' : tag = 1，全覆盖（多次阈值迭代）
          - 'Eulerian'     : tag = 0，只做一轮阈值增长后停止

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

    # 拷贝，避免外部变量被修改
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
    GLOBAL_THRESHOLD = 2**B - 1       # 255
    LOCAL_THRESHOLD_MIN = 0.0

    SPEED_list = []
    loop = 1

    # 解析 method -> tag
    if method == "Eulerian":
        tag = 0   # stopping criterion fulfilled → 只做有限步
    elif method == "non-Eulerian":
        tag = 1   # all points covered → 尽量全覆盖
    else:
        raise ValueError("method must be 'Eulerian' or 'non-Eulerian'")

    # 初始 seeds_current：SYe/SXe 前 EN 个
    SYe = np.asarray(SYe, dtype=int)
    SXe = np.asarray(SXe, dtype=int)
    seeds_current = [(int(SYe[k]), int(SXe[k])) for k in range(EN)]

    # Wave propagation
    while len(seeds_current) > 0:
        EN2 = 0
        LOCAL_THRESHOLD = 2**B - 1
        DeltaE = 0.0
        DeltaN = 0
        DelNMAX = 0  # 保留变量名以贴合原代码
        DelNMIN = 0

        seeds_next = []

        # 当前 LOCAL_THRESHOLD_MIN 下，一轮完整的波前推进
        # queue 模拟 MATLAB 中 while k<=EN & EN 动态增长
        queue = list(seeds_current)
        q_idx = 0

        while q_idx < len(queue):
            y, x = queue[q_idx]
            q_idx += 1

            label = int(Ms[y, x])
            if label == 0:
                continue
            index = abs(label)  # 对应 SA 行 index-1

            id1 = 0    # 邻居候选数
            id2 = 0    # 真正吸收的邻居数

            j = -1
            while j < 2:
                i = -1
                while i < 2:
                    if not (j == 0 and i == 0):
                        y1 = y + j
                        x1 = x + i
                        if 0 <= y1 < H and 0 <= x1 < W and Ms[y1, x1] == 0:
                            id1 += 1
                            avg = SA[index - 1, 1]

                            # 主条件：|avg - I(y1,x1)| <= LOCAL_THRESHOLD_MIN
                            if abs(avg - img_gray[y1, x1]) <= LOCAL_THRESHOLD_MIN:
                                Ms[y1, x1] = label
                                # 新像素继续作为本轮“前沿点”
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
                                sigs = abs(img_gray[y1, x1] - avg)
                                if sigs < LOCAL_THRESHOLD:
                                    LOCAL_THRESHOLD = sigs
                    i += 1
                j += 1

            # 若还存在未吸收的候选邻居，则下一轮继续保留
            if id1 > id2:
                seeds_next.append((y, x))
                EN2 += 1

        # 终止条件
        if EN2 == 0 or LOCAL_THRESHOLD_MIN > GLOBAL_THRESHOLD:
            break
        else:
            seeds_current = seeds_next

            if DeltaN != 0:
                SPEED_list.append(DeltaE / DeltaN)

            # Porikli 2004 的阈值更新规则
            if LOCAL_THRESHOLD_MIN == 0:
                # Delta_q = 3 * 2^B / 64; (B=8 → 12)
                LOCAL_THRESHOLD_MIN = 3 * (2**B) / 64.0
            else:
                if tag == 1:  # non-Eulerian: 继续提高阈值
                    if LOCAL_THRESHOLD_MIN >= LOCAL_THRESHOLD:
                        LOCAL_THRESHOLD_MIN = LOCAL_THRESHOLD_MIN + 0.1
                    else:
                        LOCAL_THRESHOLD_MIN = LOCAL_THRESHOLD + 0.05
                else:         # Eulerian: 做一轮后直接停止
                    break

            loop += 1

    SPEED = np.asarray(SPEED_list, dtype=float)
    return Ms, loop, SA, LOCAL_THRESHOLD_MIN, SPEED
