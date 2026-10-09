"""Wiring check for the Pico 2: compares GP26 (sensor node) with GP27 (unconnected).

Deploy as CIRCUITPY/code.py. With correct wiring and nobody touching, GP26 reads
near 3.3 V while GP27 floats (~0.76 V); touching the electrodes pulls GP26 down.
"""

import time

import analogio
import board

sensor = analogio.AnalogIn(board.GP26)
floating = analogio.AnalogIn(board.GP27)


def volts(pin, n=200):
    return sum(pin.value for _ in range(n)) / n * 3.3 / 65535


while True:
    print("# GP26={:.3f} V   GP27(unconnected)={:.3f} V".format(volts(sensor), volts(floating)))
    time.sleep(0.5)
