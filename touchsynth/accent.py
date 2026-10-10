"""Strike accent: a soft "felt-mallet vibraphone" note on fast, firm touches.

Replaces the white-noise burst that sounded like a crash. Modal synthesis
(STK ModalBar, Perry Cook) with the bar's partials retuned to harmonics 1-2-4-6
so they agree with the pentatonic pad; a harder strike is like a harder mallet:
louder and with stronger upper partials (velocity -> spectral tilt, as in acoustic
instruments), never noise. Nothing is rendered in the 2.5-5.5 kHz band rated
most unpleasant (Kumar et al., JASA 2008).
"""

import numpy as np

# (ratio to f1, base amplitude, T60 seconds, velocity exponent: brightness)
PARTIALS = ((1.0, 1.00, 2.2, 0.0), (2.0, 0.30, 1.2, 1.0),
            (4.0, 0.22, 0.45, 1.5), (6.0, 0.08, 0.20, 2.5))
HARSH_BAND_HZ = 2500.0      # partials above this are not rendered
ACCENT_LEVEL = 0.2          # peak at the hardest strike (pad peaks ~0.35 pre-gain)
DYNAMIC_DB = 15.0           # softest .. hardest strike
ATTACK_SOFT_S, ATTACK_HARD_S = 0.012, 0.008   # raised-cosine onset: no click
MAX_VOICES = 4
STEAL_FADE_S = 0.02


class _Voice:
    def __init__(self, sample_rate, f1, velocity):
        keep = [p for p in PARTIALS if p[0] * f1 < HARSH_BAND_HZ]
        level = ACCENT_LEVEL * 10 ** (-DYNAMIC_DB * (1 - velocity ** 0.8) / 20)
        self.freqs = np.array([r * f1 for r, _, _, _ in keep])
        self.amps = np.array([a * velocity ** p for _, a, _, p in keep]) * level
        self.taus = np.array([t60 / 6.91 for _, _, t60, _ in keep]) * sample_rate
        self.attack = (ATTACK_SOFT_S + (ATTACK_HARD_S - ATTACK_SOFT_S) * velocity) * sample_rate
        self.life = max(t60 for _, _, t60, _ in keep) * sample_rate
        self.sample_rate = sample_rate
        self.age = 0
        self.fade_from = None

    @property
    def alive(self):
        if self.fade_from is not None:
            return self.age < self.fade_from + STEAL_FADE_S * self.sample_rate
        return self.age < self.life

    def render(self, n):
        t = self.age + np.arange(n)
        env = self.amps[:, None] * np.exp(-t / self.taus[:, None])
        tone = np.sum(env * np.sin(2 * np.pi * np.outer(self.freqs, t) / self.sample_rate), axis=0)
        tone *= 0.5 - 0.5 * np.cos(np.pi * np.minimum(t / self.attack, 1.0))
        if self.fade_from is not None:
            tone *= np.clip(1 - (t - self.fade_from) / (STEAL_FADE_S * self.sample_rate), 0, 1)
        self.age += n
        return tone


class StrikeAccent:
    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate
        self.voices = []

    def trigger(self, f1: float, velocity: float) -> None:
        velocity = min(1.0, max(0.0, velocity))
        sounding = [v for v in self.voices if v.fade_from is None]
        if len(sounding) >= MAX_VOICES:  # steal the oldest, fading it out
            sounding[0].fade_from = sounding[0].age
        self.voices.append(_Voice(self.sample_rate, f1, velocity))

    def render(self, n: int) -> np.ndarray:
        out = np.zeros(n)
        for voice in self.voices:
            out += voice.render(n)
        self.voices = [v for v in self.voices if v.alive]
        return out
