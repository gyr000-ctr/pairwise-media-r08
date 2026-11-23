"""GLSL 声明解析器（无外部依赖，线程安全）。

支持的声明语法（GLSL ES 风格）::

    [layout(qualifier=value, ...)] [precision] storage [precision] type
        name[dim]... [, name[dim]...]* ;

其中 storage 为 ``uniform`` / ``in`` / ``out``，precision 为
``highp`` / ``mediump`` / ``lowp``。注释（``//``、``/* */``）与预处理行
（``#`` 开头，支持反斜杠续行）被跳过，但行号与列号始终相对于原始源码保留。

解析结果为 dict 列表，每项包含::

    name, type, storage, line, col, array, layout, precision

``parse`` 不读写任何实例/全局可变状态，同一个 ``GlslParse`` 实例可被多线程
并发调用。
"""

import re

__all__ = [
    "GlslParse",
    "GlslParseError",
    "InvalidInputError",
    "MissingSemicolonError",
    "InvalidTypeError",
    "DuplicateDeclarationError",
]

_STORAGE = frozenset(("uniform", "in", "out"))
_PRECISION = frozenset(("highp", "mediump", "lowp"))

_SCALAR_TYPES = frozenset(
    ("float", "int", "uint", "bool", "double", "void", "atomic_uint")
)
_VEC_TYPES = frozenset(
    prefix + str(n)
    for prefix in ("vec", "ivec", "uvec", "bvec", "dvec")
    for n in (2, 3, 4)
)
_MAT_TYPES = frozenset(
    "mat%dx%d" % (a, b) for a in (2, 3, 4) for b in (2, 3, 4)
) | frozenset(("mat2", "mat3", "mat4"))
_SAMPLER_TYPES = frozenset(
    (
        "sampler1D",
        "sampler2D",
        "sampler3D",
        "samplerCube",
        "sampler2DArray",
        "samplerCubeArray",
        "sampler2DShadow",
        "sampler2DArrayShadow",
        "samplerCubeShadow",
        "sampler2DMS",
        "sampler2DMSArray",
        "samplerBuffer",
        "samplerExternalOES",
        "sampler2DRect",
        "sampler2DRectShadow",
        "isampler1D",
        "isampler2D",
        "isampler3D",
        "isamplerCube",
        "isampler2DArray",
        "isampler2DMS",
        "isampler2DMSArray",
        "isamplerBuffer",
        "isampler2DRect",
        "usampler1D",
        "usampler2D",
        "usampler3D",
        "usamplerCube",
        "usampler2DArray",
        "usampler2DMS",
        "usampler2DMSArray",
        "usamplerBuffer",
        "usampler2DRect",
    )
)
TYPES = frozenset(
    _SCALAR_TYPES | _VEC_TYPES | _MAT_TYPES | _SAMPLER_TYPES
)

# 注释与预处理行：匹配内容整体替换为等长空白（保留换行符），行列号不变。
_STRIP_RE = re.compile(
    r"//[^\n]*"
    r"|/\*[^\n]*(?:\n[^\n]*?)*?\*/"
    r"|^[ \t]*#(?:\\\r?\n|[^\n])*",
    re.MULTILINE,
)
_NEWLINE_RE = re.compile(r"\n")
_TOKEN_RE = re.compile(
    r"\s+"
    r"|\d+"
    r"|[A-Za-z_]\w*"
    r"|==|!=|<=|>=|&&|\|\|"
    r"|[][;,()=.+\-*/<>!&|^~%?:{}]"
)


class GlslParseError(ValueError):
    """解析错误基类，携带 1 起始的 ``line`` / ``col``。"""

    code = "syntax_error"

    def __init__(self, message, line, col):
        self.line = int(line)
        self.col = int(col)
        super().__init__("%s (line %d, col %d)" % (message, self.line, self.col))


class InvalidInputError(GlslParseError):
    """输入不是合法的 GLSL 源码字符串。"""

    code = "invalid_input"

    def __init__(self, message):
        super().__init__(message, 0, 0)


class MissingSemicolonError(GlslParseError):
    """声明缺少终止分号。"""

    code = "missing_semicolon"


class InvalidTypeError(GlslParseError):
    """使用了未知/非法类型名。"""

    code = "invalid_type"


class DuplicateDeclarationError(GlslParseError):
    """同名变量被重复声明。"""

    code = "duplicate_declaration"


def _blank_out(match):
    # 保留换行以维持行号，其余字符替换为空格以维持列号。
    return "".join("\n" if ch == "\n" else " " for ch in match.group(0))


