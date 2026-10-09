import pathlib
import sys

# firmware/lib holds the pure-Python sensing core that also runs on the Pico.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "firmware" / "lib"))
