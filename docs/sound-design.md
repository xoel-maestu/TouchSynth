# Sound design

TouchSynth is an ambient pad played by touch. The design goal is the one Wessel
& Wright describe as *low entry fee, high ceiling*: any touch makes a pleasant
sound immediately, and attentive players discover more and more nuance in how
they touch.

## Gesture → sound

Each gesture feature drives its own sound dimension, so they do not fight each
other. Intensity drives many parameters at once along perceptual curves
(exponential for frequency, dB-linear for loudness), following Hunt &
Wanderley's one-to-many mapping (NIME 2002). The gesture vocabulary is
inspired by the ROLI Seaboard's "5D touch" (strike / press / lift) and by
Jensenius' impulsive and sustained action types.

| Gesture | Measured as | What changes |
|---|---|---|
| **More / less contact** | intensity (log of conductance) | gain −30…0 dB, brightness 100 Hz → 8 kHz, fifth and octave layers, saturation, reverb (distant → close) |
| **Fast strike / slow touch** | rise speed in the first 40 ms (10–35 /s) | attack 120 → 12 ms; a soft felt-mallet note (louder and brighter for harder strikes); up to one octave of extra brightness, never above 3 kHz, fading over 350 ms |
| **Squeeze / ease off** | intensity above a slow per-touch baseline (ignores sweat drift) | stereo width and detune |
| **Tremble** | 3+ Hz variation over 300 ms | vibrato 0–20 cents |
| **Hold** | contact duration | a layer two octaves up grows in (τ 8 s) |
| **Let go fast / slowly** | fall time before release | tail 0.35–3 s; a fast lift throws the sound into the reverb |

All gesture features are computed from the unsmoothed intensity so fast
gestures are not blurred; the level that drives the pad itself goes through a
light 1€ filter (Casiez et al., CHI 2012), which keeps jitter low at rest
without adding lag on fast moves. The press feature compares against a slow
per-touch baseline (τ 4 s) that only starts after a 250 ms settle period, so the
initial rise of a touch is not mistaken for a squeeze or a tremor.

If the sensor stops reporting mid-touch (cable pulled), the sound fades out
instead of droning on.

## Strike accent

A fast, firm touch rings a soft **felt-mallet "vibe" note** on top of the pad
(`touchsynth/accent.py`). It is built with modal synthesis in the manner of
Perry Cook's STK ModalBar: a few exponentially decaying partials, here retuned
to harmonics 1-2-4-6 so they agree with the pentatonic pad.

- **Velocity → spectral tilt**, as in acoustic instruments: a harder strike is
  louder (15 dB from softest to hardest) and its upper partials are stronger,
  but it never turns into noise.
- **No energy in 2.5–5.5 kHz**: partials above 2.5 kHz are not rendered, and the
  strike's brightness boost of the pad is capped at 3 kHz. That band is the
  region Kumar et al. (JASA 2008) found most associated with unpleasant sounds,
  and it is also where perceived sharpness and roughness (Zwicker & Fastl) make
  a percussive onset read as a harsh "crash".
- **Register and variation**: the accent sounds about an octave above the pad
  (a round robin of octave, fifth, octave, two octaves, kept below 750 Hz), so
  repeated taps are not mechanical.
- A raised-cosine onset (8–12 ms) avoids clicks; at most four accents ring at
  once, the oldest fading out in 20 ms when stolen.

The result is checked objectively: in recorded sessions, the 2.5–5.5 kHz energy
in the first 60 ms of hard strikes must not exceed that of the held tone (see
[validation.md](validation.md)).

## Timbre palette

The pad is additive (32 harmonics per voice) and its tone colour is a position
on a circular palette of five colours, chosen to span the brightness and
spectral-shape dimensions of timbre space (McAdams et al., 1995):

1. **flute**: soft, few overtones (1/k²)
2. **warm**: sawtooth-like (1/k)
3. **hollow**: clarinet-like, odd harmonics only
4. **choir "ah"**: vowel formants at 700 / 1220 / 2600 Hz
5. **choir "oo"**: vowel formants at 300 / 870 / 2240 Hz

Every colour is normalised to the same power, so morphing does not change
loudness. The position drifts slowly on its own (two slow sinusoids of 47 and
73 s) and each touch pushes it by 0.3–1.5 palette steps (further for harder
strikes), always gliding (τ 0.6 s), never jumping.

The lowpass that follows intensity is applied analytically to each harmonic's
amplitude, so the pad is band-limited by construction and the filter has no
recursive state to click when the cutoff moves. A 4-line feedback delay
network reverb (Jot) places the sound from distant (light touch) to close
(firm touch).

## Pentatonic note walk

The pad's root walks a two-octave **pentatonic scale, G2–E4**
(G A C D E). Any sequence of pentatonic notes is consonant, so players cannot
play a "wrong" note.

- Each new touch takes a melodic step: one scale degree, or two for hard
  strikes, with a 50 ms portamento.
- Steps lean back towards the middle of the range and bounce off its ends.
- After a pause of more than 4 s the walk returns to the low "home" octave.
- Contact glitches shorter than 150 ms change nothing (no note, no accent).

## Speaker profiles and limiter

Small speakers cannot reproduce deep bass; asking them to only produces
distortion. The `--speakers` flag picks an output profile
(`touchsynth/output.py`):

| Profile | High-pass | Sub-oscillator | For |
|---|---|---|---|
| `small` (default) | 4th-order, 120 Hz | off | laptops, monitors, small speakers |
| `full` | 2nd-order, 25 Hz | on (one octave below the root) | headphones, hi-fi |

The output always passes through a block-wise **peak limiter with a −3 dBFS
ceiling** (instant gain reduction, 150 ms release), leaving headroom for cheap
DACs and speakers. Saturation is a gentle `tanh` drive (0–12 dB with
intensity) tuned for warmth rather than fuzz.

## Latency

| Stage | Figure |
|---|---|
| Sensor window (hum-cancelling average) | 20 ms |
| Touch detection | within one window; release within two |
| Squeeze / ease off visible | ~40 ms |
| Control latency, sensor to sound | ~40 ms |
| Strike attack | ~12 ms |
| Audio block | 512 frames at 48 kHz (10.7 ms) |
| Output buffer | 30 ms |
| Bluetooth (A2DP) output | adds roughly 150–250 ms |

Envelopes are evaluated analytically at audio time rather than stepped at the
sensor rate, so they stay smooth and add no latency of their own.
