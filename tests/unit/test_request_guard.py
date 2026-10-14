from app.guards import RequestGuard


class Clock:
    value = 0.0

    def __call__(self):
        return self.value


def test_guard_blocks_empty_long_fast_and_duplicate_requests():
    clock = Clock()
    guard = RequestGuard(
        min_interval_seconds=10,
        max_question_chars=10,
        duplicate_suppression_seconds=60,
        clock=clock,
    )

    assert guard.check("").allowed is False
    assert guard.check("12345678901").allowed is False
    assert guard.check("int").allowed is True
    assert guard.check("int").allowed is False

    clock.value = 11
    assert guard.check("int").allowed is False


def test_guard_does_not_have_a_daily_total_cap():
    clock = Clock()
    guard = RequestGuard(min_interval_seconds=0, clock=clock)

    for index in range(100):
        assert guard.check(f"int {index}").allowed is True
        clock.value += 1
