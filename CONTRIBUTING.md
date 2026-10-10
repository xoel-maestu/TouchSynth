# Contributing to TouchSynth

Thanks for your interest! Bug reports, sound-design ideas, hardware variants and
pull requests are all welcome.

## Getting started

```bash
git clone https://github.com/xoel-maestu/TouchSynth.git
cd TouchSynth
uv sync                       # Python 3.12 virtualenv with runtime + dev dependencies
uv run pytest                 # all tests should pass
uv run touchsynth --simulate  # hear it without hardware
```

You need [uv](https://docs.astral.sh/uv/). A Raspberry Pi Pico 2 is only needed
for hardware work: see [docs/hardware.md](docs/hardware.md).

## Development workflow

1. Open an issue first for anything non-trivial, so the approach can be discussed.
2. Create a branch from `main`.
3. Write a failing test first, then the change (`tests/` mirrors the modules).
   Sound changes should come with a measurable expectation, for example a
   spectral centroid, a level or a band energy. The firmware's sensing core
   (`firmware/lib/touchcore.py`) is pure Python and must stay CircuitPython
   compatible: no numpy, no typing-only syntax at runtime.
4. Keep `uv run ruff check` and `uv run pytest` green; CI runs both.
5. If you have the hardware, play a session and run
   `uv run python tools/evaluate_sessions.py sessions/<your-session>.csv`.
   Mention the result in the pull request.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/),
written in English:

```
feat(accent): add a kalimba-style strike accent
fix(sources): reconnect when the Pico re-enumerates under a new name
docs: explain electrode sizes
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`,
`ci`, `chore`. Use the body to explain *why*, with measurements when relevant.

## Code style

- Small, single-purpose modules; constants with units in their names
  (`_HZ`, `_S`, `_US`, `_DB`) and a comment explaining where each value comes
  from.
- The audio callback must never block, allocate excessively or raise.
  Cross-thread state is shared as immutable tuples, swapped atomically.
- Prefer measurable, research-backed choices; cite the source in a comment or
  in [docs/research.md](docs/research.md).

## Reporting bugs

Use the bug report template. Include your OS, the audio output used, whether
you are on real hardware or `--simulate`, and the terminal output. If you can,
attach a recorded session CSV from `sessions/`.

## Code of Conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
