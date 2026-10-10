# Research and references

The works below shaped TouchSynth's design. Each entry notes how.

## Musical interaction and mapping

- **A. Hunt, M. M. Wanderley and M. Paradis, "The importance of parameter
  mapping in electronic instrument design", NIME 2002.** One-to-many mappings feel more
  expressive than one-to-one: a single touch intensity drives loudness,
  brightness, harmonic layers, saturation, reverb and width at once, along
  perceptual (exponential / dB-linear) curves (`touchsynth/mapping.py`).
- **D. Wessel and M. Wright, "Problems and prospects for intimate musical
  control of computers", *Computer Music Journal*, 2002.** The latency budget
  for intimate control (on the order of 10 ms, with low jitter) and the goal of
  a *low entry fee with a high ceiling*: any touch sounds good, nuance rewards
  practice. Drove the 20 ms sensor window, the ~12 ms strike attack and the
  audio-rate envelopes.
- **A. R. Jensenius, action types (impulsive, sustained, iterative).** The
  split between strike (impulsive onset) and press / hold / tremor (sustained
  evolution) in `touchsynth/gestures.py`.
- **ROLI Seaboard, "5D touch" (strike, press, glide, slide, lift).** The
  vocabulary of strike, press and lift as separate expressive dimensions of a
  single contact.
- **Playtronica TouchMe.** A commercial instrument that makes music from
  skin-to-skin conduction between people; a precedent for the interaction
  concept.
- **M. Sato, I. Poupyrev and C. Harrison, "Touché: enhancing touch interaction
  on humans, screens, liquids, and everyday objects", CHI 2012.** Swept-
  frequency capacitive sensing can distinguish touch *configurations*.
  Considered and rejected as overkill: a DC conductance measurement with one
  resistor gives the continuous intensity the instrument needs, with far
  simpler hardware.

## Signal processing

- **G. Casiez, N. Roussel and D. Vogel, "1€ filter: a simple speed-based
  low-pass filter for noisy input in interactive systems", CHI 2012.** Smooths
  the level that drives the pad: low jitter at rest, low lag on fast moves
  (`touchsynth/smoothing.py`).
- **J.-M. Jot and A. Chaigne, "Digital delay networks for designing artificial
  reverberators", AES Convention, 1991.**
  The 4-line FDN reverb with a Hadamard feedback matrix and per-line damping
  (`touchsynth/synth.py`).
- **P. R. Cook, Synthesis ToolKit (STK), `ModalBar`.** Modal synthesis of a
  struck bar, the basis of the felt-mallet strike accent, with partials retuned
  to harmonics 1-2-4-6 (`touchsynth/accent.py`).

## Psychoacoustics and timbre

- **E. Zwicker and H. Fastl, *Psychoacoustics: Facts and Models*.** Sharpness
  and roughness as the perceptual correlates of harshness; motivated keeping
  strikes free of high-frequency noise and limiting saturation.
- **S. Kumar, H. M. Forster, P. Bailey and T. D. Griffiths, "Mapping
  unpleasantness of sounds to their auditory representation", *JASA* 124(6),
  2008.** The 2.5–5.5 kHz band is most associated with unpleasant sounds:
  the accent renders nothing there, strike brightness is capped at 3 kHz, and
  `tools/evaluate_sessions.py` checks it on real sessions.
- **S. McAdams, S. Winsberg, S. Donnadieu, G. De Soete and J. Krimphoff,
  "Perceptual scaling of synthesized musical timbres", *Psychological
  Research*, 1995.** Timbre space (spectral centroid, attack, spectral
  shape): the five-colour palette spans brightness and spectral shape, and the
  strike controls attack time.

## Hardware and safety

- **Raspberry Pi, *RP2350 Datasheet*, including erratum E9.** ADC and GPIO pad
  behaviour and the pad-register addresses used by `tools/diag_code.py`. E9
  (pad leakage while the digital input buffer is enabled) does not affect the
  sensor: CircuitPython disables the input buffer on ADC pins, which was
  confirmed on the board (IE = 0 on GP26).
- **IEC 60601-1, medical electrical equipment: general requirements for
  safety.** Patient leakage limit of 10 µA for applied parts in normal
  condition; the circuit limits current to ≈ 3 µA.
- **Electrodermal activity (skin conductance) literature**, e.g. W. Boucsein,
  *Electrodermal Activity*, Springer. Skin conductance varies widely between
  people and over time with temperature, hydration and arousal; matches the
  ~5× evening-to-night variation measured on this instrument and motivated the
  adaptive intensity top (`firmware/lib/touchcore.py`).
