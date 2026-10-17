from datetime import datetime, timezone

from assistant_bot.time_utils import next_occurrence, parse_model_datetime


def test_naive_datetime_uses_user_timezone():
    parsed = parse_model_datetime("2026-09-11T10:00:00", "Asia/Almaty")
    assert parsed == datetime(2026, 9, 11, 5, 0, tzinfo=timezone.utc)


def test_wrong_model_offset_does_not_shift_wall_clock_time():
    parsed = parse_model_datetime("2026-09-11T10:00:00+06:00", "Asia/Almaty")
    assert parsed == datetime(2026, 9, 11, 5, 0, tzinfo=timezone.utc)


def test_monthly_recurrence_clamps_end_of_month():
    current = datetime(2026, 1, 31, 8, 0, tzinfo=timezone.utc)
    assert next_occurrence(current, "monthly") == datetime(
        2026, 2, 28, 8, 0, tzinfo=timezone.utc
    )
