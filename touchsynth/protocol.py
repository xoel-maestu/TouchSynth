"""Line protocol sent by the Pico firmware: `ms,raw,g_us,intensity,touched`.

Lines starting with '#' are comments (the firmware announces itself with one).
"""

from typing import NamedTuple, Optional


class Reading(NamedTuple):
    ms: int            # Pico monotonic clock
    raw: int           # 20 ms mean of the ADC, 0..65535
    g_us: float        # skin-path conductance, microsiemens
    intensity: float   # 0..1, log-conductance in the adaptive range
    touched: bool


def format_line(r: Reading) -> str:
    return f"{r.ms},{r.raw},{r.g_us:.4f},{r.intensity:.4f},{int(r.touched)}"


def parse_line(line: str) -> Optional[Reading]:
    fields = line.strip().split(",")
    if len(fields) != 5:
        return None
    try:
        return Reading(int(fields[0]), int(fields[1]), float(fields[2]),
                       float(fields[3]), fields[4] == "1")
    except ValueError:
        return None
