"""Replay a real Pico 2 recording through the sensing core (regression on hardware data)."""

import csv
from pathlib import Path

from touchcore import TouchSensor

DATA = Path(__file__).parent / "data" / "pico2_pressure_session.csv"
R_PULLUP = 1_000_000
G_MAX_US = 0.8  # firmware/code.py calibration for this setup
REST_RAW = 61350  # same board at rest, from the session just before (the recording starts mid-touch)

# Phases read off the recording (seconds): rest, light pinch, firm pinch.
REST = [(15, 19), (33, 40), (66, 78), (97, 100)]
LIGHT = [(42, 50), (80.5, 84)]  # the faintest onset (80.0-80.5 s) sits right at the threshold
FIRM = [(53, 63), (86, 95)]


def replay():
    rows = [r for r in csv.reader(line for line in DATA.open() if not line.startswith("#"))][1:]
    sensor = TouchSensor(R_PULLUP, 0, g_max_us=G_MAX_US)
    sensor.update(REST_RAW)  # booted untouched
    out = []
    for t, raw in rows:
        g, intensity, touched = sensor.update(int(raw))
        out.append((float(t), intensity, touched))
    return out


def during(samples, spans):
    return [s for s in samples if any(a <= s[0] < b for a, b in spans)]


def test_no_false_touches_at_rest():
    assert not any(touched for _, _, touched in during(replay(), REST))


def test_every_touch_phase_is_detected():
    assert all(touched for _, _, touched in during(replay(), LIGHT + FIRM))


def test_firm_reads_clearly_higher_than_light():
    samples = replay()
    light = [x for _, x, _ in during(samples, LIGHT)]
    firm = [x for _, x, _ in during(samples, FIRM)]
    assert min(firm) > max(light) - 0.05
    assert sum(firm) / len(firm) - sum(light) / len(light) > 0.25


def test_releases_are_detected_within_100_ms():
    samples = replay()
    for start, _ in REST:  # already untouched 100 ms into every rest span
        first = [s for s in samples if start <= s[0] < start + 0.1]
        assert first and not any(touched for _, _, touched in first)
