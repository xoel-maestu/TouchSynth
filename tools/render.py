"""Render a recorded session (or the built-in simulation) to WAV, offline.

Usage:  python tools/render.py sessions/X.csv out.wav
        python tools/render.py --simulate out.wav [seconds]
Prints, per second, touch and intensity next to the audio level and brightness,
so the response to touches can be checked objectively and listened to.
"""

import csv
import sys
import wave

import numpy as np

from touchsynth.replay import SAMPLE_RATE, replay
from touchsynth.sources import UPDATE_HZ, simulated_touch


def session_readings(path):
    with open(path) as f:
        rows = [(float(r["host_s"]), float(r["intensity"]), r["touched"] == "1")
                for r in csv.DictReader(f)]
    return [(t - rows[0][0], x, touched) for t, x, touched in rows]


def simulated_readings(seconds):
    return [(i / UPDATE_HZ, *simulated_touch(i / UPDATE_HZ)) for i in range(int(seconds * UPDATE_HZ))]


def report(frames, audio):
    print("  s  touch  intensity  level dB  centroid Hz  note Hz")
    for s in range(int(frames[-1].t)):
        sec = [f for f in frames if s <= f.t < s + 1]
        seg = audio[s * SAMPLE_RATE:(s + 1) * SAMPLE_RATE].mean(axis=1)
        level = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        centroid = (spec * np.fft.rfftfreq(len(seg), 1 / SAMPLE_RATE)).sum() / (spec.sum() + 1e-12)
        touched = np.mean([f.touched for f in sec])
        print(f"{s:3d}  {touched:4.0%}   {max(f.params.gain_db for f in sec) + 30:4.0f}/30"
              f"  {level:8.1f}  {centroid:10.0f}  {sec[-1].params.root_hz:7.1f}")


def main(argv):
    if argv[0] == "--simulate":
        readings, out = simulated_readings(float(argv[2]) if len(argv) > 2 else 24.0), argv[1]
    else:
        readings, out = session_readings(argv[0]), argv[1]
    frames = list(replay(readings))
    audio = np.concatenate([f.audio for f in frames])
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((audio * 32767).astype("<i2").tobytes())
    report(frames, audio)


if __name__ == "__main__":
    main(sys.argv[1:])
