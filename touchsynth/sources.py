"""Where touch readings come from: the Pico over USB serial, or a simulation."""

import math
import threading
import time
from typing import Callable, Iterable, Optional

from touchsynth.protocol import Reading, parse_line

CIRCUITPYTHON_VIDS = (0x239A, 0x2E8A)  # Adafruit, Raspberry Pi
UPDATE_HZ = 50.0  # firmware sends one reading per 20 ms window
SIMULATION_PERIOD_S = 24.0

OnReading = Callable[[Reading], None]


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


class SerialSource:
    """Background thread reading the Pico; reconnects if the cable is replugged."""

    def __init__(self, port: str, on_reading: OnReading, opener=_open_serial):
        self.port = port
        self._on_reading = on_reading
        self._opener = opener
        self._running = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.connected = False

    def start(self) -> None:
        self._running.set()
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while self._running.is_set():
            try:
                link = self._opener(self.port)
            except OSError:
                self.connected = False
                time.sleep(1.0)
                continue
            self.connected = True
            try:
                self._pump(link)
            except OSError:
                self.connected = False
                time.sleep(1.0)
            finally:
                link.close()

    def _pump(self, link) -> None:
        while self._running.is_set():
            reading = parse_line(link.readline().decode("ascii", errors="ignore"))
            if reading is not None:
                self._on_reading(reading)


def simulated_touch(t: float) -> tuple[float, bool]:
    """A looping 24 s gesture script: rest, light touch, slow press, rest, slaps."""
    t %= SIMULATION_PERIOD_S
    jitter = 0.02 * math.sin(2 * math.pi * 7.3 * t)
    if t < 2:
        return 0.0, False
    if t < 6:      # light fingertip with small pressure wobble
        return 0.25 + 0.05 * math.sin(2 * math.pi * 0.5 * t) + jitter, True
    if t < 12:     # slowly pressing into a full palm and back
        return 0.25 + 0.7 * math.sin(math.pi * (t - 6) / 6) + jitter, True
    if t < 15:
        return 0.0, False
    phase = (t - 15) % 3.0   # three slaps of 1 s
    if phase < 1.0:
        return min(1.0, 0.9 + jitter), True
    return 0.0, False


class SimulatedSource:
    """Feeds `simulated_touch` at the firmware's update rate, for use without a Pico."""

    def __init__(self, on_reading: OnReading):
        self._on_reading = on_reading
        self._running = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.connected = True
        self.port = "simulation"

    def start(self) -> None:
        self._running.set()
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        start = time.monotonic()
        tick = 0
        while self._running.is_set():
            t = tick / UPDATE_HZ
            intensity, touched = simulated_touch(t)
            intensity = max(0.0, min(1.0, intensity))
            self._on_reading(Reading(int(t * 1000), 0, 0.0, intensity, touched))
            tick += 1
            time.sleep(max(0.0, start + tick / UPDATE_HZ - time.monotonic()))
