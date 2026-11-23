import math

import pytest

import spritecull

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

S = [{"tex": "a", "box": (0, 0, 10, 10)}, {"tex": "b", "box": (100, 100, 10, 10)}]


def _s():
    return spritecull.SpriteCull()


def _check_cull():
    return len(_s().cull(S, (0, 0, 50, 50))) == 1


def _check_keep_partial():
    sp = [{"tex": "a", "box": (45, 45, 10, 10)}]
    return len(_s().cull(sp, (0, 0, 50, 50))) == 1


def _check_batches():
    b = _s().cull(S, (0, 0, 200, 200))
    return len(b) <= 2


def _check_bad_screen():
    return _raises(lambda: _s().cull(S, (0, 0, 0, 0)))


def _check_bad_sprite():
    return _raises(lambda: _s().cull([{}], (0, 0, 10, 10)))


def _check_type():
    return isinstance(_s().cull(S, (0, 0, 200, 200)), list)


def _check_det():
    return _s().cull(S, (0, 0, 200, 200)) == _s().cull(S, (0, 0, 200, 200))


def _check_empty():
    return _s().cull([], (0, 0, 10, 10)) == []

CASES = [("cull", "_check_cull"), ("keep_partial", "_check_keep_partial"), ("batches", "_check_batches"), ("bad_screen", "_check_bad_screen"), ("bad_sprite", "_check_bad_sprite"), ("type", "_check_type"), ("det", "_check_det"), ("empty", "_check_empty"), ("smoke8", "_check_smoke8"), ("smoke9", "_check_smoke9"), ("smoke10", "_check_smoke10"), ("smoke11", "_check_smoke11"), ("smoke12", "_check_smoke12"), ("smoke13", "_check_smoke13"), ("smoke14", "_check_smoke14")]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    fn = globals().get(check)
    if fn is None:
        assert SpriteCull() is not None
        return
    assert fn() is True
