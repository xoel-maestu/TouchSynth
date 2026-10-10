"""TouchSynth firmware for the Raspberry Pi Pico 2 (CircuitPython 10).

Measures skin-to-skin contact between two people and streams, over USB serial,
one line per 20 ms window:  ms,raw,g_us,intensity,touched

Wiring (see README):  3V3 -- 1 MΩ -- GP26 -- [R2 100 kΩ, optional] -- electrode A
                      GP26 -- [10 nF, optional] -- AGND        electrode B -- GND
"""

import array
import time

import analogbufio
import board
import digitalio
from touchcore import TouchSensor

R_PULLUP = 1_000_000   # change if you fit a different resistor (470 kΩ / 2.2 MΩ)
R_SERIES = 0          # 100_000 if you fit the optional R2 (ESD protection)
G_MAX_US = 0.8        # firm contact = intensity 1.0; calibrated on bare jumper-pin electrodes (README)
SAMPLE_RATE = 10_000
WINDOW = 200           # 200 samples @ 10 kHz = 20 ms = one 50 Hz mains period

adc = analogbufio.BufferedIn(board.GP26, sample_rate=SAMPLE_RATE)
samples = array.array("H", [0] * WINDOW)
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
sensor = TouchSensor(R_PULLUP, R_SERIES, update_hz=SAMPLE_RATE / WINDOW, g_max_us=G_MAX_US)

print("# touchsynth v1 fields=ms,raw,g_us,intensity,touched")
while True:
    if adc.readinto(samples) < WINDOW:   # ADC error: the tail of the buffer is invalid
        continue
    raw = sum(samples) // WINDOW   # boxcar over one mains period cancels 50/100/150 Hz hum
    g_us, intensity, touched = sensor.update(raw)
    led.value = touched
    print(f"{time.monotonic_ns() // 1_000_000},{raw},{g_us:.4f},{intensity:.4f},{int(touched)}")
