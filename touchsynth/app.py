"""TouchSynth host: Pico readings -> controller -> pad synth -> speakers (+ CSV log).

Usage:  python -m touchsynth [--simulate] [--port /dev/ttyACM0] [--volume 0.7]
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from touchsynth.controller import TouchController
from touchsynth.protocol import Reading
from touchsynth.recorder import CsvRecorder
from touchsynth.sources import UPDATE_HZ, SerialSource, SimulatedSource, find_pico_port
from touchsynth.synth import PadSynth

SAMPLE_RATE = 48000
BLOCK_SIZE = 512  # 10.7 ms
SESSIONS_DIR = Path("sessions")


def parse_args(argv):
    p = argparse.ArgumentParser(prog="touchsynth", description=__doc__.splitlines()[0])
    p.add_argument("--simulate", action="store_true", help="play a scripted gesture, no Pico needed")
    p.add_argument("--port", help="serial port of the Pico (auto-detected by default)")
    p.add_argument("--volume", type=float, default=0.7, help="master volume 0..1")
    p.add_argument("--device", help="audio output device (name or index)")
    p.add_argument("--no-record", action="store_true", help="do not write a session CSV")
    return p.parse_args(argv)


def _meter(reading: Reading, connected: bool) -> str:
    if not connected:
        return "waiting for the Pico...".ljust(60)
    bar = "#" * int(reading.intensity * 30)
    state = "TOUCH" if reading.touched else "  -  "
    return f"{state} |{bar:<30}| {reading.intensity:4.2f}  G={reading.g_us:7.3f} uS"


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    controller = TouchController(UPDATE_HZ)
    synth = PadSynth(SAMPLE_RATE)
    volume = max(0.0, min(1.0, args.volume))
    device = int(args.device) if args.device and args.device.isdigit() else args.device
    last = {"reading": Reading(0, 0, 0.0, 0.0, False)}
    underflows = [0]

    recorder = None
    if not args.no_record:
        SESSIONS_DIR.mkdir(exist_ok=True)
        path = SESSIONS_DIR / f"{datetime.datetime.now():%Y%m%d-%H%M%S}.csv"
        recorder = CsvRecorder(path.open("w", buffering=1 << 16))
        print(f"recording to {path}")

    def on_reading(reading: Reading) -> None:
        now = time.monotonic()
        controller.update(reading.intensity, reading.touched, now)
        last["reading"] = reading
        if recorder:
            recorder.write(reading, now)

    def callback(outdata, frames, time_info, status):
        if status.output_underflow:
            underflows[0] += 1
        try:
            params, gate = controller.current(time.monotonic())
            outdata[:] = synth.render(frames, params, gate) * volume
        except Exception:  # never let the audio thread die
            outdata.fill(0)

    if args.simulate:
        source = SimulatedSource(on_reading)
    else:
        port = args.port or find_pico_port()
        if port is None:
            print("No Pico found. Plug it in, pass --port, or use --simulate.")
            return 1
        source = SerialSource(port, on_reading)
    print(f"source: {source.port}   (Ctrl+C to quit)")

    source.start()
    try:
        with sd.OutputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, channels=2,
                             dtype="float32", latency="low", device=device,
                             callback=callback):
            while True:
                print("\r" + _meter(last["reading"], source.connected), end="", flush=True)
                time.sleep(0.1)
    except KeyboardInterrupt:
        print()
    finally:
        source.stop()
        if recorder:
            recorder.close()
        if underflows[0]:
            print(f"warning: {underflows[0]} audio underflows (try a larger --device buffer or close other apps)")
    return 0
