"""Skin-to-skin touch sensing core. Pure Python: runs on CircuitPython and CPython.

Circuit: 3V3 -- R_pullup -- ADC node -- R_series -- electrode A ~ skin ~ electrode B -- GND.
Skin resistance spans decades (light fingertip ~MΩ, firm palm ~100 kΩ), so the
intensity is the *logarithm* of the skin conductance, normalised to a range that
adapts to the people playing.
"""

import math

FULL_SCALE = 65535
MIN_SKIN_OHMS = 1000.0  # clamp for a shorted electrode pair

TOUCH_ON_US = 0.1          # 10 MΩ: contact starts
TOUCH_OFF_US = 1.0 / 15.0  # 15 MΩ: contact ends (hysteresis); also intensity 0
DEBOUNCE_WINDOWS = 2

G_MAX_SEED_US = 10.0   # 100 kΩ: expected firm palm contact
G_MAX_FLOOR_US = 1.0   # 1 MΩ: the adaptive top never shrinks below this
G_MAX_DECAY_PER_S = 0.05


def conductance_us(raw, r_pullup, r_series):
    """Skin-path conductance in microsiemens from a 16-bit ADC reading."""
    if raw >= FULL_SCALE:
        return 0.0
    divider_ohms = r_pullup * raw / (FULL_SCALE - raw)
    skin_ohms = max(divider_ohms - r_series, MIN_SKIN_OHMS)
    return 1e6 / skin_ohms


class TouchSensor:
    """Turns hum-free ADC window means into (conductance_us, intensity 0..1, touched)."""

    def __init__(self, r_pullup, r_series, update_hz=50.0):
        self.r_pullup = r_pullup
        self.r_series = r_series
        self.touched = False
        self.g_max_us = G_MAX_SEED_US
        self._decay = (1.0 - G_MAX_DECAY_PER_S) ** (1.0 / update_hz)
        self._pending = 0

    def update(self, raw):
        g = conductance_us(raw, self.r_pullup, self.r_series)
        self._update_touch(g)
        if not self.touched:
            return g, 0.0, False
        self._update_range(g)
        return g, self._intensity(g), True

    def _update_touch(self, g):
        wants_change = g < TOUCH_OFF_US if self.touched else g > TOUCH_ON_US
        self._pending = self._pending + 1 if wants_change else 0
        if self._pending >= DEBOUNCE_WINDOWS:
            self.touched = not self.touched
            self._pending = 0

    def _update_range(self, g):
        if g > self.g_max_us:
            self.g_max_us = g
        else:
            self.g_max_us = max(self.g_max_us * self._decay, G_MAX_FLOOR_US, g)

    def _intensity(self, g):
        if g <= TOUCH_OFF_US:
            return 0.0
        x = math.log(g / TOUCH_OFF_US) / math.log(self.g_max_us / TOUCH_OFF_US)
        return min(x, 1.0)
