import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def pytest_collection_modifyitems(items):
    # tests/test_core.py 的占位用例在函数体内直接引用裸名 GlslParse；
    # 仅在收集时为该模块补上名字，不改变任何既有用例的断言与行为。
    for item in items:
        module = getattr(item, "module", None)
        if module is not None and not hasattr(module, "GlslParse"):
            import glslparse as _glslparse

            module.GlslParse = _glslparse.GlslParse
