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


def degree(root_hz):
    return min(range(len(SCALE_ROOTS_HZ)), key=lambda i: abs(SCALE_ROOTS_HZ[i] - root_hz))


def test_contact_glitches_change_nothing():
    v = Variation(seed=4)
    before = v.current(10.0)
    v.on_touch(1.0, 10.0, rested_s=0.06)
    after = v.current(10.5)
    assert after[1] == before[1]
    assert circular(after[0], before[0]) < 0.05


def test_each_retouch_steps_to_a_neighbouring_note():
    v = Variation(seed=4)
    for i in range(30):
        before = degree(v.current(i * 1.0)[1])
        v.on_touch(0.3, i * 1.0 + 0.5, rested_s=0.5)
        after = degree(v.current(i * 1.0 + 0.9)[1])
        assert 1 <= abs(after - before) <= 2 or before in (0, len(SCALE_ROOTS_HZ) - 1)


def test_harder_strikes_take_bigger_steps():
    def mean_step(strike):
        v, steps = Variation(seed=8), []
        for i in range(200):
            before = degree(v.current(i * 1.0)[1])
            v.on_touch(strike, i * 1.0 + 0.5, rested_s=0.5)
            steps.append(abs(degree(v.current(i * 1.0 + 0.9)[1]) - before))
        return sum(steps) / len(steps)
    assert mean_step(1.0) > mean_step(0.0) + 0.5


def test_melody_wanders_over_the_whole_scale_without_sticking_to_an_end():
    v, seen = Variation(seed=9), []
    for i in range(300):
        v.on_touch(0.5, i * 1.0, rested_s=0.5)
        seen.append(degree(v.current(i * 1.0 + 0.5)[1]))
    assert len(set(seen)) == len(SCALE_ROOTS_HZ)
    assert max(seen.count(d) for d in set(seen)) < 0.3 * len(seen)


def test_notes_glide_briefly_instead_of_jumping():
    v = Variation(seed=4)
    before = v.current(10.0)[1]
    v.on_touch(1.0, 10.0, rested_s=0.5)
    target = v.current(11.0)[1]
    mid = v.current(10.005)[1]
    assert before != target
    assert min(before, target) < mid < max(before, target)


def test_a_long_pause_returns_to_the_low_home_octave():
    v = Variation(seed=4)
    for i in range(20):
        v.on_touch(1.0, i * 1.0, rested_s=0.5)  # wander upwards maybe
        if degree(v.current(i + 0.5)[1]) >= 5:
            break
    v.on_touch(0.5, 100.0, rested_s=10.0)
    assert degree(v.current(100.5)[1]) < 5


def test_timbre_position_stays_on_the_palette_circle():
    v = Variation(seed=6)
    for i in range(50):
        v.on_touch(1.0, i * 2.0, rested_s=1.0)
        assert 0.0 <= v.current(i * 2.0 + 1.0)[0] < PALETTE_SIZE
