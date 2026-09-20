from datetime import datetime, timedelta, timezone
from app.memory.database import load_messages_between

def get_yesterday_range():
    now = datetime.now(timezone.utc)

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

def get_yesterday_messages():
    start_time, end_time = get_yesterday_range()

    return load_messages_between(
        start_time,
        end_time,
    )