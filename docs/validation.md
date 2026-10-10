# Validation

All figures on this page were measured on the real hardware: a Raspberry Pi
Pico 2 with the reference circuit (R1 = 1 MΩ, no R2), CircuitPython 10, and a
Linux PC, in October 2026.

## Sensing

| Measurement | Result |
|---|---|
| False touches at rest | **0** over minutes of recording |
| Touch and release detection | **< 100 ms** (touch within one 20 ms window, release within two) |
| Resting conductance (ADC sampling load) | ~0.07 µS, learned at boot and subtracted |
| Resting noise | ~0.003 µS, well below the 0.02 µS touch threshold |
| Steady-hold intensity jitter | standard deviation ~0.002 |

A raw recording of light and firm pinches from this board is kept as a
regression fixture (`tests/data/pico2_pressure_session.csv`) and replayed
through the sensing core by `tests/test_real_session.py`.

## Skin conductance variability and adaptive sensitivity

Skin conductance changes with time of day, temperature and moisture. On the
same setup and players, the median touch conductance was **0.35 µS in an
evening session** and **0.07 µS in a night session** — about 5× lower.

With a fixed intensity top, the night session would use only the bottom of
the range. With the adaptive top (2.2 × the 75th percentile of the last 12
touch peaks, see [hardware.md](hardware.md#adaptive-sensitivity)), the night
session gave:

| Night session | Fixed top | Adaptive top |
|---|---|---|
| Touches detected | 30 | **48** |
| Median intensity | 0.30 | **~0.7** |

## Sound: objective checks on real sessions

`tools/evaluate_sessions.py` replays each recorded session through the whole
host pipeline (controller, mapping, synth, output) and applies nine checks,
each stating what "good" means for a player:

| # | Check | Criterion |
|---|---|---|
| 1 | No clipping | peak ≤ −3 dBFS ceiling |
| 2 | Loudness follows touch | gain p10..p90 ≥ 8 dB |
| 3 | Brightness follows touch | cutoff p90/p10 ≥ 3 |
| 4 | Vibrato used but not saturated | p50 < 15 cents, p90 > 3 cents |
| 5 | Stereo width varies | p10..p90 ≥ 0.2 |
| 6 | Timbre varies | ≥ 4 palette colours visited |
| 7 | Notes vary | ≥ 5 distinct notes |
| 8 | Melodic | ≥ 80 % of note changes are steps of 1–2 degrees |
| 9 | Strikes are not harsh | p90 rise of 2.5–5.5 kHz energy in the first 60 ms of a touch vs. the held tone ≤ 0 dB |

Four real touch sessions pass all nine checks, with 12–17 dB of loudness range,
brightness ×7–15, vibrato used but not saturated, varying stereo width, 4–5
timbre colours, 6–9 distinct notes and 100 % melodic steps. Hard strikes are
1–6 dB *softer* in the 2.5–5.5 kHz band than the held tone.

## Audio stability and latency

| Configuration | Underflows with the real Pico streaming |
|---|---|
| 512-frame blocks, 30 ms output buffer (shipped) | **0** in 3 × 60 s |
| 256-frame blocks | 51 in 40 s under load |
| PortAudio "low" latency (~11 ms) | ~4 per minute |

Control latency from sensor to sound is ~40 ms and the strike attack is
~12 ms. See [sound-design.md](sound-design.md#latency) for the full latency
budget.

## Reproducing

Record sessions by playing the instrument (`uv run touchsynth` writes
`sessions/YYYYMMDD-HHMMSS.csv`), then:

```bash
uv run python tools/evaluate_sessions.py sessions/*.csv   # nine checks, exit code 1 on failure
uv run python tools/render.py sessions/X.csv out.wav       # listen + per-second report
uv run pytest                                               # includes the real-session regression
```

The evaluation is deterministic: replays use a fixed random seed for the
timbre and note variation.
