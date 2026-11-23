"""polyoffset 核心 API：简单多边形的内缩/外扩（miter 偏移）。

设计要点：
- 边沿外法向平移、相邻偏移边求交，得到精确平行多边形（凸多边形与鞋带公式
  严格一致）；
- 结果若自交/退化/翻面，则在 0 与目标距离之间二分回退到安全距离，绝不
  输出自交多边形，且面积随距离单调；
- 全部计算只使用局部变量，无共享可变状态，并发安全。
"""

from __future__ import annotations

import math

__all__ = ["PolyOffset"]

_MIN_AREA = 1e-12   # 偏移结果的最小有效面积
_PARALLEL = 1e-12   # 相邻边平行判定阈值（相对边长平方）


def _signed_area(pts):
    """鞋带公式有符号面积（逆时针为正）。"""
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def _is_convex(pts):
    """是否凸多边形（允许相邻边共线）。"""
    n = len(pts)
    sign = 0
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        cx, cy = pts[(i + 2) % n]
        c = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if c > 0.0:
            if sign < 0:
                return False
            sign = 1
        elif c < 0.0:
            if sign > 0:
                return False
            sign = -1
    return True


def _self_intersects(pts):
    """简单多边形自交检测（只检查非相邻边对，含端点接触）。"""
    n = len(pts)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ux, uy = bx - ax, by - ay
        lo_x, hi_x = (ax, bx) if ax <= bx else (bx, ax)
        lo_y, hi_y = (ay, by) if ay <= by else (by, ay)
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # 首尾边相邻
            cx, cy = pts[j]
            dx, dy = pts[(j + 1) % n]
            # 包围盒快速排除
            if hi_x < (cx if cx <= dx else dx) or (cx if cx >= dx else dx) < lo_x:
                continue
            if hi_y < (cy if cy <= dy else dy) or (cy if cy >= dy else dy) < lo_y:
                continue
            d1 = ux * (cy - ay) - uy * (cx - ax)
            d2 = ux * (dy - ay) - uy * (dx - ax)
            wx, wy = dx - cx, dy - cy
            d3 = wx * (ay - cy) - wy * (ax - cx)
            d4 = wx * (by - cy) - wy * (bx - cx)
            if d1 * d2 < 0.0 and d3 * d4 < 0.0:
                return True
            if d1 == 0.0 or d2 == 0.0 or d3 == 0.0 or d4 == 0.0:
                # 共线/端点接触：检查接触点是否落在线段上
                if d1 == 0.0 and lo_x <= cx <= hi_x and lo_y <= cy <= hi_y:
                    return True
                if d2 == 0.0 and lo_x <= dx <= hi_x and lo_y <= dy <= hi_y:
                    return True
                clo_x, chi_x = (cx, dx) if cx <= dx else (dx, cx)
                clo_y, chi_y = (cy, dy) if cy <= dy else (dy, cy)
                if d3 == 0.0 and clo_x <= ax <= chi_x and clo_y <= ay <= chi_y:
                    return True
                if d4 == 0.0 and clo_x <= bx <= chi_x and clo_y <= by <= chi_y:
                    return True
    return False


