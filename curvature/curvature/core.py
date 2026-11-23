"""曲线曲率与拐点。

对离散点列建立均匀参数（节点参数 u = 0..m，m = len(points)-1）的
夹持（clamped）三次样条，对外暴露归一化参数 t ∈ [0, 1]（u = t * m，
即 t = k/m 恰好落在第 k 个节点上）。

选择夹持边界条件：端点一阶导用三点单边差分（O(h^2)）估计。相较
not-a-knot，它在端点处不会因外推过度而产生虚假曲率变号（即不会
伪造拐点），并能精确再现不超过二次的多项式；内部曲率保持 O(h^4)
收敛阶。

曲率（几何量，与参数化无关）：
    κ(t) = |x'y'' - y'x''| / (x'^2 + y'^2)^(3/2)，恒为非负 float。
拐点定义为有符号曲率分子 q = x'y'' - y'x'' 的变号位置：先在 n 个
均匀采样点上定位变号区间，再用二分法把根求精；采样点恰好落在
零点上时按其两侧符号是否相反判定，避免误报与重复。

设计说明：
- 所有中间量均为调用内局部变量，实例不持有任何可变状态，线程安全。
- 退化点（切向量为 0、曲率无定义）按题面允许的方案定义为 0.0。
- 非有限输入（NaN/Inf）、参数越界、点数不足、n 非正整数一律 ValueError。
- 仅使用标准库，三对角求解为 O(m)，满足 1 万点 400 ms 的性能上界。
"""

import math

# 速度平方低于该阈值视为退化点（曲率定义为 0），避免除零放大。
_EPS_SPEED2 = 1e-18
# 拐点二分次数：2^-40 远高于 1e-4 精度要求。
_BISECT_ITERS = 40


