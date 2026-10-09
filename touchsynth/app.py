"""TouchSynth host: Pico readings -> controller -> pad synth -> speakers (+ CSV log).

Usage:  python -m touchsynth [--simulate] [--port /dev/ttyACM0] [--volume 0.7]
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

import sounddevice as sd

from touchsynth.controller import TouchController
from touchsynth.protocol import Reading
from touchsynth.recorder import CsvRecorder
from touchsynth.sources import RELEASED, UPDATE_HZ, SerialSource, SimulatedSource
from touchsynth.synth import PadSynth

SAMPLE_RATE = 48000
BLOCK_SIZE = 256  # 5.3 ms
SESSIONS_DIR = Path("sessions")


def parse_args(argv):
    p = argparse.ArgumentParser(prog="touchsynth", description=__doc__.splitlines()[0])
    p.add_argument("--simulate", action="store_true", help="play a scripted gesture, no Pico needed")
    p.add_argument("--port", help="serial port of the Pico (auto-detected by default)")
    p.add_argument("--volume", type=float, default=0.7, help="master volume 0..1")
    p.add_argument("--device", help="audio output device (name or index, see --list-devices)")
    p.add_argument("--speakers", choices=("small", "full"), default="small",
                   help="small: monitor/laptop speakers (no deep bass, default); "
                        "full: headphones or hi-fi")
    p.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    p.add_argument("--no-record", action="store_true", help="do not write a session CSV")
    return p.parse_args(argv)


def meter(reading: Reading, connected: bool) -> str:
    if not connected:
        return "waiting for the Pico...".ljust(60)
    bar = "#" * int(reading.intensity * 30)
    state = "TOUCH" if reading.touched else "  -  "
    return f"{state} |{bar:<30}| {reading.intensity:4.2f}  G={reading.g_us:7.3f} uS"


def open_recorder() -> CsvRecorder:
    SESSIONS_DIR.mkdir(exist_ok=True)
    path = SESSIONS_DIR / f"{datetime.datetime.now():%Y%m%d-%H%M%S}.csv"
    print(f"recording to {path}")
    return CsvRecorder(path.open("w", buffering=1))  # line-buffered: survives a crash


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.list_devices:
        print(sd.query_devices())
        return 0

    controller = TouchController(UPDATE_HZ)
    synth = PadSynth(SAMPLE_RATE, speakers=args.speakers)
    volume = max(0.0, min(1.0, args.volume))
    device = int(args.device) if args.device and args.device.isdigit() else args.device
    recorder = None if args.no_record else open_recorder()
    last_reading = RELEASED
    underflows = callback_errors = 0

    def on_reading(reading: Reading) -> None:
        nonlocal last_reading
        now = time.monotonic()
        controller.update(reading.intensity, reading.touched, now)
        last_reading = reading
        if recorder:
            recorder.write(reading, now)

    def callback(outdata, frames, time_info, status):
        nonlocal underflows, callback_errors
        underflows += bool(status.output_underflow)
        try:
            params, gate = controller.current(time.monotonic())
            outdata[:] = synth.render(frames, params, gate) * volume
        except Exception:  # never let the audio thread die; reported on exit
            callback_errors += 1
            outdata.fill(0)

    source = (SimulatedSource(on_reading) if args.simulate
              else SerialSource(args.port, on_reading))
    print(f"source: {source.port}   (Ctrl+C to quit)")
    source.start()
    try:
        with sd.OutputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, channels=2,
                             dtype="float32", latency="low", device=device,
                             callback=callback):
            while True:
                print("\r" + meter(last_reading, source.connected), end="", flush=True)
                time.sleep(0.1)
    except KeyboardInterrupt:
        print()
    finally:
        source.stop()
        if recorder:
            recorder.close()
        if underflows:
            print(f"warning: {underflows} audio underflows (close other audio apps)")
        if callback_errors:
            print(f"error: the synth failed in {callback_errors} audio blocks")
    return 0