def _line_starts(src):
    starts = [0]
    for m in _NEWLINE_RE.finditer(src):
        starts.append(m.end())
    return starts


def _locate(line_starts, pos):
    """根据字节偏移返回 (1 起始行号, 1 起始列号)。"""
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) >> 1
        if line_starts[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1, pos - line_starts[lo] + 1


def _tokenize(src):
    """把已剥离注释/预处理行的源码切成 token 列表。

    每个 token 为 ``(kind, value, line, col)``，kind 为
    ``id`` / ``int`` / ``punct``。
    """
    line_starts = _line_starts(src)
    tokens = []
    pos = 0
    total = len(src)
    for m in _TOKEN_RE.finditer(src):
        if m.start() != pos:
            line, col = _locate(line_starts, pos)
            raise GlslParseError(
                "unexpected character %r" % src[pos], line, col
            )
        text = m.group(0)
        pos = m.end()
        if text.isspace():
            continue
        line, col = _locate(line_starts, m.start())
        if text[0].isdigit():
            tokens.append(("int", int(text), line, col))
        elif text[0].isalpha() or text[0] == "_":
            tokens.append(("id", text, line, col))
        else:
            tokens.append(("punct", text, line, col))
    if pos != total:
        line, col = _locate(line_starts, pos)
        raise GlslParseError("unexpected character %r" % src[pos], line, col)
    eof_line, eof_col = _locate(line_starts, total)
    return tokens, eof_line, eof_col


class _Parser:
    def __init__(self, tokens, eof_line, eof_col):
        self.toks = tokens
        self.n = len(tokens)
        self.pos = 0
        self.eof_line = eof_line
        self.eof_col = eof_col
        self.seen = {}

    # -- 基础工具 ------------------------------------------------------
    def _peek(self):
        if self.pos < self.n:
            return self.toks[self.pos]
        return None

    def _advance(self):
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def _here(self, tok):
        if tok is None:
            # EOF：错误位置指向上一个 token 之后的一列，没有 token 时为 (1,1)
            if self.pos > 0:
                last = self.toks[self.pos - 1]
                return last[2], last[3] + len(str(last[1]))
            return 1, 1
        return tok[2], tok[3]

    def _expect_punct(self, mark):
        tok = self._peek()
        if tok is None or tok[0] != "punct" or tok[1] != mark:
            line, col = self._here(tok)
            raise GlslParseError("expected %r" % mark, line, col)
        return self._advance()

    # -- 语法部件 ------------------------------------------------------
    def _parse_layout(self):
        # 当前 token 为 layout 关键字
        self._advance()
        tok = self._peek()
        line, col = self._here(tok)
        if tok is None or tok[0] != "punct" or tok[1] != "(":
            raise GlslParseError("layout qualifier requires '('", line, col)
        self._advance()
        layout = {}
        while True:
            tok = self._peek()
            if tok is None:
                raise GlslParseError(
                    "unterminated layout qualifier", *self._here(tok)
                )
            if tok[0] == "punct" and tok[1] == ")":
                self._advance()
                break
            if tok[0] != "id":
                raise GlslParseError(
                    "invalid layout qualifier", *self._here(tok)
                )
            key = self._advance()[1]
            value = None
            nxt = self._peek()
            if nxt is not None and nxt[0] == "punct" and nxt[1] == "=":
                self._advance()
                vtok = self._peek()
                if vtok is None or vtok[0] not in ("int", "id"):
                    raise GlslParseError(
                        "invalid layout value", *self._here(vtok)
                    )
                value = self._advance()[1]
            layout[key] = value
            nxt = self._peek()
            if nxt is not None and nxt[0] == "punct" and nxt[1] == ",":
                self._advance()
                continue
            self._expect_punct(")")
            break
        return layout

    def _parse_array_dims(self):
        dims = []
        while True:
            tok = self._peek()
            if tok is None or tok[0] != "punct" or tok[1] != "[":
                break
            lbracket = self._advance()
            inner = self._peek()
            if inner is not None and inner[0] == "punct" and inner[1] == "]":
                # 未指定大小的数组：float arr[]
                self._advance()
                dims.append(None)
                continue
            if inner is None or inner[0] not in ("int", "id"):
                raise GlslParseError(
                    "invalid array dimension", *self._here(inner)
                )
            dim = self._advance()[1]
            close = self._peek()
            if close is None or close[0] != "punct" or close[1] != "]":
                raise GlslParseError(
                    "expected ']' for array dimension", *self._here(close)
                )
            self._advance()
            dims.append(dim)
            del lbracket
        if not dims:
            return None
        if len(dims) == 1:
            return dims[0]
        return dims

    def _parse_declarators(self, storage, dtype, layout, precision):
        decls = []
        while True:
            tok = self._peek()
            if tok is None or tok[0] != "id":
                line, col = self._here(tok)
                raise GlslParseError("expected declaration name", line, col)
            name_tok = self._advance()
            name = name_tok[1]
            if name in self.seen:
                first = self.seen[name]
                raise DuplicateDeclarationError(
                    "duplicate declaration of %r (first at line %d)"
                    % (name, first),
                    name_tok[2],
                    name_tok[3],
                )
            self.seen[name] = name_tok[2]
            dims = self._parse_array_dims()
            decls.append(
                {
                    "name": name,
                    "type": dtype,
                    "storage": storage,
                    "line": name_tok[2],
                    "col": name_tok[3],
                    "array": dims,
                    "layout": layout,
                    "precision": precision,
                }
            )
            tok = self._peek()
            if tok is not None and tok[0] == "punct" and tok[1] == ",":
                self._advance()
                continue
            if tok is not None and tok[0] == "punct" and tok[1] == ";":
                self._advance()
                return decls
            line, col = self._here(tok)
            raise MissingSemicolonError(
                "missing ';' after declaration of %r" % name, line, col
            )

    def parse(self):
        decls = []
        while self.pos < self.n:
            tok = self._peek()
            if tok[0] != "id":
                raise GlslParseError(
                    "unexpected token %r" % tok[1], tok[2], tok[3]
                )
            word = tok[1]

            # layout(...) 限定符
            layout = None
            if word == "layout":
                layout = self._parse_layout()
                tok = self._peek()
                if tok is None or tok[0] != "id":
                    raise GlslParseError(
                        "declaration expected after layout qualifier",
                        *self._here(tok)
                    )
                word = tok[1]

            # 前置精度限定符：highp uniform ...
            precision = None
            if word in _PRECISION:
                precision = word
                self._advance()
                tok = self._peek()
                if tok is None or tok[0] != "id":
                    raise GlslParseError(
                        "storage qualifier expected after precision",
                        *self._here(tok)
                    )
                word = tok[1]

            # 全局精度语句：precision highp float;
            if word == "precision":
                self._advance()
                ptok = self._peek()
                if ptok is None or ptok[0] != "id" or ptok[1] not in _PRECISION:
                    raise GlslParseError(
                        "precision qualifier expected", *self._here(ptok)
                    )
                self._advance()
                ttok = self._peek()
                if (
                    ttok is None
                    or ttok[0] != "id"
                    or ttok[1] not in TYPES
                ):
                    raise InvalidTypeError(
                        "invalid type in precision statement",
                        *self._here(ttok)
                    )
                self._advance()
                semi = self._peek()
                if semi is None or semi[1] != ";":
                    raise MissingSemicolonError(
                        "missing ';' after precision statement",
                        *self._here(semi)
                    )
                self._advance()
                continue

            if word not in _STORAGE:
                raise GlslParseError(
                    "expected storage qualifier uniform/in/out, got %r" % word,
                    tok[2],
                    tok[3],
                )
            storage = word
            self._advance()

            # storage 与 type 之间的精度限定符
            tok = self._peek()
            if tok is not None and tok[0] == "id" and tok[1] in _PRECISION:
                precision = tok[1]
                self._advance()
                tok = self._peek()

            if tok is None or tok[0] != "id":
                raise InvalidTypeError(
                    "type expected after %r" % storage, *self._here(tok)
                )
            if tok[1] not in TYPES:
                raise InvalidTypeError(
                    "invalid type %r" % tok[1], tok[2], tok[3]
                )
            dtype = self._advance()[1]

            decls.extend(
                self._parse_declarators(storage, dtype, layout, precision)
            )
        return decls


class GlslParse:
    """GLSL 声明解析器。无实例可变状态，可跨线程共享。"""

    def parse(self, src):
        """解析 GLSL 源码，返回声明 dict 列表。

        非法输入抛出 :class:`GlslParseError` 的子类（同时是 ``ValueError``），
        异常对象带 ``line`` / ``col`` / ``code`` 属性。
        """
        if not isinstance(src, str):
            raise InvalidInputError(
                "GLSL source must be str, got %s" % type(src).__name__
            )
        cleaned = _STRIP_RE.sub(_blank_out, src)
        if "/*" in cleaned:
            line, col = _locate(_line_starts(cleaned), cleaned.index("/*"))
            raise GlslParseError("unterminated block comment", line, col)
        tokens, eof_line, eof_col = _tokenize(cleaned)
        return _Parser(tokens, eof_line, eof_col).parse()
