import math

import pytest

from touchsynth.gestures import GestureTracker

RATE = 50.0
DT = 1 / RATE


def run(tracker, xs, t0=0.0, touched=True):
    t = t0
    for x in xs:
        t += DT
        tracker.update(x, touched, t)
    return t


def rest(tracker, seconds, t0=0.0):
    return run(tracker, [0.0] * int(seconds * RATE), t0, touched=False)


def test_slap_has_high_strike_and_slow_press_low():
    slap, press = GestureTracker(RATE), GestureTracker(RATE)
    run(slap, [0.8] * 5, rest(slap, 0.5))
    run(press, [0.8 * i / 50 for i in range(1, 51)], rest(press, 0.5))
    assert slap.strike > 0.9
    assert press.strike < 0.1


def test_strike_is_known_from_the_first_reading():
    g = GestureTracker(RATE)
    run(g, [0.7], rest(g, 0.5))
    assert g.strike > 0.9


def test_onset_and_release_are_reported_with_times():
    g = GestureTracker(RATE)
    t = rest(g, 0.5)
    t = run(g, [0.6] * 10, t)
    assert g.touched and g.onset_time == pytest.approx(0.5 + DT)
    run(g, [0.0], t, touched=False)
    assert not g.touched and g.release_time == pytest.approx(t + DT)


def test_fast_lift_has_short_fall_time_and_slow_lift_long():
    fast, slow = GestureTracker(RATE), GestureTracker(RATE)
    for g, tail in ((fast, []), (slow, [0.8 - 0.06 * i for i in range(1, 13)])):
        t = run(g, [0.8] * 50, rest(g, 0.5))
        t = run(g, tail, t)
        run(g, [0.0], t, touched=False)
    assert fast.fall_time < 0.05
    assert slow.fall_time > 0.15


def test_press_ignores_slow_drift_but_follows_squeezes():
    g = GestureTracker(RATE)
    t = rest(g, 0.5)
    t = run(g, [0.3 + 0.3 * i / 750 for i in range(750)], t)  # sweat drift: +0.3 over 15 s
    assert abs(g.press) < 0.1
    run(g, [0.6 + 0.25] * 10, t)  # a squeeze
    assert g.press > 0.15


def test_tremor_is_zero_when_steady_and_rises_with_shaking():
    steady, shaking = GestureTracker(RATE), GestureTracker(RATE)
    run(steady, [0.5] * 100, rest(steady, 0.5))
    run(shaking, [0.5 + 0.05 * math.sin(2 * math.pi * 6 * i / RATE) for i in range(100)],
        rest(shaking, 0.5))
    assert steady.tremor == pytest.approx(0.0, abs=0.02)
    assert shaking.tremor > 0.5


def test_hold_time_counts_while_touching():
    g = GestureTracker(RATE)
    run(g, [0.5] * 150, rest(g, 0.5))
    assert g.hold_s == pytest.approx(3.0, abs=0.05)
