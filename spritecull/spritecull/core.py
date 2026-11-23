"""spritecull 核心 API：屏幕空间精灵裁剪与纹理批处理。

裁剪语义
--------
- 精灵包围盒 ``box = (x, y, w, h)``，屏幕矩形 ``screen = (x, y, w, h)``，
  均采用半开区间 ``[x, x + w) x [y, y + h)``。
- 精灵包围盒与屏幕矩形相交（含部分相交）即保留；完全在屏幕外才剔除，
- 结果与逐精灵 AABB 包围盒测试完全一致。

批处理语义
----------
- 可见精灵按 ``tex`` 分组，每个不同纹理恰好一个批次，因此批次数取到最小值
  （等于可见精灵中不同纹理的数量）。
- 批次与组内精灵均按首次出现顺序排列，保证结果确定。

错误分类
--------
- 类型错误（非数值、非映射精灵等）抛 :class:`TypeError`。
- 值错误（分量缺失、长度不为 4、NaN/Inf 等非有限值、宽高非正）抛
  :class:`ValueError`。

并发
----
:class:`SpriteCull` 不持有任何可变状态，``cull`` 为纯函数式计算，
可被多线程并发调用。
"""

import math
from collections.abc import Mapping

__all__ = ["SpriteCull", "Batch"]


def _is_real_number(value):
    # bool 是 int 的子类，作为有限数值接受；complex/Decimal 等拒绝。
    return isinstance(value, (int, float))


def _validate_rect(rect, what):
    """校验并返回一个 (x, y, w, h) 矩形。"""
    try:
        items = tuple(rect)
    except TypeError as exc:
        raise TypeError(
            "%s must be a sequence of 4 numbers (x, y, w, h)" % what
        ) from exc
    if len(items) != 4:
        raise ValueError(
            "%s must have exactly 4 components (x, y, w, h), got %d"
            % (what, len(items))
        )
    x, y, w, h = items
    for name, value in (("x", x), ("y", y), ("w", w), ("h", h)):
        if not _is_real_number(value):
            raise TypeError(
                "%s %s must be a real number, got %r" % (what, name, value)
            )
        if not math.isfinite(value):
            raise ValueError(
                "%s %s must be finite, got %r" % (what, name, value)
            )
    if w <= 0 or h <= 0:
        raise ValueError(
            "%s width and height must be positive, got (w=%r, h=%r)" % (what, w, h)
        )
    return x, y, w, h


class Batch:
    """同一纹理的可见精灵批次。

    同时支持三种访问方式，便于不同调用方使用：

    - 属性访问：``batch.tex`` / ``batch.sprites``（``texture`` 为别名）；
    - 映射访问：``batch["tex"]`` / ``batch["sprites"]``；
    - 序列访问：``len(batch)``、``batch[i]``、``for s in batch``
      （迭代得到组内精灵）。
    """

    __slots__ = ("tex", "sprites")

    def __init__(self, tex, sprites):
        self.tex = tex
        self.sprites = list(sprites)

    @property
    def texture(self):
        return self.tex

    def keys(self):
        return ("tex", "sprites")

    def items(self):
        return (("tex", self.tex), ("sprites", self.sprites))

    def values(self):
        return (self.tex, self.sprites)

    def __len__(self):
        return len(self.sprites)

    def __iter__(self):
        return iter(self.sprites)

    def __contains__(self, item):
        return item in self.sprites

    def __getitem__(self, key):
        if isinstance(key, str):
            if key == "tex" or key == "texture":
                return self.tex
            if key == "sprites" or key == "sprite":
                return self.sprites
            raise KeyError(key)
        return self.sprites[key]

    def __eq__(self, other):
        if isinstance(other, Batch):
            return self.tex == other.tex and self.sprites == other.sprites
        if isinstance(other, Mapping):
            other_tex = other.get("tex", other.get("texture"))
            return other_tex == self.tex and other.get("sprites") == self.sprites
        if isinstance(other, tuple) and len(other) == 2:
            return other[0] == self.tex and other[1] == self.sprites
        return NotImplemented

    def __repr__(self):
        return "Batch(tex=%r, sprites=%r)" % (self.tex, self.sprites)


class SpriteCull:
    """屏幕空间精灵裁剪器（无状态，线程安全）。"""

    def cull(self, sprites, screen):
        """裁剪精灵并按纹理分批。

        :param sprites: 可迭代的精灵映射，每个精灵形如
            ``{"tex": 任意可哈希纹理标识, "box": (x, y, w, h)}``。
        :param screen: 屏幕矩形 ``(x, y, w, h)``，宽高必须为正。
        :return: ``Batch`` 列表；每个出现过的可见纹理恰好一个批次，
            批次按纹理首次出现顺序排列。
        :raises TypeError: 输入类型不合法。
        :raises ValueError: 输入取值不合法（缺失字段、非有限值、尺寸非正等）。
        """
        sx, sy, sw, sh = _validate_rect(screen, "screen")
        screen_right = sx + sw
        screen_bottom = sy + sh

        try:
            iterator = iter(sprites)
        except TypeError as exc:
            raise TypeError("sprites must be an iterable of sprite mappings") from exc

        groups = {}
        order = []
        isfinite = math.isfinite

        for sprite in iterator:
            if not isinstance(sprite, Mapping):
                raise TypeError(
                    "each sprite must be a mapping with 'tex' and 'box' keys, "
                    "got %r" % (sprite,)
                )
            try:
                tex = sprite["tex"]
                box = sprite["box"]
            except KeyError as exc:
                raise ValueError(
                    "sprite is missing required key %r" % (exc.args[0],)
                ) from exc

            try:
                hash(tex)
            except TypeError as exc:
                raise TypeError("sprite tex must be hashable, got %r" % (tex,)) from exc

            try:
                box_items = tuple(box)
            except TypeError as exc:
                raise TypeError(
                    "sprite box must be a sequence of 4 numbers (x, y, w, h)"
                ) from exc
            if len(box_items) != 4:
                raise ValueError(
                    "sprite box must have exactly 4 components (x, y, w, h), got %d"
                    % len(box_items)
                )
            x, y, w, h = box_items
            for name, value in (("x", x), ("y", y), ("w", w), ("h", h)):
                if not _is_real_number(value):
                    raise TypeError(
                        "sprite box %s must be a real number, got %r" % (name, value)
                    )
                if not isfinite(value):
                    raise ValueError(
                        "sprite box %s must be finite, got %r" % (name, value)
                    )
            if w <= 0 or h <= 0:
                raise ValueError(
                    "sprite box width and height must be positive, got (w=%r, h=%r)"
                    % (w, h)
                )

            # 半开矩形 AABB 相交测试：与逐精灵包围盒测试一致。
            if x < screen_right and x + w > sx and y < screen_bottom and y + h > sy:
                bucket = groups.get(tex)
                if bucket is None:
                    bucket = []
                    groups[tex] = bucket
                    order.append(tex)
                bucket.append(sprite)

        return [Batch(tex, groups[tex]) for tex in order]
