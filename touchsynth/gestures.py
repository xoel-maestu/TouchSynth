"""Gesture features from the touch stream: how a contact starts, evolves and ends.

Inspired by the ROLI Seaboard "5D touch" (strike / press / lift) and Jensenius'
impulsive / sustained action types. All features are computed from the raw
(unsmoothed) intensity so fast gestures are not blurred.
"""

import math
from collections import deque

STRIKE_WINDOW_S = 0.04        # strike = fastest rise seen in the first 40 ms
STRIKE_SLOW, STRIKE_FAST = 2.0, 15.0   # intensity/s mapped to strike 0..1
PRESS_TAU_S = 4.0             # press = intensity above this slow, per-touch baseline
TREMOR_HIGHPASS_HZ = 3.0
TREMOR_WINDOW_S = 0.3
TREMOR_FLOOR, TREMOR_FULL = 0.002, 0.03   # RMS of the 3+ Hz band (real data: p10, p90)
FALL_HISTORY_S = 1.0
FALL_LEVEL = 0.7              # lift starts when intensity drops below 70 % of the hold


def _clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


class GestureTracker:
    def __init__(self, rate_hz: float):
        self.dt = 1.0 / rate_hz
        self._press_a = 1.0 - math.exp(-self.dt / PRESS_TAU_S)
        self._hp_a = 1.0 / (1.0 + 2 * math.pi * TREMOR_HIGHPASS_HZ * self.dt)
        self._rms_a = 1.0 - math.exp(-self.dt / TREMOR_WINDOW_S)
        self.touched = False
        self.onset_time = self.release_time = self.last_time = 0.0
        self.strike = self.fall_time = 0.0
        self._baseline = self._x = self._hp = self._hp_in = self._power = 0.0
        self._history = deque()

    @property
    def press(self) -> float:
        return self._x - self._baseline

    @property
    def tremor(self) -> float:
        rms = math.sqrt(self._power)
        return math.sqrt(_clamp((rms - TREMOR_FLOOR) / (TREMOR_FULL - TREMOR_FLOOR)))

    @property
    def hold_s(self) -> float:
        return self.last_time - self.onset_time if self.touched else 0.0

    def update(self, x: float, touched: bool, now: float) -> None:
        self.last_time = now
        if touched and not self.touched:
            self._start(x, now)
        elif not touched and self.touched:
            self._release(now)
        self.touched = touched
        if touched:
            self._follow(x, now)

    def _start(self, x, now):
        self.onset_time = now
        self.strike = 0.0
        self._baseline = self._hp_in = x
        self._hp = self._power = 0.0
        self._history.clear()

    def _release(self, now):
        self.release_time = now
        top = max((x for _, x in self._history), default=0.0)
        held = [t for t, x in self._history if x >= FALL_LEVEL * top]
        self.fall_time = now - held[-1] if held else 0.0

    def _follow(self, x, now):
        self._x = x
        since = now - self.onset_time
        if since <= STRIKE_WINDOW_S:
            speed = x / (since + self.dt)
            self.strike = max(self.strike, _clamp((speed - STRIKE_SLOW) / (STRIKE_FAST - STRIKE_SLOW)))
        self._baseline += self._press_a * (x - self._baseline)
        self._hp = self._hp_a * (self._hp + x - self._hp_in)
        self._hp_in = x
        self._power += self._rms_a * (self._hp ** 2 - self._power)
        self._history.append((now, x))
        while self._history[0][0] < now - FALL_HISTORY_S:
            self._history.popleft()
