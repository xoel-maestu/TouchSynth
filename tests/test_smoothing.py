import math

from touchsynth.smoothing import OneEuroFilter

RATE = 150.0


def test_one_euro_converges_to_constant_input():
    f = OneEuroFilter(rate_hz=RATE)
    for _ in range(600):
        y = f(0.7)
    assert math.isclose(y, 0.7, abs_tol=1e-3)


def test_one_euro_reduces_jitter():
    f = OneEuroFilter(rate_hz=RATE, mincutoff=1.0, beta=0.0)
    outputs = [f(0.5 + (0.05 if i % 2 else -0.05)) for i in range(600)]
    tail = outputs[-100:]
    assert max(tail) - min(tail) < 0.01


def test_one_euro_tracks_fast_moves_better_with_beta():
    slow = OneEuroFilter(rate_hz=RATE, mincutoff=1.0, beta=0.0)
    fast = OneEuroFilter(rate_hz=RATE, mincutoff=1.0, beta=5.0)
    for _ in range(50):
        slow(0.0)
        fast(0.0)
    for _ in range(10):
        ys, yf = slow(1.0), fast(1.0)
    assert yf > ys


def test_one_euro_exposes_derivative():
    f = OneEuroFilter(rate_hz=RATE)
    for i in range(300):
        f(i / RATE)  # ramp of 1 unit per second
    assert math.isclose(f.derivative, 1.0, rel_tol=0.1)

