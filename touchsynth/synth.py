"""Additive ambient pad + feedback-delay-network reverb, rendered per block.

The lowpass is applied analytically to each harmonic's amplitude, so the pad
is band-limited by construction and has no recursive filter state to click
when the cutoff moves. Every parameter is ramped linearly across the block.
"""

import numpy as np
from scipy.signal import lfilter

from touchsynth.mapping import SynthParams

FILTER_ORDER = 2  # ~24 dB/oct feel
OUTPUT_GAIN = 2.0  # light touch ~ -40 dBFS RMS, firm ~ -16 dBFS RMS, peak < 0.9
MIX_LEVEL = 0.15  # full intensity: mix peak ~2.2 x drive 4 x 0.15 ~ 1.3 into tanh = warmth, not fuzz


class _Voice:
    """Phase-continuous additive oscillator with sawtooth-like harmonics."""

    def __init__(self, sample_rate: int, ratio: float, harmonics: int):
        self.sample_rate = sample_rate
        self.ratio = ratio
        self.k = np.arange(1, harmonics + 1, dtype=float)
        self.phase = np.random.default_rng(int(ratio * 1000)).random()
        self.amps = np.zeros(harmonics)

    def _harmonic_amps(self, f0: float, cutoff_hz: float) -> np.ndarray:
        fk = self.k * f0
        amps = (1.0 / self.k) / np.sqrt(1.0 + (fk / cutoff_hz) ** (2 * FILTER_ORDER))
        amps[fk > 0.45 * self.sample_rate] = 0.0
        return amps

    def render(self, ramp: np.ndarray, f0_start: float, f0_end: float,
               cutoff_hz: float) -> np.ndarray:
        f0 = f0_start + (f0_end - f0_start) * ramp
        phases = self.phase + np.cumsum(f0) / self.sample_rate
        self.phase = phases[-1] % 1.0
        new_amps = self._harmonic_amps(f0_end, cutoff_hz)
        amps = self.amps + np.outer(ramp, new_amps - self.amps)
        self.amps = new_amps
        return np.sum(amps * np.sin(2 * np.pi * np.outer(phases % 1.0, self.k)), axis=1)


class FdnReverb:
    """4-line feedback delay network (Jot); block-vectorised, needs block <= min delay."""

    DELAYS = (1499, 1889, 2381, 2999)
    MIX = 0.5 * np.array([[1, 1, 1, 1], [1, -1, 1, -1], [1, 1, -1, -1], [1, -1, -1, 1]])

    def __init__(self, sample_rate: int, t60_s: float = 3.0, damping: float = 0.3):
        self.lines = [np.zeros(d) for d in self.DELAYS]
        self.pos = [0] * len(self.DELAYS)
        self.gains = np.array([10 ** (-3 * d / (sample_rate * t60_s)) for d in self.DELAYS])
        self.damp_b, self.damp_a = [1 - damping], [1, -damping]
        self.damp_state = [np.zeros(1) for _ in self.DELAYS]

    def process(self, mono: np.ndarray) -> np.ndarray:
        n = len(mono)
        idx = [(p + np.arange(n)) % len(line) for p, line in zip(self.pos, self.lines)]
        outs = np.stack([line[i] for line, i in zip(self.lines, idx)])
        feedback = self.MIX @ (outs * self.gains[:, None])
        for j, (line, i) in enumerate(zip(self.lines, idx)):
            damped, self.damp_state[j] = lfilter(
                self.damp_b, self.damp_a, feedback[j], zi=self.damp_state[j])
            line[i] = mono + damped
            self.pos[j] = (self.pos[j] + n) % len(line)
        return np.stack([outs[0] + outs[2], outs[1] + outs[3]], axis=1) * 0.5


class PadSynth:
    def __init__(self, sample_rate: int = 48000, root_hz: float = 55.0,
                 harmonics: int = 16, reverb: bool = True):
        self.sample_rate = sample_rate
        self.root_hz = root_hz
        # (pitch ratio to root, detune sign, pan 0=L..1=R)
        layout = [(1.0, -1, 0.15), (1.0, 0, 0.5), (1.0, 1, 0.85),
                  (1.5, 0, 0.35), (2.0, 0, 0.65)]
        self.voices = [_Voice(sample_rate, r, harmonics) for r, _, _ in layout]
        self.detune_signs = [s for _, s, _ in layout]
        self.pans = np.array([[np.cos(p * np.pi / 2), np.sin(p * np.pi / 2)]
                              for _, _, p in layout])
        self.sub_phase = 0.0
        self.lfo_phase = 0.0
        self.reverb = FdnReverb(sample_rate) if reverb else None
        self._prev = None
        self._prev_gate = 0.0
        self._prev_f0 = [root_hz * r for r, _, _ in layout]

    def render(self, n: int, params: SynthParams, gate: float) -> np.ndarray:
        prev = self._prev or params
        ramp = np.arange(1, n + 1) / n

        def lerp(a, b):
            return a + (b - a) * ramp

        out = np.zeros((n, 2))
        layer_gain = [1 / 3, 1 / 3, 1 / 3, params.fifth_gain, params.octave_gain]
        prev_layer_gain = [1 / 3, 1 / 3, 1 / 3, prev.fifth_gain, prev.octave_gain]
        for i, voice in enumerate(self.voices):
            f0 = self.root_hz * voice.ratio * 2 ** (self.detune_signs[i] * params.detune_cents / 1200)
            signal = voice.render(ramp, self._prev_f0[i], f0, params.cutoff_hz)
            self._prev_f0[i] = f0
            signal *= lerp(prev_layer_gain[i], layer_gain[i])
            out += signal[:, None] * self.pans[i]

        sub_phases = self.sub_phase + np.arange(1, n + 1) * (self.root_hz / 2) / self.sample_rate
        self.sub_phase = sub_phases[-1] % 1.0
        sub = np.sin(2 * np.pi * sub_phases) * lerp(prev.sub_gain, params.sub_gain)
        out += sub[:, None] * np.sqrt(0.5)

        lfo_phases = self.lfo_phase + np.cumsum(lerp(prev.lfo_hz, params.lfo_hz)) / self.sample_rate
        self.lfo_phase = lfo_phases[-1] % 1.0
        out[:, 0] *= 1 + 0.15 * np.sin(2 * np.pi * lfo_phases)
        out[:, 1] *= 1 + 0.15 * np.sin(2 * np.pi * lfo_phases + np.pi / 2)

        drive = 10 ** (lerp(prev.drive_db, params.drive_db) / 20)
        out = np.tanh(out * MIX_LEVEL * drive[:, None]) / np.sqrt(drive)[:, None]

        level = 10 ** (lerp(prev.gain_db, params.gain_db) / 20) * lerp(self._prev_gate, gate)
        out *= level[:, None]

        if self.reverb is not None:
            wet = lerp(prev.reverb_wet, params.reverb_wet)[:, None]
            out = out * (1 - wet) + self.reverb.process(out.mean(axis=1)) * wet * 2

        self._prev, self._prev_gate = params, gate
        return np.clip(out * OUTPUT_GAIN, -1.0, 1.0)
