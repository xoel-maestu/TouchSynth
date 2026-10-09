from touchsynth.variation import PALETTE_SIZE, SCALE_ROOTS_HZ, Variation


def circular(a, b):
    d = abs(a - b) % PALETTE_SIZE
    return min(d, PALETTE_SIZE - d)


def positions(v, start, end, step=0.1):
    t, out = start, []
    while t < end:
        out.append(v.current(t)[0])
        t += step
    return out


def test_is_reproducible_with_a_seed():
    a, b = Variation(seed=3), Variation(seed=3)
    a.on_touch(0.5, 10.0, rested_s=1.0)
    b.on_touch(0.5, 10.0, rested_s=1.0)
    assert a.current(12.0) == b.current(12.0)


def test_timbre_drifts_slowly_by_itself():
    v = Variation(seed=1)
    pos = positions(v, 0.0, 60.0)
    steps = [circular(a, b) for a, b in zip(pos, pos[1:])]
    assert max(pos) - min(pos) > 0.3          # it wanders...
    assert max(steps) < 0.02                  # ...smoothly


def test_harder_strikes_push_the_timbre_further():
    def moved(strike):
        v = Variation(seed=5)
        before = v.current(10.0)[0]
        v.on_touch(strike, 10.0, rested_s=1.0)
        return circular(v.current(13.0)[0], before)
    assert moved(1.0) > moved(0.0) + 0.5


def test_timbre_glides_instead_of_jumping():
    v = Variation(seed=2)
    before = v.current(10.0)[0]
    v.on_touch(1.0, 10.0, rested_s=1.0)
    assert circular(v.current(10.01)[0], before) < 0.1


def test_a_long_pause_changes_the_root_within_the_scale():
    v = Variation(seed=4)
    root = v.current(0.0)[1]
    v.on_touch(0.5, 10.0, rested_s=1.0)        # quick re-touch: same note
    assert v.current(10.5)[1] == root
    v.on_touch(0.5, 20.0, rested_s=5.0)        # after a pause: another note
    new_root = v.current(20.5)[1]
    assert new_root != root
    assert new_root in SCALE_ROOTS_HZ


def test_timbre_position_stays_on_the_palette_circle():
    v = Variation(seed=6)
    for i in range(50):
        v.on_touch(1.0, i * 2.0, rested_s=1.0)
        assert 0.0 <= v.current(i * 2.0 + 1.0)[0] < PALETTE_SIZE
