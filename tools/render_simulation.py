"""Render the simulated gesture script to a WAV file, offline (no Pico, no sound card).

Usage:  python tools/render_simulation.py demo.wav [seconds]
Prints, per second, the touch intensity next to the measured loudness and brightness.
"""

import sys
import wave

import numpy as np

from touchsynth.controller import TouchController
from touchsynth.sources import UPDATE_HZ, simulated_touch
from touchsynth.synth import PadSynth

SAMPLE_RATE = 48000
BLOCK = 480  # 10 ms


def main(path, seconds=24.0):
    synth, ctrl = PadSynth(SAMPLE_RATE), TouchController(UPDATE_HZ)
    blocks, t, next_reading = [], 0.0, 0.0
    while t < seconds:
        while next_reading <= t:
            x, touched = simulated_touch(next_reading)
            ctrl.update(max(0.0, min(1.0, x)), touched, next_reading)
            next_reading += 1 / UPDATE_HZ
        params, gate = ctrl.current(t)
        blocks.append(synth.render(BLOCK, params, gate))
        t += BLOCK / SAMPLE_RATE
    audio = np.concatenate(blocks)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((audio * 0.8 * 32767).astype("<i2").tobytes())
    print(" t  touch  intensity   level dB   centroid Hz")
    for s in range(int(seconds)):
        seg = audio[s * SAMPLE_RATE:(s + 1) * SAMPLE_RATE].mean(axis=1)
        level = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))  # Hann: no leakage floor
        centroid = (spec * np.fft.rfftfreq(len(seg), 1 / SAMPLE_RATE)).sum() / (spec.sum() + 1e-12)
        x, touched = simulated_touch(s + 0.5)
        print(f"{s:2d}  {'yes' if touched else ' - '}    {max(0, x):5.2f}    {level:7.1f}    {centroid:8.0f}")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 24.0)
