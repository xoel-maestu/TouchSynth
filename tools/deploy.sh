#!/usr/bin/env bash
# Copy the firmware onto the Pico 2's CIRCUITPY drive.
#   tools/deploy.sh                 # auto-detect the mounted CIRCUITPY drive
#   tools/deploy.sh /path/to/CIRCUITPY
# If the Pico is in bootloader mode (drive RP2350), flash CircuitPython first:
#   copy adafruit-circuitpython-raspberry_pi_pico2-en_US-10.0.3.uf2 onto it.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
target="${1:-$(findmnt -rn -o TARGET -S LABEL=CIRCUITPY 2>/dev/null || true)}"
[[ -z "$target" ]] && for d in "/run/media/$USER/CIRCUITPY" "/media/$USER/CIRCUITPY"; do
    [[ -d "$d" ]] && target="$d" && break
done

if [[ -z "$target" || ! -d "$target" ]]; then
    echo "CIRCUITPY drive not found. Plug in the Pico (mount it if needed) or pass its path." >&2
    exit 1
fi

mkdir -p "$target/lib"
cp "$root/firmware/lib/touchcore.py" "$target/lib/touchcore.py"
cp "$root/firmware/code.py" "$target/code.py"   # last: triggers CircuitPython auto-reload
sync
echo "Deployed to $target. The Pico restarts by itself; the LED lights while people touch."
