import math

import pytest

from touchsynth.mapping import map_intensity

XS = [i / 20 for i in range(21)]


def test_endpoints_of_cutoff_and_gain():
    lo, hi = map_intensity(0.0), map_intensity(1.0)
    assert lo.cutoff_hz == pytest.approx(100.0)
    assert hi.cutoff_hz == pytest.approx(8000.0)
    assert lo.gain_db == pytest.approx(-30.0)
    assert hi.gain_db == pytest.approx(0.0)


def test_cutoff_is_exponential():
    mid = map_intensity(0.5).cutoff_hz
    assert mid == pytest.approx(math.sqrt(100.0 * 8000.0))


@pytest.mark.parametrize("field", ["cutoff_hz", "gain_db", "detune_cents",
                                   "fifth_gain", "octave_gain", "drive_db",
                                   "lfo_hz", "sub_gain"])
def test_parameters_rise_monotonically_with_intensity(field):
    values = [getattr(map_intensity(x), field) for x in XS]
    assert all(b >= a for a, b in zip(values, values[1:]))


def test_reverb_gets_drier_with_firm_touch():
    assert map_intensity(1.0).reverb_wet < map_intensity(0.0).reverb_wet


def test_layers_enter_progressively():
    assert map_intensity(0.2).fifth_gain == 0.0
    assert map_intensity(0.5).octave_gain == 0.0
    assert map_intensity(0.7).fifth_gain > 0.0
    assert map_intensity(1.0).octave_gain > 0.0


def test_light_and_firm_touch_sound_clearly_different():
    light, firm = map_intensity(0.2), map_intensity(0.8)
    assert firm.cutoff_hz / light.cutoff_hz > 4.0      # > 2 octaves brighter
    assert firm.gain_db - light.gain_db > 12.0         # clearly louder (plus layers)


def test_bloom_brightens_one_octave_but_never_into_the_harsh_band():
    base = map_intensity(0.3).cutoff_hz
    assert map_intensity(0.3, bloom=1.0).cutoff_hz == pytest.approx(2 * base)
    assert map_intensity(0.7, bloom=1.0).cutoff_hz <= max(3000.0, map_intensity(0.7).cutoff_hz)


def test_strikes_do_not_add_saturation():
    assert map_intensity(0.8, bloom=1.0).drive_db == map_intensity(0.8).drive_db


def test_tremor_adds_vibrato():
    assert map_intensity(0.5).vibrato_cents == 0.0
    assert map_intensity(0.5, tremor=1.0).vibrato_cents == pytest.approx(20.0)


def test_press_widens_and_detunes():
    flat, squeezed = map_intensity(0.5), map_intensity(0.5, press=0.25)
    assert squeezed.width > flat.width + 0.4
    assert squeezed.detune_cents > flat.detune_cents + 5


def test_long_holds_grow_a_shimmer_layer():
    assert map_intensity(0.7, hold_s=0.0).shimmer_gain == 0.0
    early = map_intensity(0.7, hold_s=2.0).shimmer_gain
    late = map_intensity(0.7, hold_s=20.0).shimmer_gain
    assert 0.0 < early < late


def test_strike_and_reverb_boost_pass_through_clamped():
    p = map_intensity(0.5, strike=0.6, strike_id=3, reverb_boost=2.0)
    assert (p.strike, p.strike_id) == (pytest.approx(0.6), 3)
    assert p.reverb_wet <= 0.9


def test_input_is_clamped():
    assert map_intensity(-1.0) == map_intensity(0.0)
    assert map_intensity(2.0) == map_intensity(1.0)
