"""Additive ambient pad + feedback-delay-network reverb, rendered per block.

The lowpass is applied analytically to each harmonic's amplitude, so the pad
is band-limited by construction and has no recursive filter state to click
when the cutoff moves. Every parameter is ramped linearly across the block.
"""

import math

import numpy as np
from scipy.signal import lfilter

from touchsynth.accent import StrikeAccent
from touchsynth.mapping import SynthParams
from touchsynth.output import HighPass, PeakLimiter

FILTER_ORDER = 2  # 12 dB/oct on top of the 1/k harmonic slope
OUTPUT_GAIN = 2.0  # light touch ~ -40 dBFS RMS, firm ~ -16 dBFS RMS; the limiter catches peaks
MIX_LEVEL = 0.15  # full intensity: mix peak ~2.2 x drive 4 x 0.15 ~ 1.3 into tanh = warmth, not fuzz
VIBRATO_HZ = 5.5
SHIMMER = 5         # index of the two-octaves-up voice in the layout
SHIMMER_AIR = 2.0   # it is filtered an octave above the pad: "air"


def _formants(fk: np.ndarray, centres: tuple) -> np.ndarray:
    return 0.1 + sum(np.exp(-((fk - f) / (0.12 * f + 50.0)) ** 2) for f in centres)


# Tone colours the timbre glides between (harmonic number k, harmonic frequency fk).
TIMBRES = (
    lambda k, fk: 1.0 / k ** 2,                                  # flute: soft, few overtones
    lambda k, fk: 1.0 / k,                                       # warm: sawtooth-like
    lambda k, fk: np.where(k % 2 == 1, 1.0 / k, 0.04 / k),       # hollow: clarinet, odd only
    lambda k, fk: _formants(fk, (700, 1220, 2600)) / k ** 0.5,   # choir "ah"
    lambda k, fk: _formants(fk, (300, 870, 2240)) / k ** 0.5,    # choir "oo"
)


def timbre_weights(k: np.ndarray, fk: np.ndarray, position: float) -> np.ndarray:
    """Harmonic weights for a point between two neighbouring palette colours,
    each normalised to the power of the 'warm' colour so morphing keeps loudness."""
    reference = np.sqrt(np.sum((1.0 / k) ** 2))
    lower = math.floor(position)
    blend = position - lower

    def colour(i):
        w = TIMBRES[i % len(TIMBRES)](k, fk)
        return w * (reference / np.sqrt(np.sum(w ** 2)))

    return (1.0 - blend) * colour(lower) + blend * colour(lower + 1)


class _Voice:
    """Phase-continuous additive oscillator; harmonic weights come from the timbre palette."""

    def __init__(self, sample_rate: int, ratio: float, harmonics: int):
        self.sample_rate = sample_rate
        self.ratio = ratio
        self.k = np.arange(1, harmonics + 1, dtype=float)
        self.phase = np.random.default_rng(int(ratio * 1000)).random()
        self.amps = np.zeros(harmonics)

    def _harmonic_amps(self, f0: float, cutoff_hz: float, timbre: float) -> np.ndarray:
        fk = self.k * f0
        amps = timbre_weights(self.k, fk, timbre) / np.sqrt(1.0 + (fk / cutoff_hz) ** (2 * FILTER_ORDER))
        amps[fk > 0.45 * self.sample_rate] = 0.0
        return amps

    def render(self, ramp: np.ndarray, f0_start: float, f0_end: float,
               cutoff_hz: float, pitch_mod: np.ndarray, timbre: float) -> np.ndarray:
        f0 = (f0_start + (f0_end - f0_start) * ramp) * pitch_mod
        phases = self.phase + np.cumsum(f0) / self.sample_rate
        self.phase = phases[-1] % 1.0
        new_amps = self._harmonic_amps(f0_end, cutoff_hz, timbre)
        amps = self.amps + np.outer(ramp, new_amps - self.amps)
        self.amps = new_amps
        return np.sum(amps * np.sin(2 * np.pi * np.outer(phases % 1.0, self.k)), axis=1)


class FdnReverb:
    """4-line feedback delay network (Jot), processed a block at a time."""

    DELAYS = (1499, 1889, 2381, 2999)
    MIX = 0.5 * np.array([[1, 1, 1, 1], [1, -1, 1, -1], [1, 1, -1, -1], [1, -1, -1, 1]])

    def __init__(self, sample_rate: int, t60_s: float = 3.0, damping: float = 0.3):
        self.lines = [np.zeros(d) for d in self.DELAYS]
        self.pos = [0] * len(self.DELAYS)
        self.gains = np.array([10 ** (-3 * d / (sample_rate * t60_s)) for d in self.DELAYS])
        self.damp_b, self.damp_a = [1 - damping], [1, -damping]
        self.damp_state = [np.zeros(1) for _ in self.DELAYS]

    def process(self, mono: np.ndarray) -> np.ndarray:
        limit = min(self.DELAYS)
        if len(mono) > limit:  # block-vectorised reads need block <= shortest delay
            return np.concatenate([self.process(mono[i:i + limit])
                                   for i in range(0, len(mono), limit)])
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


