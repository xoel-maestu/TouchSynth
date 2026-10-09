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


def test_bloom_is_audible_on_firm_slaps():
    assert steady_centroid(0.9, bloom=1.0) > 1.2 * steady_centroid(0.9)


def test_blocks_join_without_clicks():
    synth = PadSynth(FS, reverb=False)
    out = np.concatenate([synth.render(BLOCK, map_intensity(x), 1.0)
                          for x in np.linspace(0, 1, 200)])
    steps = np.max(np.abs(np.diff(out, axis=0)), axis=1)
    at_boundaries = steps[BLOCK - 1::BLOCK]
    assert at_boundaries.max() <= steps.max() * 0.5


def test_renders_faster_than_real_time_with_margin():
    synth = PadSynth(FS)
    params = map_intensity(1.0)
    synth.render(BLOCK, params, 1.0)
    start = time.perf_counter()
    for _ in range(100):
        synth.render(BLOCK, params, 1.0)
    per_block = (time.perf_counter() - start) / 100
    assert per_block < 0.3 * BLOCK / FS


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
