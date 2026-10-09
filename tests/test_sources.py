import io
import threading
import time
import types

from touchsynth.protocol import Reading
from touchsynth.recorder import CsvRecorder
from touchsynth.sources import SerialSource, find_pico_port, simulated_touch


def test_simulation_covers_rest_light_and_firm_touch():
    samples = [simulated_touch(i / 50) for i in range(50 * 30)]
    touched = [x for x, t in samples if t]
    assert any(not t for _, t in samples)
    assert min(touched) < 0.35
    assert max(touched) > 0.85
    assert all(0.0 <= x <= 1.0 for x, _ in samples)


def test_find_pico_port_prefers_circuitpython_devices():
    ports = [types.SimpleNamespace(device="/dev/ttyS0", vid=None),
             types.SimpleNamespace(device="/dev/ttyACM0", vid=0x239A)]
    assert find_pico_port(ports) == "/dev/ttyACM0"
    assert find_pico_port(ports[:1]) is None


class FakeSerial:
    def __init__(self, lines):
        self._lines = [line.encode() for line in lines]
        self.closed = False

    def readline(self):
        return self._lines.pop(0) if self._lines else b""

    def close(self):
        self.closed = True


def test_serial_source_delivers_parsed_readings():
    received, done = [], threading.Event()

    def on_reading(r):
        received.append(r)
        if len(received) == 2:
            done.set()

    fake = FakeSerial(["# touchsynth v1\r\n", "10,60000,0.1000,0.0800,1\r\n",
                       "garbage\r\n", "30,65535,0.0000,0.0000,0\r\n"])
    source = SerialSource("/dev/fake", on_reading, opener=lambda port: fake)
    source.start()
    assert done.wait(2.0)
    source.stop()
    assert received[:2] == [Reading(10, 60000, 0.1, 0.08, True),
                            Reading(30, 65535, 0.0, 0.0, False)]


class BrokenSerial(FakeSerial):
    def readline(self):
        if self._lines:
            return super().readline()
        raise OSError("device disconnected")


def test_unplugging_releases_the_touch_and_reconnects():
    received, opened = [], []

    def opener(port):
        opened.append(port)
        return BrokenSerial(["10,60000,0.1000,0.0800,1\r\n"])

    source = SerialSource(None, received.append, opener=opener,
                          finder=lambda: f"/dev/ttyACM{len(opened)}")
    source.start()
    deadline = time.monotonic() + 3.0
    while len(opened) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    source.stop()
    assert received[0].touched and not received[1].touched  # released on unplug
    assert opened[:2] == ["/dev/ttyACM0", "/dev/ttyACM1"]    # found again, new name


def test_recorder_writes_header_and_rows():
    buffer = io.StringIO()
    rec = CsvRecorder(buffer)
    rec.write(Reading(10, 60000, 0.1, 0.08, True), host_s=1.5)
    text = buffer.getvalue().splitlines()
    assert text[0] == "host_s,ms,raw,g_us,intensity,touched"
    assert text[1] == "1.500000,10,60000,0.1000,0.0800,1"
