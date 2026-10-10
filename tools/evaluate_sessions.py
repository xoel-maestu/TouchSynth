"""Replay recorded sessions through the whole host pipeline and score them.

Usage:  python tools/evaluate_sessions.py sessions/*.csv
Each check states what "good" means for a real player; the script exits 1 if
any check fails, so tuning can iterate until every recorded session passes.
"""

import csv
import sys

import numpy as np

from touchsynth.output import CEILING
from touchsynth.replay import replay
from touchsynth.variation import SCALE_ROOTS_HZ


def load(path):
    with open(path) as f:
        rows = [(float(r["host_s"]), float(r["intensity"]), r["touched"] == "1")
                for r in csv.DictReader(f)]
    return [(t - rows[0][0], x, touched) for t, x, touched in rows]


def strike_harshness_db(frames):
    """Rise of 2.5-5.5 kHz energy (the band rated most unpleasant, Kumar et al.
    2008) in the first 60 ms of a touch vs. 300-600 ms later, for the hardest
    strikes (90th percentile): that is where a harsh "crash" lives. Only touches
    held >= 0.6 s count, so the reference is the sustained tone, not the tail."""
    audio = np.concatenate([f.audio for f in frames]).mean(axis=1)
    block, rises = len(frames[0].audio), []
    held = int(0.6 * 48000 / block) + 1  # compare within the same touch, not with its reverb tail
    onsets = [i for i in range(1, len(frames) - held)
              if not frames[i - 1].touched and all(f.touched for f in frames[i:i + held])]
    for i in onsets:
        start = i * block
        early, late = audio[start:start + 2880], audio[start + 14400:start + 28800]
        if len(late) < 14400:
            continue
        band = []
        for seg in (early, late):
            spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2 / len(seg)
            f = np.fft.rfftfreq(len(seg), 1 / 48000)
            band.append(spec[(f > 2500) & (f < 5500)].sum() / spec.sum())
        rises.append(10 * np.log10((band[0] + 1e-12) / (band[1] + 1e-12)))
    return float(np.percentile(rises, 90)) if rises else 0.0


def spread(values):
    return np.percentile(values, 90) - np.percentile(values, 10) if values else 0.0


def evaluate(path):
    frames = list(replay(load(path)))
    peak = max(float(np.max(np.abs(f.audio))) for f in frames)
    params = [f.params for f in frames if f.touched and f.gate > 0.5]
    if not params:
        print(f"\n{path}: no touches, skipped")
        return True
    gain = [p.gain_db for p in params]
    cutoff = np.array([p.cutoff_hz for p in params])
    vibrato = np.array([p.vibrato_cents for p in params])
    brightness = np.percentile(cutoff, 90) / np.percentile(cutoff, 10)
    degrees = [min(range(len(SCALE_ROOTS_HZ)), key=lambda d: abs(SCALE_ROOTS_HZ[d] - f.params.root_hz))
               for f in frames if f.touched]
    notes = [d for d, prev in zip(degrees[1:], degrees, strict=False) if d != prev]
    steps = [abs(b - a) for a, b in zip(notes, notes[1:], strict=False)]
    melodic = np.mean([s <= 2 for s in steps]) if steps else 0.0
    colours = len({int(p.timbre) for p in params})
    harsh = strike_harshness_db(frames)
    checks = [
        ("no clipping (peak <= ceiling)", peak <= CEILING + 1e-6, f"{peak:.3f}"),
        ("loudness follows touch (gain p10..p90 >= 8 dB)", spread(gain) >= 8, f"{spread(gain):.1f} dB"),
        ("brightness follows touch (cutoff p90/p10 >= 3)", brightness >= 3, f"x{brightness:.1f}"),
        ("vibrato is used but not saturated (p50 < 15 cents, p90 > 3)",
         np.percentile(vibrato, 50) < 15 and np.percentile(vibrato, 90) > 3,
         f"p50 {np.percentile(vibrato, 50):.1f}, p90 {np.percentile(vibrato, 90):.1f}"),
        ("stereo width varies (p10..p90 >= 0.2)", spread([p.width for p in params]) >= 0.2,
         f"{spread([p.width for p in params]):.2f}"),
        ("timbre visits >= 4 palette colours", colours >= 4, f"{colours}"),
        ("notes vary (>= 5 distinct)", len(set(degrees)) >= 5, f"{len(set(degrees))}"),
        ("melodic: most note changes are steps of 1-2", melodic >= 0.8, f"{melodic:.0%}"),
        ("hard strikes no harsher than the held tone (p90 2.5-5.5 kHz rise <= 0 dB)",
         harsh <= 0.0, f"{harsh:+.1f} dB"),
    ]
    print(f"\n{path}  ({frames[-1].t:.0f} s)")
    for name, ok, value in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {value}")
    return all(ok for _, ok, _ in checks)


if __name__ == "__main__":
    results = [evaluate(p) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
