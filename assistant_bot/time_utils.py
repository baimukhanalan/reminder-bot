from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_model_datetime(value: str, user_timezone: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    # Models occasionally return an obsolete or simply wrong UTC offset while
    # keeping the intended local wall-clock time. The IANA zone is authoritative.
    local = parsed.replace(tzinfo=None).replace(tzinfo=ZoneInfo(user_timezone))
    return local.astimezone(UTC)


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Неизвестный часовой пояс") from exc
    return value


def display_datetime(value: str, user_timezone: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(ZoneInfo(user_timezone)).strftime("%d.%m.%Y в %H:%M")


def next_occurrence(current: datetime, recurrence: str) -> datetime:
    if recurrence == "daily":
        return current + timedelta(days=1)
    if recurrence == "weekly":
        return current + timedelta(days=7)
    if recurrence == "monthly":
        month = 1 if current.month == 12 else current.month + 1
        year = current.year + 1 if current.month == 12 else current.year
        day = current.day
        while day > 28:
            try:
                return current.replace(year=year, month=month, day=day)
            except ValueError:
                day -= 1
        return current.replace(year=year, month=month, day=day)
    raise ValueError("Unsupported recurrence")
