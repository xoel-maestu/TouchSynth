"""The firmware's print format must stay parseable by the host."""

import re
from pathlib import Path

from touchsynth.protocol import parse_line

CODE = (Path(__file__).resolve().parents[1] / "firmware" / "code.py").read_text()


def test_firmware_format_string_is_parseable():
    fmt = re.search(r'print\("(\{\},\{\},[^"]+)"\.format', CODE).group(1)
    line = fmt.format(1234, 60000, 0.25, 0.5, 1)
    assert parse_line(line) is not None


def test_firmware_header_is_a_comment():
    header = re.search(r'print\("(#[^"]*)"\)', CODE).group(1)
    assert parse_line(header) is None
