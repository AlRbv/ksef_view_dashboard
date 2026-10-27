from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")

def period_range(name: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(TZ)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if name == "Last 7 days":
        return today - timedelta(days=7), now
    if name == "This month":
        return today.replace(day=1), now
    if name == "Last month":
        first_this_month = today.replace(day=1)
        first_last_month = (first_this_month - timedelta(days=5)).replace(day=1)    
        return first_last_month, first_this_month
    if name == "All time":
        return datetime(2026, 2, 1, tzinfo=TZ), now
    raise ValueError(f"Unknown period: {name}")