class Curvature:
    # ------------------------------------------------------------------
    # 输入校验
    # ------------------------------------------------------------------
    @staticmethod
    def _prepare(points):
        """归一化点列：返回 (pts, m)，m 为区间数。"""
        pts = []
        for p in points:
            try:
                x, y = p
                fx = float(x)
                fy = float(y)
            except (TypeError, ValueError):
                raise ValueError("points 中的点必须是两个数值组成的序列")
            if not (math.isfinite(fx) and math.isfinite(fy)):
                raise ValueError("points 中存在非有限数值（NaN/Inf）")
            pts.append((fx, fy))
        if len(pts) < 2:
            raise ValueError("至少需要 2 个点才能定义曲线")
        return pts, len(pts) - 1

    # ------------------------------------------------------------------
    # 夹持三次样条：求各节点第二导数 M_i（均匀节点，h=1）
    # ------------------------------------------------------------------
    @staticmethod
    def _solve_clamped(values, m):
        """夹持样条：返回各节点第二导数 M（长度 m+1）。

        内部方程（i=1..m-1）：M_{i-1} + 4 M_i + M_{i+1}
            = 6 * (v_{i-1} - 2 v_i + v_{i+1})
        端点一阶导 D0、Dm 用三点单边差分 O(h^2) 估计：
            D0 = (-3v0 + 4v1 - v2) / 2
            Dm = (v_{m-2} - 4v_{m-1} + 3v_m) / 2
        对应边界方程（h=1）：
            2 M0 + M1 = 6 * ((v1 - v0) - D0)
            M_{m-1} + 2 Mm = 6 * (Dm - (v_m - v_{m-1}))
        组装成 (m+1) 阶三对角系统，Thomas 算法 O(m) 求解。
        """
        if m == 1:
            # 单段线性，第二导数恒为 0。
            return [0.0, 0.0]

        n = m + 1
        lo = [0.0] * n
        di = [0.0] * n
        up = [0.0] * n
        rhs = [0.0] * n

        d0 = (-3.0 * values[0] + 4.0 * values[1] - values[2]) * 0.5
        dm = (values[m - 2] - 4.0 * values[m - 1] + 3.0 * values[m]) * 0.5

        # 首行：2 M0 + M1
        di[0] = 2.0
        up[0] = 1.0
        rhs[0] = 6.0 * ((values[1] - values[0]) - d0)
        # 内部行
        for i in range(1, m):
            lo[i] = 1.0
            di[i] = 4.0
            up[i] = 1.0
            rhs[i] = 6.0 * (values[i - 1] - 2.0 * values[i] + values[i + 1])
        # 末行：M_{m-1} + 2 Mm
        lo[m] = 1.0
        di[m] = 2.0
        rhs[m] = 6.0 * (dm - (values[m] - values[m - 1]))

        # Thomas 消元
        cp = [0.0] * n
        dp = [0.0] * n
        cp[0] = up[0] / di[0]
        dp[0] = rhs[0] / di[0]
        for i in range(1, n):
            denom = di[i] - lo[i] * cp[i - 1]
            cp[i] = up[i] / denom if i < m else 0.0
            dp[i] = (rhs[i] - lo[i] * dp[i - 1]) / denom

        M = [0.0] * n
        M[m] = dp[m]
        for i in range(m - 1, -1, -1):
            M[i] = dp[i] - cp[i] * M[i + 1]
        return M

    # ------------------------------------------------------------------
    # 逐点求导（Hermite 形式，h=1）
    # ------------------------------------------------------------------
    @staticmethod
    def _deriv1(values, M, k, s):
        """区间 [k, k+1]、局部参数 s∈[0,1] 处的一阶导数。"""
        s2 = s * s
        return (
            values[k + 1] - values[k]
            + M[k] * (-2.0 + 6.0 * s - 3.0 * s2) / 6.0
            + M[k + 1] * (3.0 * s2 - 1.0) / 6.0
        )

    @staticmethod
    def _deriv2(M, k, s):
        """二阶导数：相邻节点第二导数的线性插值。"""
        return (1.0 - s) * M[k] + s * M[k + 1]

    def _kinematics(self, xs, ys, Mx, My, m, u):
        """节点参数 u 处的 (x', y', x'', y'')。"""
        k = int(u)
        if k >= m:
            k = m - 1
        elif k < 0:
            k = 0
        s = u - k
        return (
            self._deriv1(xs, Mx, k, s),
            self._deriv1(ys, My, k, s),
            self._deriv2(Mx, k, s),
            self._deriv2(My, k, s),
        )

    def _build(self, pts, m):
        """一次性构建 x/y 两套样条系数。"""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        Mx = self._solve_clamped(xs, m)
        My = self._solve_clamped(ys, m)
        return xs, ys, Mx, My

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def curvature(self, points, t):
        """返回参数 t ∈ [0, 1] 处的非负曲率（float）。

        退化点（切向量为 0、曲率无定义）返回 0.0。
        """
        pts, m = self._prepare(points)
        try:
            ft = float(t)
        except (TypeError, ValueError):
            raise ValueError("t 必须是数值")
        if not math.isfinite(ft):
            raise ValueError("t 必须是有限数值")
        if not (0.0 <= ft <= 1.0):
            raise ValueError("t 必须落在 [0, 1] 内")

        xs, ys, Mx, My = self._build(pts, m)
        dx1, dy1, dx2, dy2 = self._kinematics(xs, ys, Mx, My, m, ft * m)

        speed2 = dx1 * dx1 + dy1 * dy1
        if speed2 <= _EPS_SPEED2:
            return 0.0
        q = dx1 * dy2 - dy1 * dx2
        return float(abs(q) / (speed2 * math.sqrt(speed2)))

    def inflections(self, points, n):
        """检测拐点，返回有符号曲率变号处的参数 t 列表（升序 float）。

        在 [0, 1] 上均匀取 n 个采样点定位变号区间，再二分求精；
        采样点恰好落在零点时，按其两侧符号是否相反判定，避免误报。
        """
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise ValueError("n 必须是正整数")
        pts, m = self._prepare(points)
        xs, ys, Mx, My = self._build(pts, m)

        def signed_q(u):
            dx1, dy1, dx2, dy2 = self._kinematics(xs, ys, Mx, My, m, u)
            return dx1 * dy2 - dy1 * dx2

        if n == 1:
            return []

        step = 1.0 / (n - 1)
        q = [signed_q(i * step * m) for i in range(n)]

        roots = []
        i = 0
        while i < n - 1:
            a, b = q[i], q[i + 1]
            if a * b < 0.0:
                # 严格异号：二分求 q(u)=0 的根
                lo = i * step * m
                hi = (i + 1) * step * m
                for _ in range(_BISECT_ITERS):
                    mid = 0.5 * (lo + hi)
                    if signed_q(mid) * a < 0.0:
                        hi = mid
                    else:
                        lo = mid
                roots.append(0.5 * (lo + hi) / m)
                i += 1
            elif a == 0.0:
                # 跨过一段（或单个）零采样点：仅两端符号相反才算变号
                j = i
                while j < n and q[j] == 0.0:
                    j += 1
                left = q[i - 1] if i > 0 else 0.0
                right = q[j] if j < n else 0.0
                if (left > 0.0 and right < 0.0) or (left < 0.0 and right > 0.0):
                    roots.append(0.5 * (i + j - 1) * step)
                i = j
            else:
                i += 1
        return roots
