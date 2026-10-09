"""Replay recorded sessions through the whole host pipeline and score them.

Usage:  python tools/evaluate_sessions.py sessions/*.csv
Each check states what "good" means for a real player; the script exits 1 if
any check fails, so tuning can iterate until every recorded session passes.
"""

import csv
import sys

import numpy as np

from touchsynth.controller import TouchController
from touchsynth.output import CEILING
from touchsynth.sources import UPDATE_HZ
from touchsynth.synth import PadSynth
from touchsynth.variation import SCALE_ROOTS_HZ

SAMPLE_RATE = 48000
BLOCK = 512


def load(path):
    with open(path) as f:
        rows = [(float(r["host_s"]), float(r["intensity"]), r["touched"] == "1")
                for r in csv.DictReader(f)]
    t0 = rows[0][0]
    return [(t - t0, x, touched) for t, x, touched in rows]


def replay(readings, seed=0):
    ctrl, synth = TouchController(UPDATE_HZ, seed=seed), PadSynth(SAMPLE_RATE)
    frames, i, t, peak = [], 0, 0.0, 0.0
    while t < readings[-1][0]:
        while i < len(readings) and readings[i][0] <= t:
            ctrl.update(readings[i][1], readings[i][2], readings[i][0])
            i += 1
        params, gate = ctrl.current(t)
        peak = max(peak, float(np.max(np.abs(synth.render(BLOCK, params, gate)))))
        frames.append((t, gate, params, readings[i - 1][2] if i else False))
        t += BLOCK / SAMPLE_RATE
    return frames, peak


def spread(values):
    return np.percentile(values, 90) - np.percentile(values, 10) if values else 0.0


def evaluate(path):
    frames, peak = replay(load(path))
    touching = [(g, p) for _, g, p, on in frames if on and g > 0.5]
    params = [p for _, p in touching]
    degrees = [min(range(len(SCALE_ROOTS_HZ)), key=lambda d: abs(SCALE_ROOTS_HZ[d] - p.root_hz))
               for _, _, p, on in frames if on]
    notes = [d for d, prev in zip(degrees[1:], degrees) if d != prev]
    steps = [abs(b - a) for a, b in zip(notes, notes[1:])]
    checks = [
        ("no clipping (peak <= ceiling)", peak <= CEILING + 1e-6, f"{peak:.3f}"),
        ("loudness follows touch (gain p10..p90 >= 8 dB)",
         spread([p.gain_db for p in params]) >= 8, f"{spread([p.gain_db for p in params]):.1f} dB"),
        ("brightness follows touch (cutoff p90/p10 >= 3)",
         np.percentile([p.cutoff_hz for p in params], 90) / np.percentile([p.cutoff_hz for p in params], 10) >= 3,
         f"x{np.percentile([p.cutoff_hz for p in params], 90) / np.percentile([p.cutoff_hz for p in params], 10):.1f}"),
        ("vibrato is used but not saturated (p50 < 15 cents, p90 > 3)",
         np.percentile([p.vibrato_cents for p in params], 50) < 15
         and np.percentile([p.vibrato_cents for p in params], 90) > 3,
         f"p50 {np.percentile([p.vibrato_cents for p in params], 50):.1f}, "
         f"p90 {np.percentile([p.vibrato_cents for p in params], 90):.1f}"),
        ("stereo width varies (p10..p90 >= 0.2)", spread([p.width for p in params]) >= 0.2,
         f"{spread([p.width for p in params]):.2f}"),
        ("timbre visits >= 4 palette colours", len({int(p.timbre) for p in params}) >= 4,
         f"{len({int(p.timbre) for p in params})}"),
        ("notes vary (>= 5 distinct)", len(set(degrees)) >= 5, f"{len(set(degrees))}"),
        ("melodic: most note changes are steps of 1-2",
         bool(steps) and np.mean([s <= 2 for s in steps]) >= 0.8,
         f"{np.mean([s <= 2 for s in steps]):.0%}" if steps else "no changes"),
    ]
    print(f"\n{path}  ({frames[-1][0]:.0f} s)")
    for name, ok, value in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {value}")
    return all(ok for _, ok, _ in checks)


if __name__ == "__main__":
    results = [evaluate(p) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
