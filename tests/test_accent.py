import numpy as np

from touchsynth.accent import MAX_VOICES, StrikeAccent

FS = 48000
BLOCK = 512


def render(accent, seconds):
    return np.concatenate([accent.render(BLOCK) for _ in range(int(seconds * FS / BLOCK))])


def band_energy(x, lo, hi):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / FS)
    return spec[(f >= lo) & (f < hi)].sum()


def centroid(x):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / FS)
    return (spec * f).sum() / spec.sum()


def test_silent_until_struck():
    assert np.max(np.abs(render(StrikeAccent(FS), 0.2))) == 0.0


def test_rings_at_the_requested_pitch():
    a = StrikeAccent(FS)
    a.trigger(440.0, 0.5)
    out = render(a, 0.5)
    spec = np.abs(np.fft.rfft(out * np.hanning(len(out))))
    f = np.fft.rfftfreq(len(out), 1 / FS)
    assert abs(f[np.argmax(spec)] - 440.0) < 3


def test_soft_attack_without_a_click():
    a = StrikeAccent(FS)
    a.trigger(440.0, 1.0)
    out = render(a, 0.1)
    peak_at = np.argmax(np.abs(out))
    assert abs(out[0]) < 1e-3
    assert peak_at > 0.006 * FS            # rises over several ms, not a click
    assert np.max(np.abs(np.diff(out))) < 0.05


def test_decays_away():
    a = StrikeAccent(FS)
    a.trigger(330.0, 1.0)
    out = render(a, 3.0)
    first, last = out[:4800], out[-4800:]
    assert np.sqrt(np.mean(last ** 2)) < 0.01 * np.sqrt(np.mean(first ** 2))


def test_harder_strikes_are_louder_and_brighter():
    soft, hard = StrikeAccent(FS), StrikeAccent(FS)
    soft.trigger(330.0, 0.2)
    hard.trigger(330.0, 1.0)
    s, h = render(soft, 0.3), render(hard, 0.3)
    assert np.sqrt(np.mean(h ** 2)) > 2.5 * np.sqrt(np.mean(s ** 2))
    assert centroid(h) > 1.2 * centroid(s)


def test_stays_out_of_the_harsh_band():
    a = StrikeAccent(FS)
    a.trigger(660.0, 1.0)                  # highest note, hardest strike
    out = render(a, 0.3)
    assert band_energy(out, 2500, 5500) < 0.05 * band_energy(out, 0, 2500)


def test_fast_tapping_keeps_a_few_voices_and_steals_smoothly():
    a = StrikeAccent(FS)
    out = []
    for i in range(12):                    # 12 taps at ~3.5 per second
        a.trigger(330.0 * (1 + i % 3), 1.0)
        out.append(render(a, 0.28))
        assert len(a.voices) <= MAX_VOICES
    out = np.concatenate(out)
    assert np.max(np.abs(np.diff(out))) < 0.05
