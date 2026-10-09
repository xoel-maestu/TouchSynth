# TouchSynth

Instrumento táctil para dos personas: cada una sujeta un electrodo y, al tocarse
piel con piel, suena un pad ambiental continuo que **responde a cómo os tocáis**:
suave o fuerte, rápido o lento, más o menos contacto, temblando o quieto,
soltando de golpe o despacio. El timbre se transforma y las notas recorren una
escala pentatónica con cada toque, así que nunca suena siempre igual.

```
 Persona A ── electrodo A ─┐                      ┌─ Pico 2 ── USB ── PC (Python)
                           ├─ contacto piel-piel ─┤   mide          sintetiza, graba CSV
 Persona B ── electrodo B ─┘                      └─ conductancia
```

## Por qué antes no variaba con la intensidad

1. **Mapeo lineal de una magnitud logarítmica.** La resistencia piel-piel varía
   en órdenes de magnitud (roce ≈ 1–10 MΩ, palma firme ≈ 50–300 kΩ). Leer el ADC
   lineal comprimía casi todo el rango musical en una franja minúscula, y además
   invertido (sin tocar = 1.0).
2. **Parámetros sonoros poco perceptibles.** +20 Hz de tono y un filtro lineal
   300→2100 Hz apenas se oyen. Ahora: un control → muchos parámetros con curvas
   perceptuales (Hunt & Wanderley, NIME 2002).
3. **Zumbido de red (50 Hz) y ADC de alta impedancia** sin condensador ni
   promediado: el ruido tapaba las diferencias finas.
4. **Pad demasiado grave y con pocos armónicos.** Por encima de ~900 Hz el filtro
   no tenía nada que abrir, y 55 Hz no se oye en altavoces pequeños. Ahora las
   notas van de Sol2 a Mi4 con 32 armónicos.
5. pyo estaba roto en el entorno (`libjack` ausente). Se sustituye por numpy +
   sounddevice (PipeWire/ALSA). Los scripts antiguos están en `legacy/` (necesitan pyo).

## Material

| Pieza | Valor | Nota |
|---|---|---|
| Raspberry Pi Pico 2 | RP2350 + CircuitPython 10.0.3 | `.uf2` incluido en el repo local |
| R1 (pull-up) | **1 MΩ** | ajustable tras calibrar (470 kΩ – 2,2 MΩ) |
| R2 (serie, protección) | 100 kΩ, **opcional** | protección ESD; si la pones, `R_SERIES = 100_000` en `code.py` |
| C1 | 10 nF (código `103`), **opcional** | estabiliza el ADC; no es imprescindible (la línea base se resta) |
| 2 electrodos | placas/tubos metálicos, cinta de cobre, pulseras | cuanto más grandes y firmes al agarrarlos, mejor |
| Cables, protoboard | | del kit |

## Montaje

```
3V3(OUT) pin 36 ──[ R1 1 MΩ ]──┬── GP26/ADC0 pin 31
                               ├──[ C1 10 nF, opcional ]── AGND pin 33
                               └──[ R2 100 kΩ, opcional ]── electrodo A  (persona A)

GND pin 38 ────────────────────────────────────── electrodo B  (persona B)
```

Contando filas en la protoboard (USB arriba, columna derecha de la Pico): si el
primer pin junto al USB (VBUS, pin 40) está en la fila N → GND = N+2,
3V3(OUT) = N+4, AGND = N+7, **GP26 = N+9**. No conectes nada a N (5 V) ni a N+3
(3V3_EN apaga la placa).

**Comprobación del cableado:** copia `tools/wiring_check.py` como `code.py`.
Sin tocar, GP26 debe leer ≈ 3,3 V; si lee lo mismo que GP27 (~0,76 V) es que
GP26 está al aire (era el fallo del montaje original: el sensor nunca llegaba
al pin, por eso el sonido no variaba).

- Cada persona **agarra su electrodo con toda la mano** (o pulsera): así la
  resistencia de agarre es baja y constante y lo que varía es el contacto entre
  ellas.
- No conectes nada más a GP26 (nada de `DigitalInOut` en ese pin).
- Seguridad: corriente máxima 3,3 V / 1,1 MΩ ≈ 3 µA, por debajo del límite de
  10 µA de IEC 60601-1 para partes aplicadas. Usa el PC con batería o un USB de
  calidad; no uses este montaje con equipos médicos implantados.

