from touchsynth.protocol import Reading, format_line, parse_line


def test_round_trip():
    r = Reading(ms=1234, raw=60000, g_us=0.25, intensity=0.4321, touched=True)
    assert parse_line(format_line(r)) == r


def test_parses_firmware_line():
    assert parse_line("1500,59631,0.1000,0.0810,1\r\n") == Reading(1500, 59631, 0.1, 0.081, True)


def test_ignores_comments_blank_and_garbage():
    for line in ["# touchsynth v1", "", "   ", "abc", "1,2,3", "1,2,x,4,0",
                 "Traceback (most recent call last):"]:
        assert parse_line(line) is None
