"""glslparse 扩展验收测试：layout / 数组 / 精度 / 行列号 / 错误分类 /
性能 / 并发安全。只新增，不改动既有 tests/test_core.py。"""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import glslparse
from glslparse import (
    DuplicateDeclarationError,
    GlslParse,
    GlslParseError,
    InvalidInputError,
    InvalidTypeError,
    MissingSemicolonError,
)


def _g():
    return GlslParse()


# ---------------------------------------------------------------- layout
def test_layout_location_binding():
    decls = _g().parse(
        "layout(location = 0) in vec3 aPos;\n"
        "layout(binding=2, set=1) uniform sampler2D tex;\n"
    )
    assert decls[0]["layout"] == {"location": 0}
    assert decls[1]["layout"] == {"binding": 2, "set": 1}
    assert decls[0]["storage"] == "in"
    assert decls[1]["storage"] == "uniform"


def test_layout_flag_without_value():
    decls = _g().parse("layout(std140) uniform vec4 block[4];\n")
    assert decls[0]["layout"] == {"std140": None}


def test_layout_bad_syntax_reports_position():
    with pytest.raises(GlslParseError) as ei:
        _g().parse("layout(location = ) in vec3 a;\n")
    assert ei.value.line == 1
    assert ei.value.col > 1


# ----------------------------------------------------------------- 数组
def test_array_single_dimension_int():
    decls = _g().parse("uniform float uArr[4];\n")
    assert decls[0]["array"] == 4


def test_array_multi_dimension_list():
    decls = _g().parse("uniform float m[2][3];\n")
    assert decls[0]["array"] == [2, 3]


def test_array_unsized_and_identifier_dim():
    decls = _g().parse("uniform float a[];\nuniform float b[BLOCK];\n")
    assert decls[0]["array"] is None
    assert decls[1]["array"] == "BLOCK"


def test_array_bad_dimension():
    with pytest.raises(GlslParseError) as ei:
        _g().parse("uniform float a[;];\n")
    assert ei.value.line == 1


# ----------------------------------------------------------------- 精度
def test_precision_before_and_after_storage():
    decls = _g().parse(
        "highp uniform vec4 color;\n"
        "uniform lowp float mask;\n"
        "layout(location=1) mediump out vec2 uv;\n"
    )
    assert [d["precision"] for d in decls] == ["highp", "lowp", "mediump"]


def test_global_precision_statement_skipped_as_decl():
    decls = _g().parse("precision highp float;\nuniform float a;\n")
    assert len(decls) == 1
    assert decls[0]["name"] == "a"


# ------------------------------------------------- 注释/预处理与行号保留
def test_line_comment_keeps_line_numbers():
    decls = _g().parse("// c\nuniform float a;\n")
    assert decls[0]["line"] == 2
    assert decls[0]["col"] == 15


def test_block_comment_spanning_lines():
    src = "/*\n\n multi\n line\n */\nuniform float b;\n"
    decls = _g().parse(src)
    assert len(decls) == 1
    assert decls[0]["line"] == 6
    assert decls[0]["col"] == 15


def test_preprocessor_lines_skipped_but_counted():
    src = (
        "#version 310 es\n"
        "#define FOO \\\n 1\n"
        "uniform float c;\n"
    )
    decls = _g().parse(src)
    assert len(decls) == 1
    assert decls[0]["line"] == 4


def test_unterminated_block_comment():
    with pytest.raises(GlslParseError) as ei:
        _g().parse("/* never closed\nuniform float x;\n")
    assert ei.value.line == 1


# ------------------------------------------------------------- 错误分类
def test_missing_semicolon_has_line_col_and_code():
    with pytest.raises(MissingSemicolonError) as ei:
        _g().parse("uniform float a\n")
    err = ei.value
    assert err.code == "missing_semicolon"
    assert (err.line, err.col) == (1, 16)
    assert isinstance(err, GlslParseError)
    assert isinstance(err, ValueError)


def test_invalid_type_distinguishable():
    with pytest.raises(InvalidTypeError) as ei:
        _g().parse("uniform vec99 x;\n")
    err = ei.value
    assert err.code == "invalid_type"
    assert (err.line, err.col) == (1, 9)


def test_duplicate_declaration_distinguishable():
    src = "uniform float x;\nuniform float x;\n"
    with pytest.raises(DuplicateDeclarationError) as ei:
        _g().parse(src)
    err = ei.value
    assert err.code == "duplicate_declaration"
    assert err.line == 2
    assert err.col == 15


def test_error_classes_are_distinct_for_distinct_inputs():
    with pytest.raises(GlslParseError) as e1:
        _g().parse("uniform float a\n")
    with pytest.raises(GlslParseError) as e2:
        _g().parse("uniform vec99 a;\n")
    with pytest.raises(GlslParseError) as e3:
        _g().parse("uniform float a;\nuniform float a;\n")
    assert {type(e1.value), type(e2.value), type(e3.value)} == {
        MissingSemicolonError,
        InvalidTypeError,
        DuplicateDeclarationError,
    }


def test_invalid_input_classification():
    for bad in (123, None, b"uniform float x;", 3.14):
        with pytest.raises(InvalidInputError):
            _g().parse(bad)
    # 旧契约：依然是 ValueError
    with pytest.raises(ValueError):
        _g().parse(123)


def test_unknown_storage_qualifier():
    with pytest.raises(GlslParseError) as ei:
        _g().parse("static float a;\n")
    assert ei.value.line == 1
    assert ei.value.col == 1


# ------------------------------------------------------------------ 结构
def test_multi_declarators_and_fields():
    decls = _g().parse("uniform float a, b[2], c;\n")
    assert [d["name"] for d in decls] == ["a", "b", "c"]
    assert decls[1]["array"] == 2
    assert decls[0]["type"] == "float"
    assert decls[0]["storage"] == "uniform"
    assert decls[0]["layout"] is None
    assert decls[0]["precision"] is None
    assert set(decls[0]) == {
        "name", "type", "storage", "line", "col", "array", "layout",
        "precision",
    }


def test_empty_and_whitespace_only():
    assert _g().parse("") == []
    assert _g().parse("\n\n  \n// only comment\n") == []


# ------------------------------------------------------------------ 性能
def test_10k_lines_under_300ms():
    src = "".join("uniform vec4 u%d;\n" % i for i in range(10000))
    for _ in range(3):
        t0 = time.perf_counter()
        decls = _g().parse(src)
        elapsed = time.perf_counter() - t0
        assert len(decls) == 10000
        assert elapsed < 0.3, "parse took %.3fs" % elapsed


# ---------------------------------------------------------------- 并发
def test_concurrent_parse_is_thread_safe():
    parser = GlslParse()
    src = (
        "layout(location=0) highp in vec3 aPos;\n"
        "uniform sampler2D tex[4];\n"
        "// comment\n"
        "#define X 1\n"
        "out lowp vec2 vUV;\n"
    )
    expected = parser.parse(src)

    def work(_):
        return parser.parse(src)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, range(64)))
    assert all(r == expected for r in results)
