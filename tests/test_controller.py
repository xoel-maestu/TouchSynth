import pytest

from touchsynth.controller import TouchController
from touchsynth.mapping import map_intensity

RATE = 50.0
DT = 1 / RATE


def play(ctrl, xs, t=0.0, touched=True):
    for x in xs:
        t += DT
        ctrl.update(x, touched, t)
    return t


def rest(ctrl, seconds, t=0.0):
    return play(ctrl, [0.0] * int(seconds * RATE), t, touched=False)


def gate(ctrl, t):
    return ctrl.current(t)[1]


def test_silent_until_touched():
    ctrl = TouchController(RATE)
    assert gate(ctrl, rest(ctrl, 1.0)) == 0.0


def test_a_slap_sounds_at_once_and_a_slow_touch_swells():
    slap, slow = TouchController(RATE), TouchController(RATE)
    t = play(slap, [0.8], rest(slap, 0.5))
    assert gate(slap, t + 0.02) > 0.9
    t = play(slow, [0.03, 0.06], rest(slow, 0.5))
    assert gate(slow, t) < 0.5


@pytest.mark.parametrize("start, end", [(0.2, 0.8), (0.8, 0.2)])
def test_level_follows_pressure_changes_within_60_ms(start, end):
    ctrl = TouchController(RATE)
    t = play(ctrl, [start] * 100, rest(ctrl, 0.5))
    play(ctrl, [end] * 3, t)  # 60 ms
    assert abs(ctrl.intensity - end) < 0.1 * abs(end - start)


def lift(tail):
    ctrl = TouchController(RATE)
    t = play(ctrl, [0.8] * 100, rest(ctrl, 0.5))
    t = play(ctrl, tail, t)
    return ctrl, play(ctrl, [0.0], t, touched=False)


def test_fast_lift_cuts_short_and_slow_lift_rings_on():
    fast, t_fast = lift([])
    slow, t_slow = lift([0.8 - 0.03 * i for i in range(1, 26)])  # 0.5 s fade out
    assert gate(fast, t_fast + 0.8) < 0.2
    assert gate(slow, t_slow + 0.8) > 0.5


def test_release_keeps_the_timbre():
    ctrl, t = lift([])
    touching = map_intensity(0.8).cutoff_hz
    assert ctrl.current(t + 0.3)[0].cutoff_hz == pytest.approx(touching, rel=0.1)


def test_fast_lift_throws_the_sound_into_the_reverb():
    fast, t = lift([])
    assert fast.current(t + 0.05)[0].reverb_wet > map_intensity(0.8).reverb_wet + 0.2
    assert fast.current(t + 3.0)[0].reverb_wet == pytest.approx(map_intensity(0.8).reverb_wet, abs=0.02)


def test_slap_blooms_and_bursts_but_slow_touch_does_not():
    slap, slow = TouchController(RATE), TouchController(RATE)
    t_slap = play(slap, [0.8] * 3, rest(slap, 0.5))
    t_slow = play(slow, [0.8 * i / 99 for i in range(100)], rest(slow, 0.5))
    p_slap, p_slow = slap.current(t_slap), slow.current(t_slow)
    assert p_slap[0].cutoff_hz > 1.4 * map_intensity(slap.intensity).cutoff_hz
    assert p_slap[0].noise_gain > 0.05
    assert p_slow[0].cutoff_hz == pytest.approx(map_intensity(slow.intensity).cutoff_hz, rel=0.05)
    assert p_slow[0].noise_gain < 0.01


def test_strike_effects_decay():
    ctrl = TouchController(RATE)
    t = play(ctrl, [0.8] * 3, rest(ctrl, 0.5))
    params, _ = ctrl.current(t + 1.5)
    assert params.noise_gain < 0.001
    assert params.cutoff_hz == pytest.approx(map_intensity(ctrl.intensity).cutoff_hz, rel=0.02)


def test_shaking_adds_vibrato_and_holding_adds_shimmer():
    import math
    ctrl = TouchController(RATE)
    t = play(ctrl, [0.6] * 50 * 10, rest(ctrl, 0.5))  # 10 s steady hold
    steady = ctrl.current(t)[0]
    t = play(ctrl, [0.6 + 0.05 * math.sin(2 * math.pi * 6 * i / RATE) for i in range(50)], t)
    shaking = ctrl.current(t)[0]
    assert steady.vibrato_cents < 1.0
    assert shaking.vibrato_cents > 8.0
    assert steady.shimmer_gain > 0.2


def test_gate_fades_out_when_readings_stop_mid_touch():
    ctrl = TouchController(RATE)
    t = play(ctrl, [0.8] * 50, rest(ctrl, 0.5))  # then the cable is pulled
    assert gate(ctrl, t + 0.1) > 0.9
    assert gate(ctrl, t + 5.0) < 0.2


def test_each_touch_moves_the_timbre():
    from tests.test_variation import circular
    ctrl = TouchController(RATE, seed=1)
    t = rest(ctrl, 0.5)
    before = ctrl.current(t)[0].timbre
    t = play(ctrl, [0.8] * 100, t)  # a slap, held 2 s
    assert circular(ctrl.current(t)[0].timbre, before) > 0.5


def test_retouching_plays_a_new_note_but_a_contact_glitch_does_not():
    ctrl = TouchController(RATE, seed=2)
    t = play(ctrl, [0.6] * 50, rest(ctrl, 0.5))
    first = ctrl.current(t)[0].root_hz
    t = play(ctrl, [0.6] * 50, rest(ctrl, 0.06, t))  # 60 ms dropout of the pins
    assert ctrl.current(t)[0].root_hz == pytest.approx(first, rel=1e-6)
    t = play(ctrl, [0.6] * 50, rest(ctrl, 0.5, t))   # a real re-touch
    assert ctrl.current(t)[0].root_hz != pytest.approx(first, rel=1e-3)


def test_gate_recovers_smoothly_when_readings_resume():
    ctrl = TouchController(RATE)
    t = play(ctrl, [0.8] * 50, rest(ctrl, 0.5))
    t += 1.0                                   # readings stall for 1 s mid-touch
    dipped = gate(ctrl, t)
    play(ctrl, [0.8], t)
    assert gate(ctrl, t + 0.011) < dipped + 0.5 * (1 - dipped)


def test_a_touch_right_at_startup_counts():
    from tests.test_variation import circular
    touched, untouched = TouchController(RATE, seed=3), TouchController(RATE, seed=3)
    for ctrl in (touched, untouched):
        rest(ctrl, 0.04)                       # two idle readings after boot...
    play(touched, [0.9] * 60, 0.04)            # ...then a touch at t = 0.06 s
    assert circular(touched.current(1.2)[0].timbre, untouched.current(1.2)[0].timbre) > 0.2
