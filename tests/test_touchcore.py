import math

import pytest

from touchcore import FULL_SCALE, TouchSensor, conductance_us

R_PULLUP = 1_000_000
R_SERIES = 100_000


def raw_for(skin_ohms):
    """ADC reading produced by a given skin-path resistance (divider model)."""
    if math.isinf(skin_ohms):
        return FULL_SCALE
    rx = skin_ohms + R_SERIES
    return round(FULL_SCALE * rx / (R_PULLUP + rx))


def make_sensor():
    return TouchSensor(r_pullup=R_PULLUP, r_series=R_SERIES)


def feed(sensor, skin_ohms, windows):
    for _ in range(windows):
        result = sensor.update(raw_for(skin_ohms))
    return result


def test_conductance_inverts_the_divider():
    assert conductance_us(raw_for(1_000_000), R_PULLUP, R_SERIES) == pytest.approx(1.0, rel=1e-3)


def test_open_circuit_has_zero_conductance():
    assert conductance_us(FULL_SCALE, R_PULLUP, R_SERIES) == 0.0


def test_short_circuit_is_finite():
    assert math.isfinite(conductance_us(0, R_PULLUP, R_SERIES))


def test_untouched_reads_zero_intensity_and_no_touch():
    _, intensity, touched = feed(make_sensor(), math.inf, 10)
    assert intensity == 0.0
    assert touched is False


def test_firm_touch_reads_higher_than_light_touch():
    s = make_sensor()
    _, light, touched = feed(s, 5_000_000, 5)
    _, firm, _ = feed(s, 100_000, 5)
    assert touched is True
    assert firm > light + 0.5


def test_intensity_is_logarithmic_in_conductance():
    s = make_sensor()
    _, a, _ = feed(s, 4_000_000, 5)
    _, b, _ = feed(s, 1_000_000, 5)
    _, c, _ = feed(s, 250_000, 5)
    assert (b - a) == pytest.approx(c - b, abs=0.02)  # equal ratios -> equal steps


def test_touch_needs_consecutive_windows_to_switch_on():
    s = make_sensor()
    feed(s, math.inf, 5)
    _, _, touched = s.update(raw_for(1_000_000))
    assert touched is False
    _, _, touched = s.update(raw_for(1_000_000))
    assert touched is True


def test_hysteresis_keeps_touch_between_thresholds():
    s = make_sensor()
    feed(s, 1_000_000, 5)
    _, _, touched = feed(s, 12_000_000, 5)  # between on (10 MΩ) and off (15 MΩ)
    assert touched is True
    _, _, touched = feed(s, 30_000_000, 5)
    assert touched is False


def test_steady_light_touch_stays_light():
    s = make_sensor()
    _, early, _ = feed(s, 1_000_000, 50)
    _, late, _ = feed(s, 1_000_000, 50 * 120)  # two minutes later
    assert late == pytest.approx(early, abs=0.02)
    assert late < 0.75


def test_single_spike_does_not_shrink_later_readings():
    s = make_sensor()
    _, before, _ = feed(s, 100_000, 10)
    feed(s, 2_000, 1)  # sweat / electrodes shorting for one window
    _, after, _ = feed(s, 100_000, 10)
    assert after == pytest.approx(before, abs=0.03)


def test_range_expands_for_sustained_stronger_contact():
    s = make_sensor()
    _, before, _ = feed(s, 100_000, 5)
    feed(s, 20_000, 50 * 10)  # ten seconds of much better contact
    _, after, _ = feed(s, 100_000, 5)
    assert after < before - 0.1


def test_range_returns_to_seed_after_a_while():
    s = make_sensor()
    _, before, _ = feed(s, 100_000, 5)
    feed(s, 20_000, 50 * 10)
    feed(s, 100_000, 50 * 300)  # five minutes of normal play
    _, after, _ = feed(s, 100_000, 5)
    assert after == pytest.approx(before, abs=0.03)


def test_stronger_than_range_is_clamped_to_one():
    _, intensity, _ = feed(make_sensor(), 20_000, 3)
    assert intensity == 1.0


def test_sudden_release_to_open_circuit_does_not_crash():
    s = make_sensor()
    feed(s, 100_000, 5)
    _, intensity, touched = s.update(FULL_SCALE)  # still debouncing the release
    assert intensity == 0.0 and touched is True
    _, _, touched = s.update(FULL_SCALE)
    assert touched is False


def test_rejects_a_firm_level_below_the_touch_threshold():
    with pytest.raises(ValueError):
        TouchSensor(R_PULLUP, R_SERIES, g_max_us=0.05)
