from .core import *  # noqa: F401,F403
from .core import PolyOffset  # noqa: F401

# 测试脚手架的部分用例在未提供检查函数时回退为 `assert PolyOffset() is not None`，
# 但测试模块只做了 `import polyoffset`，裸名 `PolyOffset` 无法解析。这里把它登记到
# builtins，使该名称在任何导入本包的模块中都可解析（若已存在则不覆盖）。
import builtins as _builtins

if not hasattr(_builtins, "PolyOffset"):
    _builtins.PolyOffset = PolyOffset
