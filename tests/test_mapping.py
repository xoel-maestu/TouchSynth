import math

import pytest

from touchsynth.mapping import map_intensity

XS = [i / 20 for i in range(21)]


def test_endpoints_of_cutoff_and_gain():
    lo, hi = map_intensity(0.0), map_intensity(1.0)
    assert lo.cutoff_hz == pytest.approx(150.0)
    assert hi.cutoff_hz == pytest.approx(4000.0)
    assert lo.gain_db == pytest.approx(-24.0)
    assert hi.gain_db == pytest.approx(0.0)


def test_cutoff_is_exponential():
    mid = map_intensity(0.5).cutoff_hz
    assert mid == pytest.approx(math.sqrt(150.0 * 4000.0))


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


def test_bloom_brightens_up_to_one_octave():
    base = map_intensity(0.5).cutoff_hz
    assert map_intensity(0.5, bloom=1.0).cutoff_hz == pytest.approx(2 * base)


def test_input_is_clamped():
    assert map_intensity(-1.0) == map_intensity(0.0)
    assert map_intensity(2.0) == map_intensity(1.0)
