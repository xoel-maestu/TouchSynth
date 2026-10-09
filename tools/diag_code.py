"""Temporary diagnostic for GP26 on the Pico 2: pad register bits + ADC readings.

Deploy as CIRCUITPY/code.py, read the serial output, then redeploy firmware/code.py.
"""

import array
import time

import analogbufio
import analogio
import board

try:
    import memorymap
except ImportError:
    memorymap = None

PADS_BANK0 = 0x40038000      # RP2350 datasheet, PADS_BANK0_BASE
GPIO26_PAD = PADS_BANK0 + 0x04 + 26 * 4


def pad_bits():
    if memorymap is None:
        return "memorymap not available"
    reg = memorymap.AddressRange(start=GPIO26_PAD, length=4)
    v = int.from_bytes(reg[0:4], "little")
    return "pad=0x{:03x} ISO={} OD={} IE={} PUE={} PDE={}".format(
        v, (v >> 8) & 1, (v >> 7) & 1, (v >> 6) & 1, (v >> 3) & 1, (v >> 2) & 1)


def mean_analogio(n=200):
    with analogio.AnalogIn(board.GP26) as a:
        print("# analogio open:", pad_bits())
        return sum(a.value for _ in range(n)) // n


def mean_bufferedin():
    buf = array.array("H", [0] * 200)
    with analogbufio.BufferedIn(board.GP26, sample_rate=10_000) as a:
        print("# bufferedin open:", pad_bits())
        a.readinto(buf)
    return sum(buf) // len(buf)


time.sleep(1)
print("# boot:", pad_bits())
for _ in range(3):
    print("# analogio mean:", mean_analogio())
    print("# bufferedin mean:", mean_bufferedin())
    print("# after release:", pad_bits())
    time.sleep(0.5)
print("# diag done")
while True:
    time.sleep(1)
