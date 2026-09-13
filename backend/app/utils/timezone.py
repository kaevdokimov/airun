from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def user_today(timezone_name: str) -> date:
    return datetime.now(ZoneInfo(timezone_name)).date()


def user_week_ago_utc(timezone_name: str, days: int = 7) -> datetime:
    local_now = datetime.now(ZoneInfo(timezone_name))
    week_ago_local = local_now.date() - timedelta(days=days)
    return datetime.combine(week_ago_local, time.min, tzinfo=ZoneInfo(timezone_name)).astimezone(
        timezone.utc
    )