### Calibración (2 min, recomendable)

1. Arranca el sintetizador (abajo). El medidor muestra `G=… uS` (conductancia).
2. Tocaos con la **palma firme** unos segundos y anota el valor `G`.
3. Pon ese valor en `G_MAX_US` de `firmware/code.py` y vuelve a desplegar.
   Ese contacto será intensidad 1.0; el roce más leve que se detecta (33 MΩ) es 0.
   Valor actual: **0,8 µS**, medido con las puntas metálicas de los cables
   (una persona pellizcando: suave 0,1–0,3 µS, fuerte 0,4–0,65 µS). Con
   electrodos grandes o palmas sube mucho (hasta ~10 µS): recalibra.
4. Arranca la Pico **sin tocar los electrodos**: el primer segundo aprende la
   conductancia de reposo (carga del propio ADC, ~0,07 µS) y la resta siempre.
   Si alguien consigue un contacto mejor de forma sostenida (>3 s), el techo se
   estira solo y vuelve a su valor en unos minutos; un pico suelto se ignora.

### Ajuste opcional de R1 (con polímetro)

Cada persona sujeta una punta del polímetro (en Ω) y se tocan: anota la lectura
con un roce ligero (`R_roce`) y con la palma firme (`R_firme`). El R1 óptimo es
`√(R_roce · R_firme)` (máxima sensibilidad en escala log). Si sale lejos de
1 MΩ, pon el valor comercial más cercano y cambia `R_PULLUP` en
`firmware/code.py`.

## Despliegue en la Pico 2

1. (Solo la primera vez) Mantén **BOOTSEL** al enchufar → aparece la unidad
   `RP2350` → copia `adafruit-circuitpython-raspberry_pi_pico2-en_US-10.0.3.uf2`.
   Se reinicia como `CIRCUITPY`.
2. `tools/deploy.sh` (o copia `firmware/code.py` → `CIRCUITPY/code.py` y
   `firmware/lib/touchcore.py` → `CIRCUITPY/lib/`).
3. El LED de la placa se enciende mientras hay contacto. Puedes ver los datos
   crudos con `screen /dev/ttyACM0` (`ms,raw,g_us,intensity,touched`).

## Ejecutar el sintetizador (PC)

```bash
pipenv install                       # una vez
pipenv run python -m touchsynth      # detecta la Pico sola (y la espera si no está)
pipenv run python -m touchsynth --simulate     # sin hardware: gesto de prueba
pipenv run python -m touchsynth --port /dev/ttyACM0 --volume 0.5 --device pipewire
pipenv run python -m touchsynth --speakers full  # auriculares / equipo con graves
pipenv run python -m touchsynth --list-devices  # salidas de audio disponibles
```

`--speakers small` (por defecto) es seguro en pantallas, portátiles y altavoces
pequeños: corta los graves que no pueden reproducir (filtro de 120 Hz, sin
subgrave). La salida lleva un limitador a −3 dBFS en cualquier caso.

Cada sesión se graba en `sessions/AAAAMMDD-HHMMSS.csv`
(`host_s,ms,raw,g_us,intensity,touched`) salvo con `--no-record`.

Escuchar sin hardware ni tarjeta de sonido, o reescuchar una sesión grabada:

```bash
PYTHONPATH=. pipenv run python tools/render.py --simulate demo.wav
PYTHONPATH=. pipenv run python tools/render.py sessions/X.csv out.wav
PYTHONPATH=. pipenv run python tools/evaluate_sessions.py sessions/*.csv  # criterios objetivos
```

## Cómo responde al gesto

Cada rasgo del gesto mueve su propia dimensión del sonido (para que no se pisen):

| Gesto | Cómo se mide | Qué cambia |
|---|---|---|
| **Más / menos contacto** | intensidad (log de la conductancia) | volumen −30…0 dB, brillo 100 Hz → 8 kHz, capas de quinta y octava, saturación, reverb (lejos → cerca) |
| **Golpe rápido / toque lento** | velocidad en los primeros 40 ms (10–35 /s) | ataque 120 → 5 ms, ráfaga de ruido, destello de brillo (+1,5 oct, +9 dB de saturación, 150 ms) |
| **Apretar / aflojar** | intensidad sobre una base lenta por toque (ignora la deriva del sudor) | anchura estéreo y desafinado |
| **Temblar** | variación de 3+ Hz en 300 ms | vibrato 0–20 cents |
| **Mantener** | duración del contacto | capa brillante dos octavas arriba que crece (τ 8 s) |
| **Soltar de golpe / despacio** | tiempo de caída antes de soltar | cola de 0,35 a 3 s; al soltar de golpe, impulso de reverb |

