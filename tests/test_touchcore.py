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


def test_range_adapts_to_people_who_never_reach_the_seed_maximum():
    s = make_sensor()
    for _ in range(3000):  # ~60 s of touches that only reach 1 MΩ
        s.update(raw_for(1_000_000))
    _, intensity, _ = s.update(raw_for(1_000_000))
    assert intensity > 0.9


def test_range_expands_immediately_for_stronger_contact():
    s = make_sensor()
    _, intensity, _ = feed(s, 20_000, 3)  # far beyond the 100 kΩ seed
    assert intensity == pytest.approx(1.0)
    _, intensity, _ = feed(s, 100_000, 3)
    assert intensity < 1.0
