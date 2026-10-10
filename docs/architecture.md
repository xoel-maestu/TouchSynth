# Architecture

TouchSynth has two halves: a small CircuitPython firmware on the Pico 2 that
turns the ADC into a clean touch signal, and a Python host program that turns
that signal into sound.

## Module map

```
firmware/code.py           Pico: 20 ms ADC windows (cancel 50 Hz hum) → touchcore → USB serial
firmware/lib/touchcore.py  conductance, log scale, resting baseline, hysteresis, adaptive top
                           (pure Python: runs on CircuitPython and CPython)

touchsynth/protocol.py     serial line format: Reading, parse_line, format_line
touchsynth/sources.py      serial reader with auto-detection and reconnection; simulator
touchsynth/gestures.py     gesture features: strike, press, tremor, fall time, hold time
touchsynth/smoothing.py    1€ filter for the control signal
touchsynth/variation.py    timbre palette position and pentatonic note walk
touchsynth/controller.py   gestures + variation → parameters and envelopes
touchsynth/mapping.py      one-to-many perceptual mapping → SynthParams
touchsynth/synth.py        additive pad (timbre palette, analytic lowpass) + FDN reverb
touchsynth/accent.py       felt-mallet modal accent for strikes
touchsynth/output.py       speaker-profile high-pass + peak limiter
touchsynth/recorder.py     session CSV
touchsynth/replay.py       offline rendering of readings (sessions, simulation)
touchsynth/app.py          CLI, audio stream, terminal meter

tools/deploy.sh            copy the firmware to the CIRCUITPY drive
tools/wiring_check.py      on-board check of the sensor node (GP26 vs floating GP27)
tools/diag_code.py         on-board GP26 pad-register and ADC diagnostic
tools/render.py            render a session or the simulation to WAV, with a per-second report
tools/evaluate_sessions.py replay sessions through the whole pipeline and score them
```

## Data flow

```
 ADC (10 kHz) ─► 200-sample mean ─► TouchSensor.update ─► serial line
                 (one 50 Hz period)  conductance, intensity,   ms,raw,g_us,intensity,touched
                                     touched
                                              │ USB serial (115200)
                                              ▼
 SerialSource ─► parse_line ─► TouchController.update ─► (immutable state)
 (sensor thread)               GestureTracker, 1€ filter,
                               Variation                        │
                                                                ▼
 audio callback ─► TouchController.current ─► map_intensity ─► PadSynth.render
 (every 512 frames)  envelopes evaluated        SynthParams      pad + accent + reverb
                     at audio time                               → high-pass → limiter
```

### Firmware

`firmware/code.py` samples GP26 at 10 kHz with `analogbufio` and averages
windows of 200 samples. 200 samples at 10 kHz is exactly one 50 Hz mains
period, so the boxcar average cancels hum at 50, 100 and 150 Hz. Each window
mean goes through `TouchSensor.update` (`firmware/lib/touchcore.py`), which:

1. converts the reading to the node conductance with the divider model;
2. subtracts the learned resting baseline and the optional series resistor;
3. applies the touch thresholds with hysteresis and debounce;
4. maps the logarithm of the skin conductance onto 0..1 against the adaptive
   top (see [hardware.md](hardware.md#adaptive-sensitivity)).

The board LED mirrors the touch state.

### Serial protocol

One ASCII line per 20 ms window:

```
ms,raw,g_us,intensity,touched
```

| Field | Meaning |
|---|---|
| `ms` | Pico monotonic clock, milliseconds |
| `raw` | 20 ms mean of the ADC, 0..65535 |
| `g_us` | skin-path conductance, µS |
| `intensity` | 0..1, log-conductance within the adaptive range |
| `touched` | `1` or `0` |

Lines starting with `#` are comments; the firmware announces itself with
`# touchsynth v1 fields=ms,raw,g_us,intensity,touched`. Malformed or
non-finite lines are discarded by `parse_line`.

### Sources

`SerialSource` finds the Pico by USB vendor ID (Adafruit or Raspberry Pi),
reads lines in a daemon thread, and on any failure reports a release (so the
sound never keeps droning), waits one second and reconnects, looking the port
up again, so a replug that comes back under another name is still found.
`SimulatedSource` plays a looping 24 s gesture script at the same rate.

### Controller

`TouchController.update` runs on the sensor thread for every reading:

- `GestureTracker` extracts strike (fastest rise in the first 40 ms), press
  (intensity above a slow per-touch baseline), tremor (RMS of the 3+ Hz band),
  hold time and fall time, from the unsmoothed intensity.
- A 1€ filter smooths the level that drives the pad.
- `Variation` advances the timbre palette and the note walk on each new touch
  (ignoring contact glitches shorter than 150 ms).
- The gate envelope's attack follows the strike speed and its release follows
  how slowly the players let go.

`TouchController.current` runs in the audio callback: it evaluates the
envelopes analytically at the current time and calls `map_intensity` to
produce a `SynthParams`.

### Synth and output

`PadSynth.render` ramps every parameter linearly across the block, renders six
additive voices (three detuned roots, fifth, octave, and the two-octaves-up
shimmer), the optional sub-oscillator, slow LFO motion, `tanh` saturation, the
gate, the strike accent and the FDN reverb, and finally the speaker-profile
high-pass and the peak limiter. The details are in
[sound-design.md](sound-design.md).

## Threading model

There are two threads that matter: the **sensor thread** (serial reader) and
the **audio callback** (PortAudio, via `sounddevice`). They share no locks.

- The controller and the variation state are each one **immutable
  `NamedTuple`**, rebuilt by the sensor thread and swapped in with a single
  attribute assignment, which is atomic in CPython.
- The audio callback only reads the current tuple and computes everything else
  from it, so it never waits for the sensor thread and never sees a
  half-updated state.
- Envelopes are stored as (start, target, time constant, start time) and
  evaluated at audio time, so the sound stays smooth between 50 Hz sensor
  updates and adds no latency.
- If readings stop for more than 250 ms mid-touch, the gate decays on its own.
- The callback catches any exception and outputs silence for that block (the
  count is reported on exit), so the audio stream never dies.

Audio runs at 48 kHz in **512-frame blocks** (10.7 ms) with a **30 ms output
buffer**. These settings ran without underflows alongside the serial reader on
the real hardware (see [validation.md](validation.md)).

## Offline tools

`touchsynth/replay.py` feeds `(t, intensity, touched)` readings to a fresh
controller at their original times and renders the synth block by block, with
a fixed random seed so renders are reproducible. It is shared by:

- `tools/render.py`: writes a WAV and prints, per second, touch share,
  intensity, audio level, spectral centroid and current note;
- `tools/evaluate_sessions.py`: runs nine objective checks per session and
  exits non-zero if any fails, so tuning can iterate until every recorded
  session passes.

## Testing strategy

`uv run pytest` covers three levels:

- **Unit tests** for each host module (protocol, sources, gestures, smoothing,
  variation, mapping, controller, synth, accent) and for the sensing core
  (`tests/test_touchcore.py`), which imports `firmware/lib/touchcore.py`
  directly on CPython.
- **Firmware on CPython**: `tests/test_firmware_smoke.py` runs the real
  `firmware/code.py` with stubbed `analogbufio`, `board` and `digitalio`
  modules feeding simulated ADC windows (including mains hum), and checks the
  emitted lines with the host's own parser (`touchsynth/protocol.py`), so the
  firmware and the host cannot drift apart.
- **Real-session regression**: `tests/test_real_session.py` replays a raw
  recording from the Pico 2 (`tests/data/pico2_pressure_session.csv`) through
  the sensing core and checks rest, light-touch and firm-touch phases.
