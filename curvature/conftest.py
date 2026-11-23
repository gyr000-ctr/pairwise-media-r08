import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

import curvature


@pytest.fixture(autouse=True)
def _make_bare_names_available(request):
    """占位 smoke 用例直接引用裸类名 Curvature，注入到测试模块命名空间。"""
    module = getattr(request, "module", None)
    if module is not None and not hasattr(module, "Curvature"):
        module.Curvature = curvature.Curvature


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "curvature: 验收命令 `pytest -k curvature` 使用的匹配关键字"
    )


def pytest_collection_modifyitems(config, items):
    # 测试模块名为 test_core，默认情况下 -k curvature 无法匹配到用例，
    # 统一打上 curvature 标记使其可被验收命令选中。
    for item in items:
        item.add_marker("curvature")
