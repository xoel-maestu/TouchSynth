import pytest

from touchsynth.controller import TouchController
from touchsynth.mapping import map_intensity

RATE = 50.0


def play(ctrl, intensity, touched, seconds, t0=0.0):
    t = t0
    for _ in range(int(seconds * RATE)):
        t += 1 / RATE
        ctrl.update(intensity, touched, t)
    return t


def test_silent_until_touched():
    ctrl = TouchController(RATE)
    t = play(ctrl, 0.0, False, 1.0)
    _, gate = ctrl.current(t)
    assert gate == 0.0


def test_touch_opens_gate_quickly():
    ctrl = TouchController(RATE)
    t = play(ctrl, 0.6, True, 0.2)
    _, gate = ctrl.current(t)
    assert gate > 0.9


def test_release_fades_slowly_and_keeps_timbre():
    ctrl = TouchController(RATE)
    t = play(ctrl, 0.8, True, 1.0)
    params_touching, _ = ctrl.current(t)
    t = play(ctrl, 0.0, False, 0.5, t)
    params, gate = ctrl.current(t)
    assert 0.5 < gate < 0.95  # still sounding half a second later
    assert params.cutoff_hz == pytest.approx(params_touching.cutoff_hz, rel=0.05)


def test_intensity_changes_follow_within_a_fraction_of_a_second():
    ctrl = TouchController(RATE)
    t = play(ctrl, 0.2, True, 1.0)
    t = play(ctrl, 0.8, True, 0.5, t)
    params, _ = ctrl.current(t + 1.0)  # well after any onset bloom has decayed
    assert params.cutoff_hz == pytest.approx(map_intensity(0.8).cutoff_hz, rel=0.1)
    t = play(ctrl, 0.2, True, 1.0, t)
    params, _ = ctrl.current(t)
    assert params.cutoff_hz == pytest.approx(map_intensity(0.2).cutoff_hz, rel=0.1)


def test_fast_onset_blooms_and_slow_onset_does_not():
    slap, press = TouchController(RATE), TouchController(RATE)
    t_slap = play(slap, 0.9, True, 0.06)
    t_press = 0.0
    for i in range(100):  # 2 s ramp to the same level
        t_press += 1 / RATE
        press.update(0.9 * i / 99, True, t_press)
    bright_slap = slap.current(t_slap)[0].cutoff_hz / map_intensity(slap.intensity).cutoff_hz
    bright_press = press.current(t_press)[0].cutoff_hz / map_intensity(press.intensity).cutoff_hz
    assert bright_slap > 1.4
    assert bright_press == pytest.approx(1.0, abs=0.05)


def test_bloom_decays():
    ctrl = TouchController(RATE)
    t = play(ctrl, 0.9, True, 0.06)
    params, _ = ctrl.current(t + 2.0)
    assert params.cutoff_hz == pytest.approx(map_intensity(ctrl.intensity).cutoff_hz, rel=0.02)


def test_gate_fades_out_when_readings_stop_mid_touch():
    ctrl = TouchController(RATE)
    t = play(ctrl, 0.8, True, 1.0)  # then the cable is pulled: no more updates
    assert ctrl.current(t + 0.1)[1] > 0.9
    assert ctrl.current(t + 5.0)[1] < 0.2
