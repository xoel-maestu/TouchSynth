"""Output stage: speaker-profile high-pass and a peak limiter, so the synth sounds
clean on anything from a monitor's tiny speakers to headphones."""

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

CEILING = 10 ** (-3 / 20)        # -3 dBFS: headroom for cheap DACs and speakers
LIMITER_RELEASE_S = 0.15
LIMITER_ATTACK_SAMPLES = 32      # gain-reduction crossfade at the start of a block

# Small speakers cannot move the air for deep bass; asking them to just distorts.
SPEAKER_HIGHPASS = {"small": (4, 120.0), "full": (2, 25.0)}


class HighPass:
    def __init__(self, sample_rate: int, speakers: str, channels: int = 2):
        order, cutoff = SPEAKER_HIGHPASS[speakers]
        self.sos = butter(order, cutoff, btype="highpass", fs=sample_rate, output="sos")
        self.state = np.repeat(sosfilt_zi(self.sos)[:, :, None], channels, axis=2) * 0.0

    def process(self, block: np.ndarray) -> np.ndarray:
        out, self.state = sosfilt(self.sos, block, axis=0, zi=self.state)
        return out


class PeakLimiter:
    """Block-wise peak limiter: instant gain reduction, smooth release, hard ceiling."""

    def __init__(self, sample_rate: int, ceiling: float = CEILING):
        self.sample_rate = sample_rate
        self.ceiling = ceiling
        self.gain = 1.0

    def process(self, block: np.ndarray) -> np.ndarray:
        n = len(block)
        peak = float(np.max(np.abs(block))) if n else 0.0
        target = min(1.0, self.ceiling / peak) if peak > 0 else 1.0
        if target < self.gain:  # attack: reach the new gain within a few samples
            ramp = np.full(n, target)
            k = min(n, LIMITER_ATTACK_SAMPLES)
            ramp[:k] = np.linspace(self.gain, target, k, endpoint=False)
        else:  # release: recover smoothly towards unity
            end = target + (self.gain - target) * np.exp(-n / (LIMITER_RELEASE_S * self.sample_rate))
            ramp = np.linspace(self.gain, end, n)
        self.gain = float(ramp[-1])
        return np.clip(block * ramp[:, None], -self.ceiling, self.ceiling)
