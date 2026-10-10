# TouchSynth

A touch instrument for two people. Each person holds one electrode; when they
touch skin to skin, a continuous ambient pad sounds and **responds to how they
touch**: soft or firm, fast or slow, more or less contact, trembling or still,
letting go abruptly or slowly. The timbre morphs and the notes walk a pentatonic
scale with each touch, so it never sounds the same twice.

```
 Person A ── electrode A ─┐                      ┌─ Pico 2 ── USB ── PC (Python)
                          ├─ skin-to-skin touch ─┤   measures        synthesises, logs CSV
 Person B ── electrode B ─┘                      └─ conductance
```

## Why the original version did not respond to touch intensity

1. **The sensor never reached the ADC.** On the original breadboard GP26 read
   the same as an unconnected pin (~0.76 V).
2. **Linear mapping of a logarithmic quantity.** Skin-to-skin resistance spans
   orders of magnitude (light touch ≈ 1–10 MΩ, firm palm ≈ 50–300 kΩ). A linear
   reading squeezed almost the whole musical range into a sliver, inverted.
3. **Barely perceptible sound parameters.** +20 Hz of pitch and a linear
   300→2100 Hz filter are hard to hear. Now one gesture drives many parameters
   along perceptual curves (Hunt & Wanderley, NIME 2002).
4. **Mains hum (50 Hz) on a high-impedance ADC**, with no averaging.
5. **Sluggish smoothing** (easing off took 720 ms) and pyo broken in the
   environment (missing `libjack`): replaced by numpy + sounddevice.

## Hardware

| Part | Value | Note |
|---|---|---|
| Raspberry Pi Pico 2 | RP2350 + CircuitPython 10.0.3 | `.uf2` kept locally, not in git |
| R1 (pull-up) | **1 MΩ** | adjustable after calibration (470 kΩ – 2.2 MΩ) |
| R2 (series) | 100 kΩ, **optional** | ESD protection; if fitted set `R_SERIES = 100_000` in `code.py` |
| C1 | 10 nF (`103`), **optional** | steadies the ADC; not required (the resting baseline is subtracted) |
| 2 electrodes | metal plates/tubes, copper tape, wristbands | bigger and held in the whole hand is better |
| Wires, breadboard | | from the kit |

## Wiring

```
3V3(OUT) pin 36 ──[ R1 1 MΩ ]──┬── GP26/ADC0 pin 31
                               ├──[ C1 10 nF, optional ]── AGND pin 33
                               └──[ R2 100 kΩ, optional ]── electrode A  (person A)

GND pin 38 ────────────────────────────────────── electrode B  (person B)
```

Counting breadboard rows (USB at the top, right-hand column of the Pico): if the
first pin next to the USB (VBUS, pin 40) is on row N → GND = N+2,
3V3(OUT) = N+4, AGND = N+7, **GP26 = N+9**. Connect nothing to N (5 V) or N+3
(3V3_EN switches the board off). See `docs/breadboard_setup.jpeg`.

**Wiring check:** copy `tools/wiring_check.py` to the board as `code.py`.
Untouched, GP26 must read ≈ 3.3 V; if it reads the same as GP27 (~0.76 V), GP26
is floating.

- Each person **grips their electrode with the whole hand** (or a wristband), so
  the grip resistance is low and steady and what changes is the contact between
  them.
- Connect nothing else to GP26 (no `DigitalInOut` on that pin).
- Safety: at most 3.3 V / 1 MΩ ≈ 3 µA, below the 10 µA IEC 60601-1 limit for
  applied parts. Use a laptop on battery or a good USB supply; do not use with
  implanted medical devices.

### Calibration (2 minutes, recommended)

