import math

import pytest
from touchcore import FULL_SCALE, TouchSensor, node_conductance_us

R_PULLUP = 1_000_000
R_SERIES = 100_000


def raw_for(skin_ohms, rest_ohms=math.inf):
    """ADC reading for the skin path (R_SERIES + skin) in parallel with a resting load
    to GND (on the real board: the ADC's own sampling load, ~15 MΩ)."""
    g = 0.0 if math.isinf(skin_ohms) else 1.0 / (skin_ohms + R_SERIES)
    g += 0.0 if math.isinf(rest_ohms) else 1.0 / rest_ohms
    if g == 0.0:
        return FULL_SCALE
    rx = 1.0 / g
    return round(FULL_SCALE * rx / (R_PULLUP + rx))


def make_sensor(rest_ohms=math.inf):
    """A sensor that has booted untouched (it learns its resting baseline then)."""
    sensor = TouchSensor(r_pullup=R_PULLUP, r_series=R_SERIES)
    for _ in range(5):
        sensor.update(raw_for(math.inf, rest_ohms))
    return sensor


def feed(sensor, skin_ohms, windows):
    for _ in range(windows):
        result = sensor.update(raw_for(skin_ohms))
    return result


def test_node_conductance_inverts_the_divider():
    raw = round(FULL_SCALE * 1e6 / (R_PULLUP + 1e6))
    assert node_conductance_us(raw, R_PULLUP) == pytest.approx(1.0, rel=1e-3)


def test_open_circuit_has_zero_conductance():
    assert node_conductance_us(FULL_SCALE, R_PULLUP) == 0.0


def test_short_circuit_is_finite():
    assert math.isfinite(node_conductance_us(0, R_PULLUP))


def test_reports_skin_conductance_without_the_series_resistor():
    g, _, _ = feed(make_sensor(), 1_000_000, 5)
    assert g == pytest.approx(1.0, rel=1e-2)


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


def test_touch_starts_on_the_first_window_but_needs_two_to_end():
    s = make_sensor()
    _, _, touched = s.update(raw_for(1_000_000))
    assert touched is True
    _, _, touched = s.update(raw_for(math.inf))
    assert touched is True
    _, _, touched = s.update(raw_for(math.inf))
    assert touched is False


def test_hysteresis_keeps_touch_between_thresholds():
    s = make_sensor()
    feed(s, 1_000_000, 5)
    _, _, touched = feed(s, 60_000_000, 5)  # between on (50 MΩ) and off (83 MΩ)
    assert touched is True
    _, _, touched = feed(s, 300_000_000, 5)
    assert touched is False


def test_very_light_touches_on_dry_skin_are_detected():
    _, _, touched = feed(make_sensor(), 30_000_000, 2)  # 0.033 µS: real dry-skin touch
    assert touched is True


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


def taps(sensor, skin_ohms, count):
    for _ in range(count):
        feed(sensor, skin_ohms, 10)     # 200 ms touch
        feed(sensor, math.inf, 10)      # 200 ms apart


def test_range_adapts_down_to_dry_skin():
    s = make_sensor()
    _, before, _ = feed(s, 12_000_000, 5)  # 0.08 µS: a typical touch late at night
    feed(s, math.inf, 5)
    taps(s, 12_000_000, 12)
    _, after, _ = feed(s, 12_000_000, 5)
    assert after > before + 0.2
    assert after > 0.6


def test_range_adapts_up_to_moist_skin():
    s = TouchSensor(r_pullup=R_PULLUP, r_series=R_SERIES, g_max_us=0.8)  # firmware setting
    feed(s, math.inf, 5)
    _, before, _ = feed(s, 1_250_000, 5)   # the default top: 0.8 µS
    feed(s, math.inf, 5)
    taps(s, 200_000, 12)                   # much better contact for a while
    _, after, _ = feed(s, 1_250_000, 5)
    assert after < before - 0.1


def test_lighter_and_firmer_than_usual_still_differ_after_adapting():
    s = make_sensor()
    taps(s, 12_000_000, 12)
    _, light, _ = feed(s, 40_000_000, 5)
    feed(s, math.inf, 5)
    _, firm, _ = feed(s, 6_000_000, 5)
    assert firm > light + 0.4


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
        TouchSensor(R_PULLUP, R_SERIES, g_max_us=0.015)


REST_LOAD = 15_000_000  # measured on the real board: ~0.067 µS with nobody touching


def test_resting_load_is_not_a_touch_and_reads_zero():
    s = make_sensor(REST_LOAD)
    for _ in range(100):
        g, intensity, touched = s.update(raw_for(math.inf, REST_LOAD))
    assert touched is False and intensity == 0.0
    assert g == pytest.approx(0.0, abs=0.005)


@pytest.mark.parametrize("skin", [10_000_000, 2_000_000, 500_000])
def test_touch_reads_the_same_with_or_without_resting_load(skin):
    clean, loaded = make_sensor(), make_sensor(REST_LOAD)
    _, expected, _ = feed(clean, skin, 5)
    for _ in range(5):
        _, got, touched = loaded.update(raw_for(skin, REST_LOAD))
    assert touched is True
    assert got == pytest.approx(expected, abs=0.03)


def test_release_is_detected_promptly_despite_resting_load():
    s = make_sensor(REST_LOAD)
    for _ in range(50):
        s.update(raw_for(2_000_000, REST_LOAD))
    s.update(raw_for(math.inf, REST_LOAD))
    _, _, touched = s.update(raw_for(math.inf, REST_LOAD))
    assert touched is False


def test_baseline_follows_slow_drift_but_freezes_while_touching():
    s = make_sensor(REST_LOAD)
    for _ in range(50 * 20):  # resting load drifts (holding one electrode lowered it)
        _, _, touched = s.update(raw_for(math.inf, 30_000_000))
    assert touched is False
    for _ in range(50 * 60):  # one-minute steady hold
        _, intensity, touched = s.update(raw_for(2_000_000, 30_000_000))
    assert touched is True and intensity > 0.3


def test_a_slow_approaching_light_touch_is_not_absorbed_into_the_baseline():
    s = make_sensor(REST_LOAD)
    touched = False
    for skin in range(100_000_000, 5_000_000, -50_000):  # ~38 s slow approach
        _, _, touched = s.update(raw_for(skin, REST_LOAD))
    assert touched is True
