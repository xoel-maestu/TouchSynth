"""Skin-to-skin touch sensing core. Pure Python: runs on CircuitPython and CPython.

Circuit: 3V3 -- R_pullup -- ADC node -- R_series -- electrode A ~ skin ~ electrode B -- GND.
Conductances in parallel add, so the resting conductance (the ADC's own sampling
load, leaks: ~0.067 µS measured on the real board) is learned while nobody touches
and subtracted. Skin resistance spans decades (light fingertip ~MΩ, firm palm
~100 kΩ), so the intensity is the *logarithm* of the skin conductance between the touch threshold
and a "firm contact" level. That top level is calibrated (g_max_us); it only
stretches for sustained stronger contact and relaxes back, so a steady touch
keeps a steady intensity and one-off spikes are ignored.
"""

import math

FULL_SCALE = 65535
MIN_SKIN_OHMS = 1000.0  # clamp for a shorted electrode pair

TOUCH_ON_US = 0.05    # 20 MΩ above the resting baseline: contact starts
TOUCH_OFF_US = 0.03   # 33 MΩ: contact ends (hysteresis); also intensity 0
DEBOUNCE_WINDOWS = 2
BASELINE_TAU_S = 2.0  # how fast the resting baseline follows drift (untouched only)
BASELINE_BAND_US = 0.015  # baseline only rises within this noise band, so a slowly
                          # approaching light touch is not absorbed; it may fall freely

G_MAX_US = 10.0        # 100 kΩ: default "firm palm" level (intensity 1.0)
G_MAX_STRETCH = 10.0   # the top may stretch up to 10x for unusually good contact
STRETCH_TAU_S = 3.0    # how long stronger contact must last to stretch the top
RELAX_TAU_S = 60.0     # how fast a stretched top returns to g_max_us


def node_conductance_us(raw, r_pullup):
    """Total conductance from the ADC node to GND, in microsiemens (divider model)."""
    if raw >= FULL_SCALE:
        return 0.0
    return 1e6 * (FULL_SCALE - raw) / (r_pullup * max(raw, 1))


class TouchSensor:
    """Turns hum-free ADC window means into (skin_conductance_us, intensity 0..1, touched).

    Boot it untouched: the first reading seeds the resting baseline.
    """

    def __init__(self, r_pullup, r_series, update_hz=50.0, g_max_us=G_MAX_US):
        if g_max_us <= TOUCH_ON_US:
            raise ValueError("g_max_us must be above the touch threshold (0.05 uS)")
        self.r_pullup = r_pullup
        self.r_series = r_series
        self.touched = False
        self._log_floor = math.log(TOUCH_OFF_US)
        self._log_seed = math.log(g_max_us)
        self._log_cap = math.log(g_max_us * G_MAX_STRETCH)
        self._log_top = self._log_seed
        self._stretch = 1.0 - math.exp(-1.0 / (STRETCH_TAU_S * update_hz))
        self._relax = 1.0 - math.exp(-1.0 / (RELAX_TAU_S * update_hz))
        self._pending = 0
        self._baseline_us = None
        self._track = 1.0 - math.exp(-1.0 / (BASELINE_TAU_S * update_hz))

    def update(self, raw):
        g_node = node_conductance_us(raw, self.r_pullup)
        if self._baseline_us is None:
            self._baseline_us = g_node
        g = self._skin_conductance(g_node - self._baseline_us)
        self._update_touch(g)
        if not self.touched and g_node < self._baseline_us + BASELINE_BAND_US:
            self._baseline_us += self._track * (g_node - self._baseline_us)
        if not self.touched:
            return g, 0.0, False
        if g <= TOUCH_OFF_US:  # letting go, still debouncing
            return g, 0.0, True
        self._update_range(g)
        return g, self._intensity(g), True

    def _skin_conductance(self, g_path_us):
        if g_path_us <= 0.0:
            return 0.0
        skin_ohms = max(1e6 / g_path_us - self.r_series, MIN_SKIN_OHMS)
        return 1e6 / skin_ohms

    def _update_touch(self, g):
        wants_change = g < TOUCH_OFF_US if self.touched else g > TOUCH_ON_US
        self._pending = self._pending + 1 if wants_change else 0
        if self._pending >= DEBOUNCE_WINDOWS:
            self.touched = not self.touched
            self._pending = 0

    def _update_range(self, g):
        log_g = math.log(g)
        if log_g > self._log_top:
            self._log_top += self._stretch * (min(log_g, self._log_cap) - self._log_top)
        else:
            self._log_top += self._relax * (self._log_seed - self._log_top)

    def _intensity(self, g):
        x = (math.log(g) - self._log_floor) / (self._log_top - self._log_floor)
        return min(x, 1.0)
