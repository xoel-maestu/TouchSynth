# TouchSynth

[![CI](https://github.com/xoel-maestu/touchsynth/actions/workflows/ci.yml/badge.svg)](https://github.com/xoel-maestu/touchsynth/actions/workflows/ci.yml)

A touch instrument for two people. Each player holds one electrode; when they
touch skin to skin, a Raspberry Pi Pico 2 measures the conductance of the contact
and a Python synthesiser turns it into a continuous ambient pad that **responds
to how they touch**: soft or firm, fast or slow, trembling or still, letting go
abruptly or gently. The timbre morphs and the notes walk a pentatonic scale with
every touch, so the instrument never sounds the same twice.

## Features

- **Skin-conductance sensing** on a Pico 2 with three parts: a resistor, two
  electrodes and the board's ADC. Mains hum is cancelled by averaging over
  exactly one 50 Hz period.
- **Adaptive sensitivity**: the intensity range follows the players' recent
  touches, so dry or damp skin, evening or night, all reach the full range
  without manual calibration.
- **Expressive gestures**: strike speed, squeeze, tremor, hold time and how
  slowly you let go each drive their own sound dimension.
- **One-to-many perceptual mapping**: one touch moves loudness, brightness,
  harmonic layers, saturation, reverb and stereo width along perceptual curves.
- **Never the same twice**: a five-colour timbre palette and a melodic
  pentatonic note walk.
- **Gentle by design**: a felt-mallet modal accent on strikes with no energy in
  the 2.5–5.5 kHz band rated most unpleasant, a −3 dBFS peak limiter, and
  speaker profiles that keep small speakers clean.
- **Low latency**: touch detected within one 20 ms window, strike attack ~12 ms.
- **Session logging and offline tools**: every session is recorded to CSV and
  can be rendered to WAV or scored with objective checks.
- **Runs without hardware** via a built-in gesture simulation.

## How it works

```
 Person A ── electrode A ─┐                      ┌─ Pico 2 ── USB serial ── PC (Python)
                          ├─ skin-to-skin touch ─┤   conductance,          gestures → pad synth
 Person B ── electrode B ─┘                      └─ intensity, touch        → speakers, CSV log
```

The firmware reports one line per 20 ms window (`ms,raw,g_us,intensity,touched`).
Skin resistance spans orders of magnitude (light fingertip ≈ MΩ, firm palm
≈ 100 kΩ), so intensity is the *logarithm* of the skin conductance between the
touch threshold and an adaptive "firm contact" top. On the PC, a gesture tracker
extracts strike, press, tremor, hold and lift features, and a perceptual mapping
drives an additive pad with an FDN reverb. See
[docs/architecture.md](docs/architecture.md).

## Hardware

| Part | Value | Note |
|---|---|---|
| Raspberry Pi Pico 2 | RP2350, CircuitPython 10 | |
| R1 (pull-up) | 1 MΩ | 470 kΩ – 2.2 MΩ also work |
| R2 (series) | 100 kΩ, optional | ESD protection |
| C1 | 10 nF, optional | steadies the ADC node |
| 2 electrodes | metal plates/tubes, copper tape, wristbands | larger and gripped with the whole hand is better |
| Wires, breadboard | | |

Wiring, breadboard layout, electrode advice, safety notes and troubleshooting:
[docs/hardware.md](docs/hardware.md).

## Quick start

Requires [uv](https://docs.astral.sh/uv/) on the PC.

1. **Flash CircuitPython**: download the UF2 for the
   [Raspberry Pi Pico 2](https://circuitpython.org/board/raspberry_pi_pico2/),
   hold **BOOTSEL** while plugging the board in, and copy the file to the
   `RP2350` drive. It reboots as `CIRCUITPY`.
2. **Deploy the firmware** (boot the board without touching the electrodes):

   ```bash
   tools/deploy.sh                 # auto-detects the CIRCUITPY drive
   ```

3. **Run the synth**:

   ```bash
   uv sync                         # once: creates .venv with Python 3.12
   uv run touchsynth               # finds the Pico (and waits for it)
   uv run touchsynth --simulate    # no hardware: scripted gesture
   ```

The board LED lights while there is contact, and the terminal meter shows the
intensity and the measured conductance `G`.

## Usage

```bash
uv run touchsynth [--simulate] [--port PORT] [--volume 0..1] [--device DEVICE]
                  [--speakers small|full] [--list-devices] [--no-record]
```

| Flag | Meaning |
|---|---|
| `--simulate` | play a looping 24 s gesture script instead of reading the Pico |
| `--port` | serial port of the Pico (auto-detected by USB vendor ID by default) |
| `--volume` | master volume, 0..1 (default 0.7) |
| `--device` | audio output device, by name or index |
| `--list-devices` | list audio devices and exit |
| `--speakers small` | default; laptops, monitors, small speakers: 120 Hz high-pass, no sub-oscillator |
| `--speakers full` | headphones or hi-fi: 25 Hz high-pass, sub-oscillator enabled |
| `--no-record` | do not write a session CSV |

Sessions are logged to `sessions/YYYYMMDD-HHMMSS.csv`
(`host_s,ms,raw,g_us,intensity,touched`).

**Bluetooth speakers** work through PipeWire like any other output: connect the
speaker and make it the default sink (e.g. `pactl set-default-sink
bluez_output.<MAC>.1`). A2DP adds roughly 150–250 ms of latency, so wired
output feels more immediate.

Offline tools:

```bash
uv run python tools/render.py --simulate demo.wav          # listen without hardware
uv run python tools/render.py sessions/X.csv out.wav        # re-listen to a session
uv run python tools/evaluate_sessions.py sessions/*.csv     # objective checks
```

## Documentation

| Page | Contents |
|---|---|
| [Hardware](docs/hardware.md) | BOM, wiring, breadboard guide, electrodes, safety, adaptive sensitivity, flashing, troubleshooting |
| [Sound design](docs/sound-design.md) | gesture → sound mapping, strike accent, timbre palette, note walk, speaker profiles, latency |
| [Architecture](docs/architecture.md) | modules, serial protocol, data flow, threading model, testing strategy |
| [Validation](docs/validation.md) | measurements on the real Pico 2 and how to reproduce them |
| [Research](docs/research.md) | references that informed the design |

## Development

```bash
uv sync                 # install runtime and dev dependencies
uv run pytest           # unit tests, firmware on CPython, real-session regression
uv run ruff check       # lint
```

The firmware's sensing core (`firmware/lib/touchcore.py`) is pure Python and is
tested on the PC; `firmware/code.py` itself runs in the test suite against
stubbed CircuitPython modules.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `docs:` …). See [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

## License

To be decided — all rights reserved until a license is chosen.

## Acknowledgements and references

TouchSynth builds on published work in musical interaction and psychoacoustics,
among others: Hunt & Wanderley's mapping strategies (NIME 2002), the 1€ filter
(Casiez et al., CHI 2012), Wessel & Wright's latency guidelines, the ROLI
Seaboard's "5D touch", Perry Cook's STK ModalBar, Jot's feedback delay
networks, and Kumar et al. (2008) on unpleasant sounds. The full list, with how
each one shaped the design, is in [docs/research.md](docs/research.md).
