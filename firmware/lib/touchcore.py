"""Skin-to-skin touch sensing core. Pure Python: runs on CircuitPython and CPython.

Circuit: 3V3 -- R_pullup -- ADC node -- R_series -- electrode A ~ skin ~ electrode B -- GND.
Conductances in parallel add, so the resting conductance (the ADC's own sampling
load, leaks: ~0.067 µS measured on the real board) is learned while nobody touches
and subtracted. Skin resistance spans decades (light fingertip ~MΩ, firm palm
~100 kΩ), so the intensity is the *logarithm* of the skin conductance between the touch threshold
and a "firm contact" top. Skin conductance also changes several-fold with time of
day, temperature and moisture (measured: median 0.35 µS in the evening, 0.07 µS
at night), so the top follows the player: it is set from the peaks of the last
touches (each touch counts once, so a long steady hold cannot saturate it).
"""

import math

FULL_SCALE = 65535
MIN_SKIN_OHMS = 1000.0  # clamp for a shorted electrode pair

TOUCH_ON_US = 0.02    # 50 MΩ above the resting baseline: contact starts (rest noise ~0.003)
TOUCH_OFF_US = 0.012  # 83 MΩ: contact ends (hysteresis); also intensity 0
DEBOUNCE_ON = 1       # windows needed to start a touch (latency matters most here)
DEBOUNCE_OFF = 2      # windows needed to end one (avoids dropouts mid-touch)
BASELINE_TAU_S = 2.0  # how fast the resting baseline follows drift (untouched only)
BASELINE_BAND_US = 0.015  # baseline only rises within this noise band, so a slowly
                          # approaching light touch is not absorbed; it may fall freely

G_MAX_US = 10.0        # 100 kΩ: starting "firm" level (intensity 1.0) before adapting
PEAK_MEMORY = 12       # the top follows the peaks of the last 12 touches...
PEAK_PERCENTILE = 0.75 # ...their 75th percentile...
TOP_HEADROOM = 2.2     # ...times this: typical touches ~0.7, <= ~15 % of readings at the top
TOP_STEP = 0.3         # per touch, the top moves 30 % of the way (log scale)
TOP_MIN_US, TOP_MAX_US = 0.06, 20.0


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
            raise ValueError("g_max_us must be above the touch threshold (0.02 uS)")
        self.r_pullup = r_pullup
        self.r_series = r_series
        self.touched = False
        self._log_floor = math.log(TOUCH_OFF_US)
        self._log_top = math.log(g_max_us)
        self._peaks = []
        self._touch_peak = 0.0
        self._pending = 0
        self._baseline_us = None
        self._track = 1.0 - math.exp(-1.0 / (BASELINE_TAU_S * update_hz))

    def update(self, raw):
        g_node = node_conductance_us(raw, self.r_pullup)
        if self._baseline_us is None:
            self._baseline_us = g_node
        g = self._skin_conductance(g_node - self._baseline_us)
        was_touched = self.touched
        self._update_touch(g)
        if was_touched and not self.touched:
            self._learn_peak(self._touch_peak)
            self._touch_peak = 0.0
        if not self.touched and g_node < self._baseline_us + BASELINE_BAND_US:
            self._baseline_us += self._track * (g_node - self._baseline_us)
        if not self.touched:
            return g, 0.0, False
        if g <= TOUCH_OFF_US:  # letting go, still debouncing
            return g, 0.0, True
        self._touch_peak = max(self._touch_peak, g)
        return g, self._intensity(g), True

    def _skin_conductance(self, g_path_us):
        if g_path_us <= 0.0:
            return 0.0
        skin_ohms = max(1e6 / g_path_us - self.r_series, MIN_SKIN_OHMS)
        return 1e6 / skin_ohms

    def _update_touch(self, g):
        wants_change = g < TOUCH_OFF_US if self.touched else g > TOUCH_ON_US
        self._pending = self._pending + 1 if wants_change else 0
        if self._pending >= (DEBOUNCE_OFF if self.touched else DEBOUNCE_ON):
            self.touched = not self.touched
            self._pending = 0

    def _learn_peak(self, peak):
        self._peaks = (self._peaks + [peak])[-PEAK_MEMORY:]
        ranked = sorted(self._peaks)
        typical = ranked[int(PEAK_PERCENTILE * (len(ranked) - 1))]
        target = min(max(typical * TOP_HEADROOM, TOP_MIN_US), TOP_MAX_US)
        self._log_top += TOP_STEP * (math.log(target) - self._log_top)

    def _intensity(self, g):
        x = (math.log(g) - self._log_floor) / (self._log_top - self._log_floor)
        return min(x, 1.0)
