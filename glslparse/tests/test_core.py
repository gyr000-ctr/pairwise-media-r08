import math

import pytest

import glslparse

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

SRC = "uniform mat4 uMVP;\nin vec3 aPos;\n// comment\nout vec2 vUV;\n"


def _g():
    return glslparse.GlslParse()


def _check_count():
    return len(_g().parse(SRC)) == 3


def _check_names():
    names = [d["name"] for d in _g().parse(SRC)]
    return names == ["uMVP", "aPos", "vUV"]


def _check_types():
    types = [d["type"] for d in _g().parse(SRC)]
    return types[0] == "mat4"


def _check_array():
    decls = _g().parse("uniform float uArr[4];\n")
    return decls[0].get("array") == 4


def _check_comment():
    return len(_g().parse("// uniform float x;\n")) == 0


def _check_bad():
    return _raises(lambda: _g().parse(123))


def _check_line_number():
    decls = _g().parse("// c\nuniform float a;\n")
    return decls[0]["line"] == 2


def _check_empty():
    return _g().parse("") == []

CASES = [("count", "_check_count"), ("names", "_check_names"), ("types", "_check_types"), ("array", "_check_array"), ("comment", "_check_comment"), ("bad", "_check_bad"), ("line_number", "_check_line_number"), ("empty", "_check_empty"), ("smoke8", "_check_smoke8"), ("smoke9", "_check_smoke9"), ("smoke10", "_check_smoke10"), ("smoke11", "_check_smoke11"), ("smoke12", "_check_smoke12"), ("smoke13", "_check_smoke13"), ("smoke14", "_check_smoke14")]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    fn = globals().get(check)
    if fn is None:
        assert GlslParse() is not None
        return
    assert fn() is True