1. Start the synth (below). The meter shows `G=… uS` (conductance).
2. Touch with a **firm palm** for a few seconds and note `G`.
3. Put that value in `G_MAX_US` in `firmware/code.py` and redeploy. That contact
   becomes intensity 1.0; the lightest detected touch (33 MΩ) is 0. Current
   value: **0.8 µS**, measured with bare jumper-pin electrodes (one person
   pinching: light 0.1–0.3 µS, firm 0.4–0.65 µS). Larger electrodes or palms read
   much higher (up to ~10 µS): recalibrate.
4. Boot the Pico **without touching the electrodes**: it learns the resting
   conductance (the ADC's own load, ~0.07 µS) and always subtracts it. If someone
   keeps a better contact for more than 3 s the top stretches, and it relaxes
   back over a few minutes; one-off spikes are ignored.

### Optional: choosing R1 with a multimeter

Each person holds one multimeter probe (Ω range) and they touch: note the
reading for a light touch (`R_light`) and a firm palm (`R_firm`). The best R1 is
`√(R_light · R_firm)` (maximum sensitivity on a log scale). If it is far from
1 MΩ, fit the nearest standard value and change `R_PULLUP` in `firmware/code.py`.

## Deploying to the Pico 2

1. (First time only) Hold **BOOTSEL** while plugging in → the `RP2350` drive
   appears → copy `adafruit-circuitpython-raspberry_pi_pico2-en_US-10.0.3.uf2`.
   It reboots as `CIRCUITPY`.
2. `tools/deploy.sh` (or copy `firmware/code.py` → `CIRCUITPY/code.py` and
   `firmware/lib/touchcore.py` → `CIRCUITPY/lib/`).
3. The board LED lights while there is contact. Raw data:
   `screen /dev/ttyACM0` (`ms,raw,g_us,intensity,touched`).

## Running the synth (PC)

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                              # once: creates .venv with Python 3.12 and dependencies
uv run touchsynth                    # finds the Pico (and waits for it)
uv run touchsynth --simulate         # no hardware: scripted gesture
uv run touchsynth --port /dev/ttyACM0 --volume 0.5 --device pipewire
uv run touchsynth --speakers full    # headphones / speakers with real bass
uv run touchsynth --list-devices     # available audio outputs
```

`--speakers small` (default) is safe on monitors, laptops and small speakers:
it removes bass they cannot reproduce (120 Hz high-pass, no sub-oscillator). The
output always goes through a −3 dBFS peak limiter.

**Bluetooth speakers** work through PipeWire like any other output: connect the
speaker and make it the default output (e.g. `pactl set-default-sink
bluez_output.<MAC>.1`). A2DP adds roughly 150–250 ms of latency, so wired output
feels more immediate.

Every session is logged to `sessions/YYYYMMDD-HHMMSS.csv`
(`host_s,ms,raw,g_us,intensity,touched`) unless `--no-record` is given.

Listen without hardware or a sound card, or re-listen to a recorded session:

```bash
uv run python tools/render.py --simulate demo.wav
uv run python tools/render.py sessions/X.csv out.wav
uv run python tools/evaluate_sessions.py sessions/*.csv  # objective checks
```

## How it responds to gestures

Each gesture feature drives its own sound dimension, so they do not fight:

| Gesture | Measured as | What changes |
|---|---|---|
| **More / less contact** | intensity (log of conductance) | gain −30…0 dB, brightness 100 Hz → 8 kHz, fifth and octave layers, saturation, reverb (distant → close) |
| **Fast strike / slow touch** | rise speed in the first 40 ms (10–35 /s) | attack 120 → 12 ms; a soft felt-mallet vibraphone note (louder and brighter for harder strikes); up to one octave of brightness, never above 3 kHz, fading over 350 ms |
| **Squeeze / ease off** | intensity above a slow per-touch baseline (ignores sweat drift) | stereo width and detune |
| **Tremble** | 3+ Hz variation over 300 ms | vibrato 0–20 cents |
| **Hold** | contact duration | a layer two octaves up grows in (τ 8 s) |
| **Let go fast / slowly** | fall time before release | tail 0.35–3 s; a fast lift throws the sound into the reverb |

**Soft strikes.** Strikes used to add a white-noise burst and extra saturation,
which sounded like a harsh "crash". They now ring a modal "felt vibe" accent
(STK ModalBar partials retuned to harmonics 1-2-4-6, pitched an octave above the
pad) with nothing in the 2.5–5.5 kHz band rated most unpleasant (Kumar et al.,
JASA 2008). On real sessions, hard strikes are 1–6 dB *softer* in that band than
the held tone (previously +2 dB harsher).

**Timbre and notes.**

- The timbre moves around a circular palette (flute → warm → hollow/clarinet →
  choir "ah" → choir "oo"). It drifts slowly and each touch pushes it (further
  for harder strikes), always gliding.
- Each new touch takes a melodic step (one degree, two for hard strikes) along a
  two-octave pentatonic scale (G2–E4) with a 50 ms portamento; after a pause of
  more than 4 s it returns to the low octave. Contact glitches (< 150 ms) change
  nothing.

A touch is detected within one 20 ms window and a release within two; squeezing
and easing off show up in ~40 ms. If the cable is pulled, the sound fades out
(it never keeps droning).

## Architecture

```
firmware/code.py          Pico: 20 ms windows (cancel 50 Hz hum) → touchcore → USB serial
firmware/lib/touchcore.py conductance, log scale, resting baseline, hysteresis (also tested on the PC)
touchsynth/sources.py     serial reader with reconnection / simulator
touchsynth/gestures.py    gesture features: strike, press, tremor, fall time, hold time
touchsynth/variation.py   timbre palette and pentatonic note walk
touchsynth/controller.py  gestures + variation → parameters and envelopes (sensor thread → lock-free audio callback)
touchsynth/mapping.py     gesture → synth parameters (perceptual curves)
touchsynth/synth.py       additive pad (timbre palette, analytic lowpass) + FDN reverb
touchsynth/accent.py      felt-mallet modal accent for strikes
touchsynth/output.py      speaker-profile high-pass + peak limiter
touchsynth/replay.py      offline rendering of readings (sessions, simulation)
touchsynth/recorder.py    session CSV
touchsynth/app.py         CLI, audio stream, terminal meter
tools/                    deploy, wiring check, render and session evaluation
docs/                     original project notes and the breadboard photo
```

Tests: `uv run pytest -q` (including the firmware run against simulated hardware).

## Verified on the real hardware (Pico 2, October 2026)

- At rest, no false touches over minutes of recording; touch and release
  detected in under 100 ms.
- Four real touch sessions pass all 9 checks in `tools/evaluate_sessions.py`
  with the final engine: no clipping, 12–17 dB of loudness range, brightness
  ×7–15, vibrato used but not saturated, varying stereo width, 4–5 timbre colours,
  6–9 distinct notes, 100 % melodic steps, and strikes no harsher than the held
  tone.
- Audio: 512-sample blocks and a 30 ms output buffer → no underflows in
  3 × 60 s with the real Pico (256 samples or "low" latency gave from 4 per
  minute up to hundreds). Control latency ~40 ms, strike attack ~12 ms.
- A recorded real session is a regression test (`tests/test_real_session.py`).

## Troubleshooting

- **Never detects contact**: check the shared GND of electrode B and that each
  person grips their electrode well; try slightly damp hands or R1 = 2.2 MΩ.
- **Always "TOUCH"**: something shorts GP26 to GND, or R1 is too small.
- **Intensity almost always 1**: `G_MAX_US` too low → recalibrate.
- **Intensity never above ~0.5**: `G_MAX_US` too high → recalibrate.
- **Stuck on "waiting for the Pico..."**: check that `/dev/ttyACM0` exists, use
  `--port`, and add your user to the `uucp` (Arch) / `dialout` (Debian) group.
  Close any `screen` session on the port.
- **Crackles**: close other audio apps; the 30 ms output buffer is in
  `touchsynth/app.py` (`OUTPUT_LATENCY_S`).
