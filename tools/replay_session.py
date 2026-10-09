"""Re-render a recorded session (sessions/*.csv) through the controller and synth.

Usage:  python tools/replay_session.py sessions/20261009-222233.csv out.wav
Prints, per second, touch state and intensity next to the audio level and brightness,
so the response to real touches can be checked objectively (and listened to).
"""

import csv
import sys
import wave

import numpy as np

from touchsynth.controller import TouchController
from touchsynth.sources import UPDATE_HZ
from touchsynth.synth import PadSynth

SAMPLE_RATE = 48000
BLOCK = 480  # 10 ms


def load(path):
    with open(path) as f:
        return [(float(r["host_s"]), float(r["intensity"]), r["touched"] == "1")
                for r in csv.DictReader(f)]


def render(readings):
    t0 = readings[0][0]
    readings = [(t - t0, x, touched) for t, x, touched in readings]
    synth, ctrl = PadSynth(SAMPLE_RATE), TouchController(UPDATE_HZ)
    blocks, i, t = [], 0, 0.0
    while t < readings[-1][0]:
        while i < len(readings) and readings[i][0] <= t:
            ctrl.update(readings[i][1], readings[i][2], readings[i][0])
            i += 1
        params, gate = ctrl.current(t)
        blocks.append(synth.render(BLOCK, params, gate))
        t += BLOCK / SAMPLE_RATE
    return readings, np.concatenate(blocks)


def report(readings, audio):
    print("  s  touch  intensity   level dB   centroid Hz")
    for s in range(int(readings[-1][0])):
        sec = [r for r in readings if s <= r[0] < s + 1]
        seg = audio[s * SAMPLE_RATE:(s + 1) * SAMPLE_RATE].mean(axis=1)
        level = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        centroid = (spec * np.fft.rfftfreq(len(seg), 1 / SAMPLE_RATE)).sum() / (spec.sum() + 1e-12)
        touched = sum(r[2] for r in sec) / max(1, len(sec))
        intensity = max((r[1] for r in sec), default=0.0)
        print(f"{s:3d}  {touched:4.0%}    {intensity:5.2f}    {level:7.1f}    {centroid:8.0f}")


def main(csv_path, wav_path):
    readings, audio = render(load(csv_path))
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((audio * 0.8 * 32767).astype("<i2").tobytes())
    report(readings, audio)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
