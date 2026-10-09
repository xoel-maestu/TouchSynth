# TouchSynth

Instrumento táctil para dos personas: cada una sujeta un electrodo y, al tocarse
piel con piel, suena un pad ambiental continuo que **cambia con la intensidad del
contacto** (roce de un dedo → suave, oscuro y lejano; palma firme → fuerte,
brillante, con más capas y presencia; golpe rápido → "florecimiento" de brillo).

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
   no tenía nada que abrir, y 55 Hz no se oye en altavoces pequeños. Ahora la
   raíz es La2 (110 Hz) con 32 armónicos.
5. pyo estaba roto en el entorno (`libjack` ausente). Se sustituye por numpy +
   sounddevice (PipeWire/ALSA). Los scripts antiguos están en `legacy/` (necesitan pyo).

## Material

| Pieza | Valor | Nota |
|---|---|---|
| Raspberry Pi Pico 2 | RP2350 + CircuitPython 10.0.3 | `.uf2` incluido en el repo local |
| R1 (pull-up) | **1 MΩ** | ajustable tras calibrar (470 kΩ – 2,2 MΩ) |
| R2 (serie, protección) | **100 kΩ** | limita corriente y ESD |
| C1 | **10 nF** (código `103`) | estabiliza el ADC y filtra 50 Hz |
| 2 electrodos | placas/tubos metálicos, cinta de cobre, pulseras | cuanto más grandes y firmes al agarrarlos, mejor |
| Cables, protoboard | | del kit |

## Montaje

```
3V3(OUT) pin 36 ──[ R1 1 MΩ ]──┬── GP26/ADC0 pin 31
                               ├──[ C1 10 nF ]── AGND pin 33
                               └──[ R2 100 kΩ ]── electrodo A  (persona A)

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
   Ese contacto será intensidad 1.0; el roce más leve que se detecta (15 MΩ) es 0.
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
pipenv run python -m touchsynth --list-devices  # salidas de audio disponibles
```

Cada sesión se graba en `sessions/AAAAMMDD-HHMMSS.csv`
(`host_s,ms,raw,g_us,intensity,touched`) salvo con `--no-record`.

Escuchar sin hardware ni tarjeta de sonido:
`PYTHONPATH=. pipenv run python tools/render_simulation.py demo.wav`.

## Cómo suena la intensidad (mapeo)

| Parámetro | Curva | Roce → palma firme |
|---|---|---|
| Volumen | dB lineal | −24 dB → 0 dB |
| Filtro (brillo) | exponencial | 150 Hz → 4 kHz |
| Capa de quinta / octava | fundido de igual potencia | entran a partir de 0,25 / 0,55 |
| Desafinado (anchura) | exponencial | ±3 → ±18 cents |
| Saturación (calidez) | dB lineal | 0 → +12 dB |
| Movimiento (LFO) | exponencial | 0,08 → 0,6 Hz |
| Reverb | lineal inversa | lejana (0,5) → presente (0,25) |
| Golpe rápido | velocidad > 3/s | +1 octava de brillo que decae en 250 ms |

Al soltar, el timbre se mantiene y el volumen se desvanece en ~2 s (también si
se desconecta el cable: nunca se queda sonando).

Medido en el render de la simulación (`tools/render_simulation.py`): de roce a
palma firme el nivel sube de ≈ −40 a ≈ −15 dBFS y el centroide espectral de
≈ 310 a ≈ 1100 Hz.

## Arquitectura

```
firmware/code.py          Pico: ventanas de 20 ms (cancela 50 Hz) → touchcore → USB serie
firmware/lib/touchcore.py conductancia, escala log adaptativa, histéresis (también se testea en PC)
touchsynth/sources.py     lector serie con reconexión / simulador
touchsynth/controller.py  filtro 1€, envolventes, gate y "bloom" (hilo lector → callback sin locks)
touchsynth/mapping.py     intensidad → parámetros (curvas perceptuales)
touchsynth/synth.py       pad aditivo con lowpass analítico + reverb FDN, rampas por bloque
touchsynth/recorder.py    CSV de sesión
touchsynth/app.py         CLI, stream de audio, medidor en terminal
```

Tests: `pipenv run python -m pytest -q` (incluye el firmware ejecutado con
hardware simulado).

## Problemas frecuentes

- **Nunca detecta contacto**: comprueba el GND común del electrodo B y que cada
  persona agarra bien su electrodo; prueba manos ligeramente húmedas o R1 = 2,2 MΩ.
- **Siempre "TOUCH"**: algo cortocircuita GP26 a GND; o R1 demasiado pequeña.
- **Intensidad casi siempre en 1**: `G_MAX_US` demasiado bajo → recalibra.
- **Intensidad nunca pasa de ~0,5**: `G_MAX_US` demasiado alto → recalibra.
- **Se queda en "waiting for the Pico..."**: comprueba que aparece `/dev/ttyACM0`,
  usa `--port`, y añade tu usuario al grupo `uucp` (Arch) / `dialout` (Debian).
  Cierra cualquier `screen` abierto sobre el puerto.
