from datetime import datetime
from periods import period_range, TZ

NOW = datetime(2026, 10, 27, 14, 0, tzinfo=TZ)     # fixed "today" for every test


def test_last_month():
    start, end = period_range("Last month", NOW)
    assert start == datetime(2026, 9, 1, tzinfo=TZ)
    assert end == datetime(2026, 10, 1, tzinfo=TZ)


def test_last_7_days():
    start, end = period_range("Last 7 days", NOW)
    assert start == datetime(2026, 10, 20, tzinfo=TZ)      
    assert end == NOW


def test_all_time():
    start, end = period_range("All time", NOW)  
    assert start == datetime(2026, 2, 1, 0, 0, tzinfo=TZ)           
    assert end == NOW          