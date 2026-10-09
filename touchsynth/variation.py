"""Keeps the sound from always being the same: timbre and root note variation.

- The timbre is a position on a circular palette of tone colours (see
  synth.TIMBRES) that drifts slowly by itself and is pushed by each new touch
  (further for harder strikes), always gliding, never jumping.
- After a pause, the next touch starts on another note of a pentatonic scale,
  so the variety stays consonant.
Written by the sensor thread (`on_touch`), read by the audio thread (`current`):
the state is one immutable tuple swapped atomically.
"""

import math
import random
from typing import NamedTuple

PALETTE_SIZE = 5                     # flute, warm, hollow, choir "ah", choir "oo"
SCALE_ROOTS_HZ = tuple(110.0 * 2 ** (s / 12) for s in (-2, 0, 3, 5, 7))  # G2 A2 C3 D3 E3
JUMP_MIN, JUMP_MAX = 0.3, 1.5        # palette steps per touch: soft .. hard strike
GLIDE_TAU_S = 0.6
NEW_ROOT_AFTER_REST_S = 4.0
DRIFT = ((0.6, 47.0), (0.4, 73.0))   # (amplitude in palette steps, period in s)


class _State(NamedTuple):
    start: float      # timbre position when the last glide began
    target: float
    since: float
    root_hz: float


class Variation:
    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._phases = [self._rng.random() * 2 * math.pi for _ in DRIFT]
        start = self._rng.random() * PALETTE_SIZE
        self._state = _State(start, start, 0.0, SCALE_ROOTS_HZ[1])

    def on_touch(self, strike: float, now: float, rested_s: float) -> None:
        s = self._state
        root = s.root_hz
        if rested_s >= NEW_ROOT_AFTER_REST_S:
            root = self._rng.choice([r for r in SCALE_ROOTS_HZ if r != root])
        jump = (JUMP_MIN + (JUMP_MAX - JUMP_MIN) * strike) * self._rng.choice((-1, 1))
        here = self._glide(s, now)
        self._state = _State(here, here + jump, now, root)

    def current(self, now: float) -> tuple[float, float]:
        """(timbre position on the palette circle, root frequency in Hz)."""
        s = self._state
        return (self._glide(s, now) + self._drift(now)) % PALETTE_SIZE, s.root_hz

    @staticmethod
    def _glide(s: _State, now: float) -> float:
        return s.target + (s.start - s.target) * math.exp(-max(0.0, now - s.since) / GLIDE_TAU_S)

    def _drift(self, now: float) -> float:
        return sum(a * math.sin(2 * math.pi * now / period + phase)
                   for (a, period), phase in zip(DRIFT, self._phases))
