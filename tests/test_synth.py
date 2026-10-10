import os
import time

import numpy as np
import pytest

from touchsynth.mapping import map_intensity
from touchsynth.synth import OUTPUT_GAIN, FdnReverb, PadSynth

FS = 48000
BLOCK = 512


def render_seconds(synth, seconds, x, gate=1.0):
    params = map_intensity(x)
    blocks = [synth.render(BLOCK, params, gate) for _ in range(int(seconds * FS / BLOCK))]
    return np.concatenate(blocks)


def rms(a):
    return float(np.sqrt(np.mean(a ** 2)))


def spectral_centroid(a):
    mono = a.mean(axis=1)
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    freqs = np.fft.rfftfreq(len(mono), 1 / FS)
    return float((spectrum * freqs).sum() / spectrum.sum())


def test_output_is_finite_bounded_stereo():
    out = render_seconds(PadSynth(FS), 0.5, 1.0)
    assert out.shape[1] == 2
    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) <= 1.0


def test_closed_gate_is_silent():
    out = render_seconds(PadSynth(FS), 0.5, 1.0, gate=0.0)
    assert np.max(np.abs(out)) == 0.0


def test_firm_touch_is_louder_than_light_touch():
    light = render_seconds(PadSynth(FS), 1.0, 0.2)[FS // 2:]
    firm = render_seconds(PadSynth(FS), 1.0, 0.8)[FS // 2:]
    assert 20 * np.log10(rms(firm) / rms(light)) > 10.0


def test_firm_touch_is_brighter_than_light_touch():
    light = render_seconds(PadSynth(FS, reverb=False), 1.0, 0.2)[FS // 2:]
    firm = render_seconds(PadSynth(FS, reverb=False), 1.0, 0.8)[FS // 2:]
    assert spectral_centroid(firm) > 2.0 * spectral_centroid(light)


def steady_centroid(x, bloom=0.0):
    synth = PadSynth(FS, reverb=False)
    params = map_intensity(x, bloom)
    out = np.concatenate([synth.render(BLOCK, params, 1.0) for _ in range(100)])
    return spectral_centroid(out[FS // 2:])


def test_brightness_keeps_rising_up_to_full_intensity():
    assert steady_centroid(1.0) > 1.2 * steady_centroid(0.75)


def test_bloom_is_audible_at_moderate_intensity():
    assert steady_centroid(0.4, bloom=1.0) > 1.2 * steady_centroid(0.4)


def test_bloom_adds_nothing_once_brightness_is_already_high():
    # firm slaps are conveyed by the accent, not by pushing into the harsh band
    assert steady_centroid(0.9, bloom=1.0) == pytest.approx(steady_centroid(0.9), rel=0.02)


def test_blocks_join_without_clicks():
    synth = PadSynth(FS, reverb=False)
    out = np.concatenate([synth.render(BLOCK, map_intensity(x), 1.0)
                          for x in np.linspace(0, 1, 200)])
    steps = np.max(np.abs(np.diff(out, axis=0)), axis=1)
    at_boundaries = steps[BLOCK - 1::BLOCK]
    assert at_boundaries.max() <= steps.max() * 0.5


@pytest.mark.skipif(bool(os.environ.get("CI")), reason="timing varies on shared CI runners")
def test_renders_faster_than_real_time_with_margin():
    synth = PadSynth(FS)
    params = map_intensity(1.0)
    synth.render(BLOCK, params, 1.0)
    batches = []
    for _ in range(5):  # best of 5: robust to momentary load from other processes
        start = time.perf_counter()
        for _ in range(20):
            synth.render(BLOCK, params, 1.0)
        batches.append((time.perf_counter() - start) / 20)
    assert min(batches) < 0.5 * BLOCK / FS  # at least 2x faster than real time


def test_reverb_tail_decays():
    rev = FdnReverb(FS, t60_s=2.0)
    impulse = np.zeros(BLOCK)
    impulse[0] = 1.0
    rev.process(impulse)
    silence = np.zeros(BLOCK)
    tail = [rms(rev.process(silence)) for _ in range(int(6 * FS / BLOCK))]
    assert max(tail[:20]) > 0.0
    assert tail[-1] < 1e-3 * max(tail[:20])  # > 60 dB down after 6 s (T60 = 2 s)


def test_reverb_is_independent_of_block_size():
    signal = np.random.default_rng(0).standard_normal(6000)
    small, large = FdnReverb(FS), FdnReverb(FS)
    out_small = np.concatenate([small.process(signal[i:i + 250]) for i in range(0, 6000, 250)])
    out_large = np.concatenate([large.process(signal[i:i + 2000]) for i in range(0, 6000, 2000)])
    assert np.allclose(out_small, out_large)


@pytest.mark.parametrize("bloom", [0.0, 1.0])
def test_never_clips_even_with_bloom_and_reverb(bloom):
    synth = PadSynth(FS)
    out = np.concatenate([synth.render(BLOCK, map_intensity(1.0, bloom), 1.0) for _ in range(300)])
    assert np.max(np.abs(out)) < 0.95


@pytest.mark.parametrize("n", [128, 256, 512, 1024])
def test_supports_variable_block_sizes(n):
    out = PadSynth(FS).render(n, map_intensity(0.5), 1.0)
    assert out.shape == (n, 2)


def test_saturation_is_gentle_at_full_intensity():
    synth = PadSynth(FS, reverb=False)
    out = render_seconds(synth, 1.0, 1.0)
    ceiling = OUTPUT_GAIN / np.sqrt(10 ** (12 / 20))  # tanh asymptote after makeup
    assert np.max(np.abs(out)) < min(0.95 * ceiling, 1.0)


def dry(params, seconds=1.0):
    synth = PadSynth(FS, reverb=False)
    return np.concatenate([synth.render(BLOCK, params, 1.0) for _ in range(int(seconds * FS / BLOCK))])


def test_vibrato_modulates_the_pitch():
    from dataclasses import replace
    base = map_intensity(0.0)

    def sideband_power(params):  # FM sidebands at 110 ± 5.5 Hz
        mono = dry(params, 2.0)[FS // 2:].mean(axis=1)
        spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) ** 2
        f = np.fft.rfftfreq(len(mono), 1 / FS)
        return spec[(abs(f - 104.5) < 1) | (abs(f - 115.5) < 1)].sum() / spec.sum()

    assert sideband_power(replace(base, vibrato_cents=20.0)) > 10 * sideband_power(base)


def test_width_decorrelates_the_channels():
    from dataclasses import replace
    p = map_intensity(0.6)

    def corr(width):
        out = dry(replace(p, width=width))[FS // 4:]
        return np.corrcoef(out[:, 0], out[:, 1])[0, 1]

    assert corr(1.0) < corr(0.0) - 0.1


def test_shimmer_adds_brightness():
    from dataclasses import replace
    p = map_intensity(0.6)
    assert spectral_centroid(dry(replace(p, shimmer_gain=0.5))) > 1.15 * spectral_centroid(dry(p))


def test_a_new_strike_rings_the_accent_once():
    from dataclasses import replace
    p = map_intensity(0.6)
    synth = PadSynth(FS, reverb=False)
    synth.render(BLOCK, p, 1.0)
    struck = replace(p, strike=1.0, strike_id=1)
    synth.render(BLOCK, struck, 1.0)
    synth.render(BLOCK, struck, 1.0)          # same strike id: no retrigger
    assert len(synth.accent.voices) == 1


def test_limiter_keeps_peaks_below_the_ceiling_in_the_worst_case():
    from dataclasses import replace

    from touchsynth.output import CEILING
    synth = PadSynth(FS)
    worst = replace(map_intensity(1.0, bloom=1.0, tremor=1.0, press=0.3, hold_s=30.0),
                    gain_db=6.0)
    out = np.concatenate([synth.render(BLOCK, worst, 1.0) for _ in range(200)])
    assert np.max(np.abs(out)) <= CEILING + 1e-6


def test_small_speaker_profile_removes_unplayable_bass():
    def low_share(speakers):
        out = render_seconds(PadSynth(FS, reverb=False, speakers=speakers), 1.0, 0.8)[FS // 2:]
        mono = out.mean(axis=1)
        spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) ** 2
        f = np.fft.rfftfreq(len(mono), 1 / FS)
        return spec[f < 80].sum() / spec.sum()
    assert low_share("small") < 0.01 * low_share("full")


def harmonic_levels(params, n=8):
    mono = dry(params, 1.0)[FS // 2:].mean(axis=1)
    spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    f = np.fft.rfftfreq(len(mono), 1 / FS)
    return np.array([spec[abs(f - k * params.root_hz) < 3].max() for k in range(1, n + 1)])


def test_hollow_timbre_has_weak_even_harmonics():
    from dataclasses import replace
    base = replace(map_intensity(0.7), octave_gain=0.0, fifth_gain=0.0, shimmer_gain=0.0)
    warm = harmonic_levels(replace(base, timbre=1.0))
    hollow = harmonic_levels(replace(base, timbre=2.0))
    assert hollow[1] / hollow[2] < 0.3 * warm[1] / warm[2]   # 2nd vs 3rd harmonic


def test_flute_timbre_is_darker_than_warm():
    from dataclasses import replace
    p = map_intensity(0.7)
    flute, warm = dry(replace(p, timbre=0.0)), dry(replace(p, timbre=1.0))
    assert spectral_centroid(flute) < 0.8 * spectral_centroid(warm)


def test_timbres_keep_a_similar_loudness():
    from dataclasses import replace
    p = map_intensity(0.7)
    levels = [rms(dry(replace(p, timbre=float(t)))[FS // 4:]) for t in range(5)]
    assert max(levels) / min(levels) < 2.0  # within 6 dB


def test_timbre_morph_is_click_free():
    from dataclasses import replace
    synth = PadSynth(FS, reverb=False)
    out = np.concatenate([synth.render(BLOCK, replace(map_intensity(0.7), timbre=t), 1.0)
                          for t in np.linspace(0, 5, 200)])
    steps = np.max(np.abs(np.diff(out, axis=0)), axis=1)
    assert steps[BLOCK - 1::BLOCK].max() <= steps.max() * 0.5


def test_root_note_sets_the_pitch():
    from dataclasses import replace
    p = replace(map_intensity(0.3), root_hz=146.83)
    mono = dry(p, 1.0)[FS // 2:].mean(axis=1)
    spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    f = np.fft.rfftfreq(len(mono), 1 / FS)
    assert abs(f[(f > 120) & (f < 200)][np.argmax(spec[(f > 120) & (f < 200)])] - 146.83) < 2


def test_zero_length_blocks_are_harmless():
    out = PadSynth(FS).render(0, map_intensity(0.5), 1.0)
    assert out.shape == (0, 2)


def test_small_speakers_skip_the_sub_oscillator():
    from touchsynth.synth import PadSynth as P
    assert P(FS, speakers="small").sub_enabled is False
    assert P(FS, speakers="full").sub_enabled is True
