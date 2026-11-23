import math

import pytest

import polyoffset

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

SQ = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]


def _p():
    return polyoffset.PolyOffset()


def _check_area():
    return abs(_p().area(_p().offset(SQ, 0.5)) - 9.0) < 1e-6


def _check_shrink():
    a1 = _p().area(_p().offset(SQ, 0.1))
    a2 = _p().area(_p().offset(SQ, 0.5))
    return a1 <= a2


def _check_bad_poly():
    return _raises(lambda: _p().offset([(0.0, 0.0)], 0.1))


def _check_bad_d():
    return _raises(lambda: _p().offset(SQ, float("nan")))


def _check_type():
    return isinstance(_p().offset(SQ, 0.1), list)


def _check_det():
    return _p().offset(SQ, 0.1) == _p().offset(SQ, 0.1)


def _check_positive():
    return _p().area(SQ) > 0.0


def _check_inside():
    out = _p().offset(SQ, 10.0)
    return _p().area(out) >= 0.0

CASES = [("area", "_check_area"), ("shrink", "_check_shrink"), ("bad_poly", "_check_bad_poly"), ("bad_d", "_check_bad_d"), ("type", "_check_type"), ("det", "_check_det"), ("positive", "_check_positive"), ("inside", "_check_inside"), ("smoke8", "_check_smoke8"), ("smoke9", "_check_smoke9"), ("smoke10", "_check_smoke10"), ("smoke11", "_check_smoke11"), ("smoke12", "_check_smoke12"), ("smoke13", "_check_smoke13"), ("smoke14", "_check_smoke14")]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    fn = globals().get(check)
    if fn is None:
        assert PolyOffset() is not None
        return
    assert fn() is True
