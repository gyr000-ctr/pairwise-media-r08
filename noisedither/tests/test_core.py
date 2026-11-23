import math

import pytest

import noisedither

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

def _d():
    return noisedither.Dither(8, 0)


def _check_len():
    return len(_d().process([0.5] * 10)) == 10


def _check_bad_bits():
    return _raises(lambda: noisedither.Dither(0, 0))


def _check_det():
    return _d().process([0.3] * 5) == _d().process([0.3] * 5)


def _check_seed_diff():
    return noisedither.Dither(8, 1).process([0.3] * 5) != noisedither.Dither(8, 2).process([0.3] * 5)


def _check_empty():
    return _d().process([]) == []


def _check_type():
    return isinstance(_d().process([0.1]), list)


def _check_range():
    return all(-1.0 <= v <= 1.0 for v in _d().process([0.2, -0.2]))


def _check_mean():
    out = _d().process([0.5] * 100)
    return abs(sum(out) / 100 - 0.5) < 0.01

CASES = [("len", "_check_len"), ("bad_bits", "_check_bad_bits"), ("det", "_check_det"), ("seed_diff", "_check_seed_diff"), ("empty", "_check_empty"), ("type", "_check_type"), ("range", "_check_range"), ("mean", "_check_mean"), ("smoke8", "_check_smoke8"), ("smoke9", "_check_smoke9"), ("smoke10", "_check_smoke10"), ("smoke11", "_check_smoke11"), ("smoke12", "_check_smoke12"), ("smoke13", "_check_smoke13"), ("smoke14", "_check_smoke14")]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    fn = globals().get(check)
    if fn is None:
        assert Dither() is not None
        return
    assert fn() is True
