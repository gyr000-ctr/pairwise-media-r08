"""Acceptance tests for dither + second-order noise shaping.

These tests cover the constraints that the provided ``tests/test_core.py``
suite does not exercise: the spectral shaping requirement, the fixed
performance budget, filter stability, error classification and thread safety.
They are named ``test_dither_*`` so that ``pytest -k dither`` (the command in
the project README) selects them.
"""

import math
import threading
import time

import pytest

import noisedither
from noisedither import (
    Dither,
    DitherTypeError,
    InvalidBitsError,
    InvalidOrderError,
    NonFiniteSampleError,
)

N_FFT = 2048
LOW_BINS = [0.025 + i * 0.0125 for i in range(7)]    # 0.025 .. 0.100
HIGH_BINS = [0.400 + i * 0.0125 for i in range(9)]   # 0.400 .. 0.500


def _band_power(signal, freqs):
    """Sum of normalised DFT power over *freqs* in cycles/sample."""
    n = len(signal)
    twopi = 2.0 * math.pi
    total = 0.0
    for f in freqs:
        step = twopi * f
        re = 0.0
        im = 0.0
        for k, value in enumerate(signal):
            angle = step * k
            re += value * math.cos(angle)
            im -= value * math.sin(angle)
        total += (re * re + im * im) / (n * n)
    return total


def test_dither_second_order_shapes_noise_away_from_low_frequencies():
    dc = 0.37
    out = Dither(8, seed=1234).process([dc] * N_FFT)
    error = [value - dc for value in out]

    low = _band_power(error, LOW_BINS)
    high = _band_power(error, HIGH_BINS)
    assert low > 0.0 and high > 0.0
    drop_db = 10.0 * math.log10(low / high)
    # Second-order shaping must push the low band at least 6 dB below the
    # high band.  The implementation achieves about 26 dB.
    assert drop_db <= -6.0, f"low-frequency noise drop is only {drop_db:.2f} dB"


def test_dither_second_order_beats_first_order_in_low_band():
    dc = 0.37
    signal = [dc] * N_FFT
    first = _band_power([v - dc for v in Dither(8, seed=5, order=1).process(signal)], LOW_BINS)
    second = _band_power([v - dc for v in Dither(8, seed=5, order=2).process(signal)], LOW_BINS)
    assert second < first


def test_dither_preserves_mean_within_tolerance():
    for bits in (8, 16):
        for samples in (
            [0.5] * 2000,
            [0.37] * 1000,
            [0.999] * 1000,
            [1.0] * 1000,
            [-1.0] * 1000,
            [0.5, 0.17, -0.9, 0.25] * 500,
        ):
            out = Dither(bits, seed=7).process(samples)
            mean_error = abs(sum(out) / len(out) - sum(samples) / len(samples))
            assert mean_error <= 1e-3, (
                f"bits={bits} mean error {mean_error:.3e} for DC {samples[0]}"
            )


def test_dither_is_reproducible_and_seed_sensitive():
    samples = [0.3] * 257
    assert Dither(10, seed=99).process(samples) == Dither(10, seed=99).process(samples)
    assert Dither(10, seed=100).process(samples) != Dither(10, seed=101).process(samples)


def test_dither_stability_is_verified_and_loop_stays_bounded():
    assert noisedither.verify_stability(1) is True
    assert noisedither.verify_stability(2) is True
    assert noisedither.verify_stability(0) is False
    assert noisedither.verify_stability(3) is False

    dither = Dither(8, seed=0)
    assert dither.is_stable() is True
    for signal in (
        [1.0] * 2000,
        [-1.0] * 2000,
        [1.0, -1.0] * 1000,
        [0.999999] * 2000,
        [1e9] * 10,
    ):
        out = dither.process(signal)
        assert all(math.isfinite(v) and -1.0 <= v <= 1.0 for v in out)


def test_dither_error_kinds_are_distinguishable():
    with pytest.raises(InvalidBitsError):
        Dither(0)
    with pytest.raises(InvalidBitsError):
        Dither(33)
    with pytest.raises(InvalidOrderError):
        Dither(8, order=0)
    with pytest.raises(InvalidOrderError):
        Dither(8, order=3)

    assert not issubclass(InvalidBitsError, InvalidOrderError)
    assert not issubclass(InvalidOrderError, InvalidBitsError)
    for cls in (InvalidBitsError, InvalidOrderError, NonFiniteSampleError):
        assert issubclass(cls, ValueError)

    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(NonFiniteSampleError):
            Dither(8).process([0.1, value])

    for bad_bits in ("8", 8.0, None):
        with pytest.raises((TypeError, ValueError)):
            Dither(bad_bits)
    for bad_samples in (None, 3.0, "abc", [[0.5]], [1 + 2j]):
        with pytest.raises((TypeError, ValueError)):
            Dither(8).process(bad_samples)


def test_dither_processing_contract():
    dither = Dither(8, seed=3)
    assert dither.process([]) == []
    out = dither.process([0.1])
    assert isinstance(out, list) and all(isinstance(v, float) for v in out)

    data = [0.1, -0.2, 0.3]
    snapshot = list(data)
    dither.process(data)
    assert data == snapshot, "process() must not mutate its input"

    # Out-of-range material is clamped to the representable range.
    assert all(-1.0 <= v <= 1.0 for v in dither.process([2.5, -2.5, 0.0]))
    assert dither.process((0.5, 0.5)) == dither.process([0.5, 0.5])


def test_dither_one_million_samples_under_400_ms():
    samples = [((i * 2654435761) % 1000003) / 1000003.0 * 2.0 - 1.0 for i in range(1_000_000)]
    start = time.perf_counter()
    out = Dither(8, seed=0).process(samples)
    elapsed = time.perf_counter() - start
    assert len(out) == 1_000_000
    assert elapsed <= 0.400, f"1M samples took {elapsed * 1000:.1f} ms"


def test_dither_concurrent_calls_are_isolated():
    samples = [((i * 37) % 101) / 101.0 * 2.0 - 1.0 for i in range(2000)]
    reference = Dither(8, seed=5).process(samples)
    shared = Dither(8, seed=5)
    results = []
    lock = threading.Lock()

    def worker(dither):
        result = dither.process(samples)
        with lock:
            results.append(result)

    threads = [
        threading.Thread(target=worker, args=(shared if i % 2 else Dither(8, seed=5),))
        for i in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 8
    assert all(result == reference for result in results)
