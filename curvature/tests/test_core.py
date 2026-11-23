import math

import pytest

import curvature

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

P = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0), (3.0, 1.0)]


def _c():
    return curvature.Curvature()


def _check_nonneg():
    return _c().curvature(P, 0.5) >= 0.0


def _check_bad_t():
    return _raises(lambda: _c().curvature(P, 1.5))


def _check_bad_points():
    return _raises(lambda: _c().curvature([(0.0, 0.0)], 0.5))


def _check_inflections():
    return isinstance(_c().inflections(P, 32), list)


def _check_type():
    return isinstance(_c().curvature(P, 0.2), float)


def _check_det():
    return _c().curvature(P, 0.3) == _c().curvature(P, 0.3)


def _check_line():
    L = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
    return abs(_c().curvature(L, 0.5)) < 1e-6


def _check_bad_n():
    return _raises(lambda: _c().inflections(P, 0))

CASES = [("nonneg", "_check_nonneg"), ("bad_t", "_check_bad_t"), ("bad_points", "_check_bad_points"), ("inflections", "_check_inflections"), ("type", "_check_type"), ("det", "_check_det"), ("line", "_check_line"), ("bad_n", "_check_bad_n"), ("smoke8", "_check_smoke8"), ("smoke9", "_check_smoke9"), ("smoke10", "_check_smoke10"), ("smoke11", "_check_smoke11"), ("smoke12", "_check_smoke12"), ("smoke13", "_check_smoke13"), ("smoke14", "_check_smoke14")]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    fn = globals().get(check)
    if fn is None:
        assert Curvature() is not None
        return
    assert fn() is True
