"""Turns the stream of touch readings into synth parameters and a gate.

Written by the sensor thread (`update`), read by the audio callback (`current`).
The shared state is a single tuple swapped atomically, so no locks are needed.
"""

import math

from touchsynth.mapping import SynthParams, map_intensity
from touchsynth.smoothing import AsymmetricFollower, OneEuroFilter

GATE_ATTACK_S = 0.04
GATE_RELEASE_S = 2.0
INTENSITY_ATTACK_S = 0.04
INTENSITY_RELEASE_S = 0.3
BLOOM_THRESHOLD_PER_S = 3.0   # intensity velocity that counts as a "slap"
BLOOM_FULL_PER_S = 15.0
BLOOM_DECAY_S = 0.25
STALE_AFTER_S = 0.25          # no readings for this long (cable pulled): fade out


class TouchController:
    def __init__(self, rate_hz: float):
        # dcutoff above the paper's 1 Hz so the derivative catches 20 ms onsets
        self._filter = OneEuroFilter(rate_hz, mincutoff=1.0, beta=1.0, dcutoff=5.0)
        self._filter(0.0)  # start at rest, so the first touch registers as an onset
        self._intensity = AsymmetricFollower(rate_hz, INTENSITY_ATTACK_S, INTENSITY_RELEASE_S)
        self._gate = AsymmetricFollower(rate_hz, GATE_ATTACK_S, GATE_RELEASE_S)
        # (intensity, gate, bloom_peak, bloom_time, last_update_time)
        self._state = (0.0, 0.0, 0.0, 0.0, 0.0)

    @property
    def intensity(self) -> float:
        return self._state[0]

    def update(self, intensity: float, touched: bool, now_s: float) -> None:
        smoothed = self._filter(intensity if touched else 0.0)
        if touched:  # on release, hold the last timbre while the gate fades
            self._intensity(smoothed)
        gate = self._gate(1.0 if touched else 0.0)

        _, _, bloom_peak, bloom_time, _ = self._state
        velocity = self._filter.derivative
        if velocity > BLOOM_THRESHOLD_PER_S:
            amount = min(1.0, velocity / BLOOM_FULL_PER_S)
            if amount > _decayed(bloom_peak, bloom_time, now_s):
                bloom_peak, bloom_time = amount, now_s
        self._state = (self._intensity.value, gate, bloom_peak, bloom_time, now_s)

    def current(self, now_s: float) -> tuple[SynthParams, float]:
        intensity, gate, bloom_peak, bloom_time, last_update = self._state
        silence = now_s - last_update - STALE_AFTER_S
        if silence > 0:
            gate *= math.exp(-silence / GATE_RELEASE_S)
        return map_intensity(intensity, _decayed(bloom_peak, bloom_time, now_s)), gate


def _decayed(peak: float, since_s: float, now_s: float) -> float:
    return peak * math.exp(-max(0.0, now_s - since_s) / BLOOM_DECAY_S)
