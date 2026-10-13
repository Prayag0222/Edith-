from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.memory.message_store import load_messages_between


LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _local_day_range(day: datetime) -> tuple[str, str]:
    start_local = day.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_local = start_local + timedelta(days=1)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    return (
        start_utc.strftime("%Y-%m-%d %H:%M:%S"),
        end_utc.strftime("%Y-%m-%d %H:%M:%S"),
    )


def get_yesterday_range() -> tuple[str, str]:
    yesterday = datetime.now(LOCAL_TIMEZONE) - timedelta(days=1)
    return _local_day_range(yesterday)


def get_today_range() -> tuple[str, str]:
    today = datetime.now(LOCAL_TIMEZONE)
    start_time, end_time = _local_day_range(today)

    # Today's range ends at the current time, not midnight tomorrow.
    now_utc = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    return start_time, min(end_time, now_utc)


def get_time_range(text: str):
    text = text.casefold()

    if "yesterday" in text:
        return get_yesterday_range()

    if "today" in text:
        return get_today_range()

    return None


def get_yesterday_messages():
    start_time, end_time = get_yesterday_range()

    return load_messages_between(start_time, end_time)