"""Where touch readings come from: the Pico over USB serial, or a simulation."""

import math
import sys
import threading
import time
from typing import Callable, Iterable, Optional

from touchsynth.protocol import Reading, parse_line

CIRCUITPYTHON_VIDS = (0x239A, 0x2E8A)  # Adafruit, Raspberry Pi
UPDATE_HZ = 50.0  # firmware sends one reading per 20 ms window (slightly less in practice)
SIMULATION_PERIOD_S = 24.0
RETRY_S = 1.0

OnReading = Callable[[Reading], None]
RELEASED = Reading(0, 0, 0.0, 0.0, False)


def find_pico_port(ports: Optional[Iterable] = None) -> Optional[str]:
    if ports is None:
        from serial.tools.list_ports import comports
        ports = comports()
    for port in ports:
        if port.vid in CIRCUITPYTHON_VIDS:
            return port.device
    return None


def _open_serial(port: str):
    import serial
    return serial.Serial(port, 115200, timeout=0.5)


class _ThreadedSource:
    """Runs `_run` in a daemon thread until `stop()`."""

    port = ""
    connected = False

    def __init__(self, on_reading: OnReading):
        self._on_reading = on_reading
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        raise NotImplementedError


class SerialSource(_ThreadedSource):
    """Reads the Pico; on any failure releases the touch and reconnects.

    With `port=None` the Pico is looked up again on every attempt, so a replug
    that comes back under another name (ttyACM1) is still found.
    """

    def __init__(self, port: Optional[str], on_reading: OnReading,
                 opener=_open_serial, finder=find_pico_port):
        super().__init__(on_reading)
        self._fixed_port = port
        self._opener = opener
        self._finder = finder
        self.port = port or "auto"

    def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                port = self._fixed_port or self._finder()
                if port is None:
                    raise OSError("Pico not found")
                link = self._opener(port)
            except Exception:
                self._stopping.wait(RETRY_S)
                continue
            self.port, self.connected = port, True
            try:
                self._pump(link)
            except Exception as error:  # unplugged, or a bug downstream: keep going
                print(f"\nserial: {error!r}", file=sys.stderr)
            finally:
                self.connected = False
                _quietly(link.close)
                _quietly(self._on_reading, RELEASED)
            self._stopping.wait(RETRY_S)

    def _pump(self, link) -> None:
        while not self._stopping.is_set():
            reading = parse_line(link.readline().decode("ascii", errors="ignore"))
            if reading is not None:
                self._on_reading(reading)


def _quietly(fn, *args) -> None:
    """Best-effort cleanup call: a failure here must not kill the reader thread."""
    try:
        fn(*args)
    except Exception as error:
        print(f"\nserial: {error!r}", file=sys.stderr)


def simulated_touch(t: float) -> tuple[float, bool]:
    """A looping 24 s gesture script: rest, light touch, slow press, rest, slaps."""
    t %= SIMULATION_PERIOD_S
    jitter = 0.02 * math.sin(2 * math.pi * 7.3 * t)
    if t < 2:
        intensity, touched = 0.0, False
    elif t < 6:      # light fingertip with small pressure wobble
        intensity, touched = 0.25 + 0.05 * math.sin(2 * math.pi * 0.5 * t) + jitter, True
    elif t < 12:     # slowly pressing into a full palm and back
        intensity, touched = 0.25 + 0.7 * math.sin(math.pi * (t - 6) / 6) + jitter, True
    elif t < 15:
        intensity, touched = 0.0, False
    elif (t - 15) % 3.0 < 1.0:  # three slaps of 1 s
        intensity, touched = 0.9 + jitter, True
    else:
        intensity, touched = 0.0, False
    return max(0.0, min(1.0, intensity)), touched


class SimulatedSource(_ThreadedSource):
    """Feeds `simulated_touch` at the firmware's update rate, for use without a Pico."""

    port = "simulation"
    connected = True

    def _run(self) -> None:
        start = time.monotonic()
        tick = 0
        while not self._stopping.is_set():
            t = tick / UPDATE_HZ
            intensity, touched = simulated_touch(t)
            self._on_reading(Reading(int(t * 1000), 0, 0.0, intensity, touched))
            tick += 1
            self._stopping.wait(max(0.0, start + tick / UPDATE_HZ - time.monotonic()))
