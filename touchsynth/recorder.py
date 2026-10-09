"""Session logging: every reading to CSV, for later analysis."""

from typing import TextIO

from touchsynth.protocol import Reading, format_line

HEADER = "host_s,ms,raw,g_us,intensity,touched"


class CsvRecorder:
    def __init__(self, stream: TextIO):
        self._stream = stream
        self._stream.write(HEADER + "\n")

    def write(self, reading: Reading, host_s: float) -> None:
        self._stream.write(f"{host_s:.6f},{format_line(reading)}\n")

    def close(self) -> None:
        self._stream.close()
