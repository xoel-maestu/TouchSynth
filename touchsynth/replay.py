"""Offline rendering of a stream of touch readings (recorded sessions, simulations)."""

from typing import Iterator, NamedTuple, Sequence

import numpy as np

from touchsynth.controller import TouchController
from touchsynth.mapping import SynthParams
from touchsynth.sources import UPDATE_HZ
from touchsynth.synth import PadSynth

SAMPLE_RATE = 48000
BLOCK = 512


class Frame(NamedTuple):
    t: float
    params: SynthParams
    gate: float
    touched: bool
    audio: np.ndarray  # (BLOCK, 2)


def replay(readings: Sequence[tuple[float, float, bool]], seed: int = 0,
           speakers: str = "small") -> Iterator[Frame]:
    """Feed (t, intensity, touched) readings to the controller at their times and
    render the synth block by block; a fixed seed makes renders reproducible."""
    ctrl = TouchController(UPDATE_HZ, seed=seed)
    synth = PadSynth(SAMPLE_RATE, speakers=speakers)
    i, t, touched = 0, 0.0, False
    while t < readings[-1][0]:
        while i < len(readings) and readings[i][0] <= t:
            _, intensity, touched = readings[i]
            ctrl.update(intensity, touched, readings[i][0])
            i += 1
        params, gate = ctrl.current(t)
        yield Frame(t, params, gate, touched, synth.render(BLOCK, params, gate))
        t += BLOCK / SAMPLE_RATE