class PolyOffset:
    """多边形偏移器。无内部状态，所有方法可并发调用。"""

    # ---------------- 公共 API ----------------

    def area(self, poly):
        """鞋带公式面积（恒为非负）。非法多边形抛错。"""
        pts = self._validate_poly(poly)
        return abs(_signed_area(pts))

    def offset(self, poly, d):
        """按距离 d 偏移多边形：d > 0 外扩，d < 0 内缩，d = 0 原样返回。

        返回新的 ``list[tuple[float, float]]``，不修改入参。结果保持原环绕
        方向且不自交；若目标距离会导致自交、退化或翻面，则回退到 0 与 d
        之间的安全距离（二分查找），保证面积随 d 单调。
        """
        pts = self._validate_poly(poly)
        dist = self._validate_d(d)
        if dist == 0.0:
            return list(pts)
        convex = _is_convex(pts)
        result = self._try_offset(pts, dist, convex)
        if result is not None:
            return result
        return self._fallback(pts, dist, convex)

    # ---------------- 输入校验 ----------------

    @staticmethod
    def _validate_d(d):
        if isinstance(d, bool) or not isinstance(d, (int, float)):
            raise TypeError("偏移距离必须是实数（int/float）")
        d = float(d)
        if not math.isfinite(d):
            raise ValueError("偏移距离必须是有限值，得到 %r" % (d,))
        return d

    @classmethod
    def _validate_poly(cls, poly):
        if isinstance(poly, (str, bytes)):
            raise TypeError("多边形必须是顶点序列，而非字符串")
        try:
            raw = list(poly)
        except TypeError:
            raise TypeError("多边形必须是可迭代的顶点序列") from None
        if len(raw) < 3:
            raise ValueError("多边形至少需要 3 个顶点，得到 %d 个" % len(raw))
        pts = []
        for p in raw:
            if isinstance(p, (str, bytes)):
                raise TypeError("顶点必须是 (x, y) 数对")
            try:
                x, y = p
            except (TypeError, ValueError):
                raise TypeError("顶点必须是 (x, y) 数对，得到 %r" % (p,)) from None
            for v in (x, y):
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise TypeError("顶点坐标必须是实数，得到 %r" % (v,))
                if not math.isfinite(v):
                    raise ValueError("顶点坐标必须是有限值，得到 %r" % (v,))
            pts.append((float(x), float(y)))
        n = len(pts)
        if len(set(pts)) != n:
            raise ValueError("多边形存在重复顶点")
        if _signed_area(pts) == 0.0:
            raise ValueError("多边形面积为零（退化/共线）")
        if not _is_convex(pts) and _self_intersects(pts):
            raise ValueError("多边形自交，非法输入")
        return pts

    # ---------------- 偏移计算 ----------------

    def _try_offset(self, pts, d, convex):
        """计算 miter 偏移；结果无效（退化/翻面/自交）时返回 None。"""
        n = len(pts)
        orient = 1.0 if _signed_area(pts) > 0.0 else -1.0
        # 每条边的单位外法向
        normals = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            inv = orient / math.hypot(x2 - x1, y2 - y1)
            normals.append(((y2 - y1) * inv, -(x2 - x1) * inv))
        out = []
        for i in range(n):
            j = i - 1 if i else n - 1
            k = (i + 1) % n
            ux = pts[i][0] - pts[j][0]
            uy = pts[i][1] - pts[j][1]
            vx = pts[k][0] - pts[i][0]
            vy = pts[k][1] - pts[i][1]
            denom = ux * vy - uy * vx
            scale = math.hypot(ux, uy) * math.hypot(vx, vy)
            if abs(denom) <= _PARALLEL * scale:
                # 相邻边（近）平行：直接沿法向平移顶点
                out.append((pts[i][0] + d * normals[i][0],
                            pts[i][1] + d * normals[i][1]))
                continue
            # 相邻两条偏移边的直线交点（miter join）
            ax = pts[j][0] + d * normals[j][0]
            ay = pts[j][1] + d * normals[j][1]
            bx = pts[i][0] + d * normals[i][0]
            by = pts[i][1] + d * normals[i][1]
            t = ((bx - ax) * vy - (by - ay) * vx) / denom
            out.append((ax + t * ux, ay + t * uy))
        for x, y in out:
            if not (math.isfinite(x) and math.isfinite(y)):
                return None
        sa = _signed_area(out)
        if sa * orient <= _MIN_AREA:
            return None  # 退化或环绕方向翻转
        # 每条偏移边必须与原边同向。越过坍缩点后 miter 多边形会“翻面”
        # 重新成为同向简单多边形（边全部反向），仅靠面积/自交无法识别。
        for i in range(n):
            ex = out[(i + 1) % n][0] - out[i][0]
            ey = out[(i + 1) % n][1] - out[i][1]
            ox = pts[(i + 1) % n][0] - pts[i][0]
            oy = pts[(i + 1) % n][1] - pts[i][1]
            if ex * ox + ey * oy <= 0.0:
                return None
        # 凸多边形的合法 miter 偏移必为凸（不会自交），可跳过 O(n^2) 检测
        if not convex and _self_intersects(out):
            return None
        return out

    def _fallback(self, pts, d, convex):
        """在 0 与 d 之间二分最大的安全偏移距离。

        一直迭代到浮点精度极限（mid 无法再细分），使不同目标距离回退到
        同一个边界值，保证结果确定且面积随距离单调。
        """
        lo, hi = 0.0, d
        best = list(pts)
        for _ in range(1200):
            mid = 0.5 * (lo + hi)
            if mid == lo or mid == hi:
                break
            r = self._try_offset(pts, mid, convex)
            if r is None:
                hi = mid
            else:
                lo = mid
                best = r
        return best
