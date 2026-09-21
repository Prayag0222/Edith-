from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.memory.database import load_messages_between


LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


def get_yesterday_range():
    now = datetime.now(LOCAL_TIMEZONE)

    yesterday = now - timedelta(days=1)

    start_time = yesterday.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_time = yesterday.replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=0,
    )

    return (
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        end_time.strftime("%Y-%m-%d %H:%M:%S"),
    )


def get_today_range():
    now = datetime.now(LOCAL_TIMEZONE)

    start_time = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_time = now

    return (
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        end_time.strftime("%Y-%m-%d %H:%M:%S"),
    )


def get_time_range(text: str):
    text = text.lower()

    if "yesterday" in text:
        return get_yesterday_range()

    if "today" in text:
        return get_today_range()

    return None


def get_yesterday_messages():
    start_time, end_time = get_yesterday_range()

    return load_messages_between(
        start_time,
        end_time,
    )