**Timbre y notas (variación):**

- El timbre se mueve por una paleta circular (flauta → cálido → hueco/clarinete
  → coral "aa" → coral "uu"), deriva despacio y cada toque lo empuja (más lejos
  cuanto más fuerte el golpe), siempre deslizándose.
- Cada nuevo toque da un paso melódico (1 grado, 2 si el golpe es fuerte) por
  una pentatónica de dos octavas (Sol2–Mi4) con portamento de 50 ms; tras una
  pausa de más de 4 s vuelve a la octava grave. Los microcortes de contacto
  (< 150 ms) no cambian nada.

El primer toque se detecta en una ventana de 20 ms y el soltar en dos;
presión y aflojado se reflejan en ~40 ms. Si se desconecta el cable, el sonido
se desvanece (nunca se queda sonando).

## Arquitectura

```
firmware/code.py          Pico: ventanas de 20 ms (cancela 50 Hz) → touchcore → USB serie
firmware/lib/touchcore.py conductancia, escala log adaptativa, histéresis (también se testea en PC)
touchsynth/sources.py     lector serie con reconexión / simulador
touchsynth/gestures.py    rasgos del gesto: golpe, presión, temblor, caída al soltar, duración
touchsynth/variation.py   paleta de timbres y paseo melódico pentatónico
touchsynth/controller.py  gestos + variación → parámetros y envolventes (hilo lector → callback sin locks)
touchsynth/mapping.py     gesto → parámetros del sintetizador (curvas perceptuales)
touchsynth/synth.py       pad aditivo (paleta de timbres, lowpass analítico) + reverb FDN
touchsynth/output.py      paso-alto según altavoz + limitador de picos
touchsynth/replay.py      render offline de lecturas (sesiones, simulación)
touchsynth/recorder.py    CSV de sesión
touchsynth/app.py         CLI, stream de audio, medidor en terminal
tools/                    despliegue, comprobación de cableado, render y evaluación de sesiones
```

Tests: `pipenv run python -m pytest -q` (incluye el firmware ejecutado con
hardware simulado).

## Verificado en el hardware real (Pico 2, 2026-10-09)

- Diagnóstico del montaje original: GP26 leía igual que un pin sin conectar
  (~0,76 V): el sensor nunca llegaba al ADC. Con el cableado correcto, en reposo
  0 falsos contactos en minutos de grabación; detección y suelta en < 100 ms.
- Tres sesiones reales tocando (v1.0–v1.2) pasan los 8 criterios de
  `tools/evaluate_sessions.py` con el motor final: sin clipping, 12–17 dB de
  rango de volumen, brillo ×7–11, vibrato usado sin saturar, anchura variable,
  4–5 colores de timbre, 6–9 notas distintas y 100 % de pasos melódicos.
- Audio: con bloques de 512 muestras, 0–5 underflows en 150 s (con 256 eran
  cientos). Latencia de control ~40 ms, ataque en un golpe ~10 ms.
- Una sesión real grabada es test de regresión (`tests/test_real_session.py`).

## Problemas frecuentes

- **Nunca detecta contacto**: comprueba el GND común del electrodo B y que cada
  persona agarra bien su electrodo; prueba manos ligeramente húmedas o R1 = 2,2 MΩ.
- **Siempre "TOUCH"**: algo cortocircuita GP26 a GND; o R1 demasiado pequeña.
- **Intensidad casi siempre en 1**: `G_MAX_US` demasiado bajo → recalibra.
- **Intensidad nunca pasa de ~0,5**: `G_MAX_US` demasiado alto → recalibra.
- **Se queda en "waiting for the Pico..."**: comprueba que aparece `/dev/ttyACM0`,
  usa `--port`, y añade tu usuario al grupo `uucp` (Arch) / `dialout` (Debian).
  Cierra cualquier `screen` abierto sobre el puerto.
