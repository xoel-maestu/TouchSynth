"""Keeps the sound from always being the same: timbre and root note variation.

- The timbre is a position on a circular palette of tone colours (see
  synth.TIMBRES) that drifts slowly by itself and is pushed by each new touch
  (further for harder strikes), always gliding, never jumping.
- Notes walk a two-octave pentatonic scale: each re-touch steps to a
  neighbouring note (two steps for hard strikes), biased back towards the
  middle, with a short portamento; a long pause returns to the low "home"
  octave. Pentatonic keeps any sequence consonant. Contact glitches (a few
  tens of ms, common with bare-pin electrodes) change nothing.
Written by the sensor thread (`on_touch`), read by the audio thread (`current`):
the state is one immutable tuple swapped atomically.
"""

import math
import random
from typing import NamedTuple

PALETTE_SIZE = 5                     # flute, warm, hollow, choir "ah", choir "oo"
SCALE_ROOTS_HZ = tuple(110.0 * 2 ** (s / 12)  # G2 A2 C3 D3 E3 G3 A3 C4 D4 E4
                       for s in (-2, 0, 3, 5, 7, 10, 12, 15, 17, 19))
HOME_DEGREES = range(0, 5)           # the low octave
RETOUCH_MIN_GAP_S = 0.15             # shorter gaps are contact glitches
HARD_STRIKE = 0.6                    # above this a re-touch steps two notes
PORTAMENTO_S = 0.05
JUMP_MIN, JUMP_MAX = 0.3, 1.5        # palette steps per touch: soft .. hard strike
GLIDE_TAU_S = 0.6
NEW_ROOT_AFTER_REST_S = 4.0
DRIFT = ((0.6, 47.0), (0.4, 73.0))   # (amplitude in palette steps, period in s)


class _State(NamedTuple):
    start: float      # timbre position when the last glide began
    target: float
    since: float
    degree: int       # index in SCALE_ROOTS_HZ
    from_hz: float    # root when the last portamento began


class Variation:
    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._phases = [self._rng.random() * 2 * math.pi for _ in DRIFT]
        start = self._rng.random() * PALETTE_SIZE
        home = SCALE_ROOTS_HZ[1]
        self._state = _State(start, start, 0.0, 1, home)

    def on_touch(self, strike: float, now: float, rested_s: float) -> None:
        if rested_s < RETOUCH_MIN_GAP_S:
            return
        s = self._state
        if rested_s >= NEW_ROOT_AFTER_REST_S:
            degree = self._rng.choice([d for d in HOME_DEGREES if d != s.degree])
        else:
            degree = self._step(s.degree, 2 if strike > HARD_STRIKE else 1)
        jump = (JUMP_MIN + (JUMP_MAX - JUMP_MIN) * strike) * self._rng.choice((-1, 1))
        here = self._glide(s, now)
        self._state = _State(here, here + jump, now, degree, self._root(s, now))

    def current(self, now: float) -> tuple[float, float]:
        """(timbre position on the palette circle, root frequency in Hz)."""
        s = self._state
        return (self._glide(s, now) + self._drift(now)) % PALETTE_SIZE, self._root(s, now)

    def _step(self, degree: int, size: int) -> int:
        top = len(SCALE_ROOTS_HZ) - 1
        up_chance = 0.5 - 0.4 * (degree - top / 2) / (top / 2)  # lean back to the middle
        step = size if self._rng.random() < up_chance else -size
        if not 0 <= degree + step <= top:  # bounce off the ends of the scale
            step = -step
        return degree + step

    @staticmethod
    def _root(s: _State, now: float) -> float:
        target = SCALE_ROOTS_HZ[s.degree]
        remaining = math.exp(-max(0.0, now - s.since) / PORTAMENTO_S)
        return target * (s.from_hz / target) ** remaining

    @staticmethod
    def _glide(s: _State, now: float) -> float:
        return s.target + (s.start - s.target) * math.exp(-max(0.0, now - s.since) / GLIDE_TAU_S)

    def _drift(self, now: float) -> float:
        return sum(a * math.sin(2 * math.pi * now / period + phase)
                   for (a, period), phase in zip(DRIFT, self._phases, strict=True))