ACCENT_RATIOS = (2.0, 3.0, 2.0, 4.0)  # round robin: octave, fifth above, octave, two octaves
ACCENT_MAX_HZ = 750.0


def _accent_pitch(root_hz: float, strike_id: int) -> float:
    """One octave above the pad (felt-vibe register), varied so taps are not mechanical."""
    f1 = root_hz * ACCENT_RATIOS[strike_id % len(ACCENT_RATIOS)]
    while f1 > ACCENT_MAX_HZ:
        f1 /= 2.0
    return f1


def _pan_gains(spread: np.ndarray, width: float) -> np.ndarray:
    """Equal-power (L, R) gains per voice; width 0 = mono, 1 = full spread."""
    pan = 0.5 + 0.5 * np.clip(spread * width, -1.0, 1.0)
    return np.stack([np.cos(pan * np.pi / 2), np.sin(pan * np.pi / 2)], axis=1)


class PadSynth:
    # Roots G2..E4 (variation.py); 32 harmonics reach >3 kHz on the root voices and
    # more on the octave/shimmer layers, so the cutoff sweep is heard to the top.
    def __init__(self, sample_rate: int = 48000, harmonics: int = 32,
                 reverb: bool = True, speakers: str = "small"):
        self.sample_rate = sample_rate
        # (pitch ratio to root, detune sign, pan -1=L..1=R at full width)
        layout = [(1.0, -1, -1.0), (1.0, 0, 0.0), (1.0, 1, 1.0),
                  (1.5, 0, -0.5), (2.0, 0, 0.5), (4.0, 0, 0.0)]  # 4.0: shimmer
        self.voices = [_Voice(sample_rate, r, harmonics) for r, _, _ in layout]
        self.detune_signs = [s for _, s, _ in layout]
        self.pan_spread = np.array([p for _, _, p in layout])
        self.sub_phase = 0.0
        self.lfo_phase = 0.0
        self.vibrato_phase = 0.0
        self.accent = StrikeAccent(sample_rate)
        self._strike_id = 0
        self.reverb = FdnReverb(sample_rate) if reverb else None
        self.highpass = HighPass(sample_rate, speakers)
        self.sub_enabled = speakers == "full"  # small speakers cannot play it anyway
        self.limiter = PeakLimiter(sample_rate)
        self._prev = None
        self._prev_gate = 0.0
        self._prev_f0 = None

    def render(self, n: int, params: SynthParams, gate: float) -> np.ndarray:
        if n == 0:
            return np.zeros((0, 2))
        prev = self._prev or params
        if self._prev_f0 is None:
            self._prev_f0 = [params.root_hz * v.ratio for v in self.voices]
        ramp = np.arange(1, n + 1) / n

        def lerp(a, b):
            return a + (b - a) * ramp

        vib_phases = self.vibrato_phase + np.arange(1, n + 1) * VIBRATO_HZ / self.sample_rate
        self.vibrato_phase = vib_phases[-1] % 1.0
        pitch_mod = 2 ** (lerp(prev.vibrato_cents, params.vibrato_cents)
                          * np.sin(2 * np.pi * vib_phases) / 1200)

        out = np.zeros((n, 2))
        layer_gain = [1 / 3, 1 / 3, 1 / 3, params.fifth_gain, params.octave_gain, params.shimmer_gain]
        prev_layer_gain = [1 / 3, 1 / 3, 1 / 3, prev.fifth_gain, prev.octave_gain, prev.shimmer_gain]
        pans_now, pans_prev = _pan_gains(self.pan_spread, params.width), _pan_gains(self.pan_spread, prev.width)
        for i, voice in enumerate(self.voices):
            f0 = params.root_hz * voice.ratio * 2 ** (self.detune_signs[i] * params.detune_cents / 1200)
            cutoff = params.cutoff_hz * (SHIMMER_AIR if i == SHIMMER else 1.0)
            signal = voice.render(ramp, self._prev_f0[i], f0, cutoff, pitch_mod, params.timbre)
            self._prev_f0[i] = f0
            signal *= lerp(prev_layer_gain[i], layer_gain[i])
            out += signal[:, None] * (pans_prev[i] + np.outer(ramp, pans_now[i] - pans_prev[i]))


        if self.sub_enabled:
            sub_phases = self.sub_phase + np.cumsum(lerp(prev.root_hz, params.root_hz) / 2) / self.sample_rate
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

        if params.strike_id != self._strike_id:
            self._strike_id = params.strike_id
            self.accent.trigger(_accent_pitch(params.root_hz, params.strike_id), params.strike)
        out += self.accent.render(n)[:, None] * np.sqrt(0.5)

        if self.reverb is not None:
            wet = lerp(prev.reverb_wet, params.reverb_wet)[:, None]
            out = out * (1 - wet) + self.reverb.process(out.mean(axis=1)) * wet * 2

        self._prev, self._prev_gate = params, gate
        return self.limiter.process(self.highpass.process(out * OUTPUT_GAIN))
