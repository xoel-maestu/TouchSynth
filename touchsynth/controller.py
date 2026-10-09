"""Turns the stream of touch readings into synth parameters and a gate.

Written by the sensor thread (`update`), read by the audio callback (`current`).
The shared state is one immutable tuple swapped atomically, so no locks are
needed. Envelopes are evaluated analytically at audio time, not stepped at the
sensor rate, so they stay smooth and add no latency.
"""

import math
from typing import NamedTuple

from touchsynth.gestures import GestureTracker
from touchsynth.mapping import SynthParams, map_intensity
from touchsynth.smoothing import OneEuroFilter
from touchsynth.variation import Variation

ATTACK_SLOW_S, ATTACK_FAST_S = 0.12, 0.005   # gate attack: soft touch .. slap
RELEASE_MIN_S, RELEASE_MAX_S = 0.35, 3.0     # gate release follows how slowly you let go
RELEASE_PER_FALL = 3.0                       # release tau grows 3 s per second of lift
TRANSIENT_DECAY_S = 0.03
BLOOM_DECAY_S = 0.15
LIFT_REVERB = 0.35                           # extra reverb send after a fast lift ...
LIFT_REVERB_DECAY_S = 0.6                    # ... decaying like this
STALE_AFTER_S = 0.25                         # no readings for this long (cable pulled)
STALE_RELEASE_S = 1.0


class _Envelope(NamedTuple):
    """Exponential approach from `start` (at time `since`) towards `target`."""
    start: float
    target: float
    tau: float
    since: float

    def at(self, now: float) -> float:
        elapsed = max(0.0, now - self.since)
        return self.target + (self.start - self.target) * math.exp(-elapsed / self.tau)


class _State(NamedTuple):
    level: float
    gate: _Envelope
    strike: float
    onset: float
    tremor: float
    press: float
    hold_s: float
    lift: float
    release: float
    last_update: float


class TouchController:
    def __init__(self, rate_hz: float, seed=None):
        self._gesture = GestureTracker(rate_hz)
        self._variation = Variation(seed)
        # light smoothing only: the real sensor is quiet (steady-hold std ~0.002)
        self._level = OneEuroFilter(rate_hz, mincutoff=4.0, beta=5.0, dcutoff=5.0)
        self._state = _State(0.0, _Envelope(0.0, 0.0, 1.0, 0.0),
                             0.0, -1e9, 0.0, 0.0, 0.0, 0.0, -1e9, 0.0)

    @property
    def intensity(self) -> float:
        return self._state.level

    def update(self, intensity: float, touched: bool, now_s: float) -> None:
        g, s = self._gesture, self._state
        g.update(intensity, touched, now_s)
        level, gate, lift, hold = s.level, s.gate, s.lift, s.hold_s
        if touched:
            if g.onset_time == now_s:
                self._level.value = None  # start from the first reading, not from 0
                self._variation.on_touch(g.strike, now_s, rested_s=now_s - s.release)
            level = self._level(intensity)
            hold = g.hold_s
            attack = ATTACK_SLOW_S * (ATTACK_FAST_S / ATTACK_SLOW_S) ** g.strike
            if gate.target != 1.0 or gate.tau != attack:
                gate = _Envelope(gate.at(now_s), 1.0, attack, now_s)
        elif gate.target != 0.0:
            release = min(RELEASE_MAX_S, RELEASE_MIN_S + RELEASE_PER_FALL * g.fall_time)
            gate = _Envelope(gate.at(now_s), 0.0, release, now_s)
            lift = LIFT_REVERB * max(0.0, 1.0 - g.fall_time / 0.3)
        self._state = _State(level, gate, g.strike, g.onset_time, g.tremor, g.press,
                             hold, lift, g.release_time, now_s)

    def current(self, now_s: float) -> tuple[SynthParams, float]:
        s = self._state
        gate = s.gate.at(now_s)
        silence = now_s - s.last_update - STALE_AFTER_S
        if silence > 0 and s.gate.target == 1.0:  # readings stopped mid-touch
            gate *= math.exp(-silence / STALE_RELEASE_S)
        since_onset = max(0.0, now_s - s.onset)
        timbre, root_hz = self._variation.current(now_s)
        params = map_intensity(
            s.level,
            bloom=s.strike * math.exp(-since_onset / BLOOM_DECAY_S),
            transient=s.strike * math.exp(-since_onset / TRANSIENT_DECAY_S),
            tremor=s.tremor, press=s.press, hold_s=s.hold_s,
            reverb_boost=s.lift * math.exp(-max(0.0, now_s - s.release) / LIFT_REVERB_DECAY_S),
            timbre=timbre, root_hz=root_hz,
        )
        return params, gate
