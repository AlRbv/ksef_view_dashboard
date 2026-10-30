from ksef_auth import KsefClient
from datetime import datetime, timedelta,  timezone

import store

PAGE_SIZE = 100
DEFAULT_START = datetime(2026, 2, 1, tzinfo=timezone.utc)   # KSeF 2.0 go-live
OVERLAP = timedelta(minutes=5)

def fetch_all(client: KsefClient, subject_type: str, date_from: str, date_to: str) -> list[dict]:
    invoices = []
    page_offset = 0

    while True:
        page = client.query_metadata_page(subject_type, date_from, date_to, page_offset=page_offset, page_size=PAGE_SIZE)
        invoices.extend(page["invoices"])

        if not page["hasMore"]:
            break
        page_offset += 1
    
    return invoices

def date_windows(start: datetime, end: datetime, days: int = 90) -> list[tuple[datetime, datetime]]:
    windows = []
    window_start = start
    while window_start < end:
        window_end = min(window_start + timedelta(days=days), end)       
        windows.append((window_start, window_end))
        window_start = window_end
    return windows


def sync_direction(client: KsefClient, conn, subject_type: str, direction: str) -> int:
    last = store.get_last_sync(conn, direction)
    start = last - OVERLAP if last else DEFAULT_START                              
    now = datetime.now(timezone.utc)      

    total = 0
    for window_start, window_end in date_windows(start, now):
        invoices = fetch_all(client, subject_type, window_start.isoformat(), window_end.isoformat())
        store.upsert(conn, invoices, direction)
        store.set_last_sync(conn, direction, window_end)  
        total += len(invoices)
    return total

def sync(client: KsefClient, conn) -> dict:
    return {
        "sent": sync_direction(client, conn, "Subject1", "sent"),
        "received": sync_direction(client, conn, "Subject2", "received"),                
    }