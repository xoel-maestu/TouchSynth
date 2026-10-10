# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-10

First public version, released under the MIT License.

### Added

- Pico 2 firmware (CircuitPython 10) that measures skin-to-skin conductance
  with a single resistor divider. It averages over exactly one 50 Hz mains
  period, subtracts the resting baseline and streams
  `ms,raw,g_us,intensity,touched` over USB serial.
- Adaptive sensitivity: the intensity range follows the players' recent touch
  peaks, so dry or damp skin both reach the full range.
- Host synthesiser in Python:
  - gesture features (strike, press, tremor, hold, lift);
  - a one-to-many perceptual mapping;
  - an additive pad with a five-colour timbre palette;
  - a pentatonic note walk;
  - a felt-mallet modal strike accent;
  - an FDN reverb;
  - speaker profiles and a −3 dBFS peak limiter.
- Serial source with automatic reconnection, a built-in gesture simulation and
  CSV session logging.
- Tools:
  - deploy to the board;
  - check the wiring;
  - render a session or the simulation to WAV;
  - score recorded sessions against objective checks.
- Test suite: unit tests, the firmware running on CPython with stubbed
  CircuitPython modules, and a real-session regression fixture.

[Unreleased]: https://github.com/xoel-maestu/touchsynth/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/xoel-maestu/touchsynth/releases/tag/v1.0.0
