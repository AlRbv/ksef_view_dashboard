from ksef_auth import KsefClient
from datetime import datetime, timedelta


PAGE_SIZE = 100

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