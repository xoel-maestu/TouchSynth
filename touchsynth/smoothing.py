"""Control-rate smoothing for the touch intensity signal.

OneEuroFilter: Casiez, Roussel & Vogel, "1€ Filter", CHI 2012
(https://gery.casiez.net/1euro/). Low jitter at rest, low lag on fast moves.
"""

import math


def _alpha(cutoff_hz: float, rate_hz: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff_hz)
    return 1.0 / (1.0 + tau * rate_hz)


class OneEuroFilter:
    def __init__(self, rate_hz: float, mincutoff: float = 1.0,
                 beta: float = 1.0, dcutoff: float = 1.0):
        self.rate_hz = rate_hz
        self.mincutoff = mincutoff
        self.beta = beta
        self.dcutoff = dcutoff
        self.value = None
        self.derivative = 0.0
        self._last_raw = 0.0

    def __call__(self, x: float) -> float:
        if self.value is None:
            self.value = self._last_raw = x
            return x
        raw_derivative = (x - self._last_raw) * self.rate_hz
        self._last_raw = x
        a_d = _alpha(self.dcutoff, self.rate_hz)
        self.derivative += a_d * (raw_derivative - self.derivative)
        cutoff = self.mincutoff + self.beta * abs(self.derivative)
        self.value += _alpha(cutoff, self.rate_hz) * (x - self.value)
        return self.value

