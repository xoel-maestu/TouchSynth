"""Run firmware/code.py on CPython with stubbed CircuitPython hardware modules."""

import builtins
import math
import sys
import types
from pathlib import Path

import pytest

from touchsynth.protocol import parse_line

CODE_PATH = Path(__file__).resolve().parents[1] / "firmware" / "code.py"
MAINS_HZ = 50.0


class _Stop(Exception):
    pass


def _fake_modules(level_for_window):
    window = {"n": 0}

    class BufferedIn:
        def __init__(self, pin, sample_rate):
            self.sample_rate = sample_rate

        def readinto(self, buf):
            level = level_for_window(window["n"])
            window["n"] += 1
            if level is None:  # ADC error bit: short read, rest of buffer is junk
                for i in range(len(buf)):
                    buf[i] = 0
                return 1
            for i in range(len(buf)):
                hum = 3000 * math.sin(2 * math.pi * MAINS_HZ * i / self.sample_rate)
                buf[i] = max(0, min(65535, int(level + hum)))
            return len(buf)

    class DigitalInOut:
        def __init__(self, pin):
            self.value = False
            self.direction = None

    return {
        "board": types.SimpleNamespace(GP26="GP26", LED="LED"),
        "analogbufio": types.SimpleNamespace(BufferedIn=BufferedIn),
        "digitalio": types.SimpleNamespace(DigitalInOut=DigitalInOut,
                                           Direction=types.SimpleNamespace(OUTPUT="out")),
    }


def run_firmware(monkeypatch, level_for_window, lines_wanted):
    for name, module in _fake_modules(level_for_window).items():
        monkeypatch.setitem(sys.modules, name, module)
    printed = []

    def fake_print(*args, **kwargs):
        printed.append(" ".join(str(a) for a in args))
        if len(printed) > lines_wanted:
            raise _Stop

    monkeypatch.setattr(builtins, "print", fake_print)
    with pytest.raises(_Stop):
        exec(compile(CODE_PATH.read_text(), str(CODE_PATH), "exec"), {"__name__": "__main__"})
    monkeypatch.undo()
    return printed


def divider_raw(skin_ohms):
    rx = skin_ohms + 100_000
    return 65535 * rx / (1_000_000 + rx)


def test_firmware_streams_parseable_lines_and_rejects_hum(monkeypatch):
    def level(n):  # untouched, then light touch, then firm touch
        return 65535 if n < 10 else divider_raw(5e6) if n < 20 else divider_raw(1e5)

    lines = run_firmware(monkeypatch, level, 30)
    assert lines[0].startswith("#")
    readings = [parse_line(line) for line in lines[1:]]
    assert all(r is not None for r in readings)
    assert not readings[5].touched
    light, firm = readings[18], readings[29]
    assert light.touched and firm.touched
    assert firm.intensity > light.intensity + 0.5
    # a full mains period per window: the ±3000-count hum leaves < 1% error
    assert abs(light.raw - divider_raw(5e6)) < 0.01 * 65535


def test_firmware_skips_short_adc_reads(monkeypatch):
    def level(n):  # untouched, with a failed ADC window in the middle
        return None if n == 5 else 65535

    lines = run_firmware(monkeypatch, level, 10)
    readings = [parse_line(line) for line in lines[1:]]
    assert all(r.raw > 60000 for r in readings)  # the zeroed junk window never shows up
