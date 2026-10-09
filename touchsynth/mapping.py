"""One-to-many perceptual mapping: touch intensity (0..1) -> synth parameters.

Pitch and brightness are heard logarithmically and loudness in dB, so the
curves are exponential / dB-linear (Hunt & Wanderley, NIME 2002).
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SynthParams:
    gain_db: float        # master level before the touch gate
    cutoff_hz: float      # analytic lowpass applied to the harmonics
    detune_cents: float   # spread of the detuned voices
    fifth_gain: float     # linear gain of the fifth layer
    octave_gain: float    # linear gain of the octave layer
    drive_db: float       # tanh saturation drive
    lfo_hz: float         # rate of the slow amplitude/detune motion
    reverb_wet: float     # 0..1
    sub_gain: float       # linear gain of the sub-octave sine
    vibrato_cents: float = 0.0  # pitch wobble depth (from tremor)
    width: float = 0.5          # stereo spread of the voices, 0..1 (from press)
    shimmer_gain: float = 0.0   # two-octaves-up layer that grows on long holds
    noise_gain: float = 0.0     # percussive noise burst on strikes


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def _lin(x: float, a: float, b: float) -> float:
    return a + (b - a) * x


def _exp(x: float, a: float, b: float) -> float:
    return a * (b / a) ** x


def _db(db: float) -> float:
    return 10.0 ** (db / 20.0)


def _fade_in(x: float, start: float, end: float, top_db: float) -> float:
    """Equal-power fade from silence (x<=start) to top_db (x>=end)."""
    t = _clamp((x - start) / (end - start))
    return math.sin(t * math.pi / 2) * _db(top_db)


def map_intensity(x: float, bloom: float = 0.0, *, tremor: float = 0.0,
                  press: float = 0.0, hold_s: float = 0.0, transient: float = 0.0,
                  reverb_boost: float = 0.0) -> SynthParams:
    """Map touch intensity x (0..1) plus gesture expression to synth parameters.

    bloom/transient: decaying strike envelopes (0..1); tremor: 0..1; press:
    intensity above the per-touch baseline; hold_s: contact duration;
    reverb_boost: decaying lift envelope.
    """
    x = _clamp(x)
    bloom = _clamp(bloom)
    squeeze = _clamp(press / 0.25)  # real settled squeezes: p90 0.17, p99 0.28
    return SynthParams(
        gain_db=_lin(x, -30.0, 0.0),
        cutoff_hz=_exp(x, 100.0, 8000.0) * 2.0 ** (1.5 * bloom),
        detune_cents=_exp(x, 3.0, 12.0) + 10.0 * squeeze,
        fifth_gain=_fade_in(x, 0.25, 0.6, -6.0),
        octave_gain=_fade_in(x, 0.55, 0.95, -9.0),
        drive_db=_lin(x, 0.0, 12.0) + 9.0 * bloom,  # strikes briefly "break up"
        lfo_hz=_exp(x, 0.08, 0.6),
        reverb_wet=min(0.9, _lin(x, 0.5, 0.25) + max(0.0, reverb_boost)),
        sub_gain=_db(_lin(x, -12.0, -3.0)),
        vibrato_cents=20.0 * _clamp(tremor),
        width=_clamp(0.3 + 0.3 * x + 0.6 * squeeze),
        shimmer_gain=0.5 * (1.0 - math.exp(-max(0.0, hold_s) / 8.0)) * math.sqrt(x),
        noise_gain=_clamp(transient),
    )
