# Security and safety policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Report them
privately through GitHub's
[private vulnerability reporting](https://github.com/xoel-maestu/touchsynth/security/advisories/new).
You will get an answer as soon as possible.

## Electrical safety

TouchSynth passes a small current through the players' bodies. Please also
report, privately and with the same priority, any design or documentation issue
that could raise that current or remove a safeguard.

The documented circuit limits the current to about 3 µA (3.3 V through 1 MΩ).
That is below the 10 µA normal-condition limit of IEC 60601-1 for applied
parts. Never power the circuit from anything other than the Pico's 3V3 output,
and do not use the instrument with implanted medical devices. See
[docs/hardware.md](docs/hardware.md#safety).
