import sqlite3
import pandas as pd

DB_PATH = "data/ksef.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    ksef_number     TEXT NOT NULL,
    direction       TEXT NOT NULL,
    invoice_number  TEXT NOT NULL,
    issue_date      TEXT NOT NULL,
    invoicing_date  TEXT NOT NULL,
    seller_nip      TEXT,
    seller_name     TEXT,
    buyer_nip       TEXT,
    buyer_name      TEXT,
    net_amount      REAL,
    vat_amount      REAL,
    gross_amount    REAL,
    currency        TEXT,
    invoice_type    TEXT,
    PRIMARY KEY (ksef_number, direction)
);
"""

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn

def to_row(inv: dict, direction: str) -> dict:
    return {
        "ksef_number":    inv["ksefNumber"],
        "direction":      direction,
        "invoice_number": inv["invoiceNumber"],
        "issue_date":     inv["issueDate"],
        "invoicing_date": inv["invoicingDate"],
        "seller_nip":     inv["seller"]["nip"],
        "seller_name":    inv["seller"].get("name"),
        "buyer_nip":      inv["buyer"].get("identifier", {}).get("value"),
        "buyer_name":     inv["buyer"].get("name"),
        "net_amount":     inv["netAmount"],
        "vat_amount":     inv["vatAmount"],
        "gross_amount":   inv["grossAmount"],
        "currency":       inv["currency"],
        "invoice_type":   inv["invoiceType"],
    }

UPSERT = """
INSERT INTO invoices (
    ksef_number, direction, invoice_number, issue_date, invoicing_date,
    seller_nip, seller_name, buyer_nip, buyer_name,
    net_amount, vat_amount, gross_amount, currency, invoice_type
)
VALUES (
    :ksef_number, :direction, :invoice_number, :issue_date, :invoicing_date,
    :seller_nip, :seller_name, :buyer_nip, :buyer_name,
    :net_amount, :vat_amount, :gross_amount, :currency, :invoice_type
)
ON CONFLICT (ksef_number, direction) DO UPDATE SET
    invoice_number = excluded.invoice_number,
    issue_date     = excluded.issue_date,
    invoicing_date = excluded.invoicing_date,
    seller_nip     = excluded.seller_nip,
    seller_name    = excluded.seller_name,
    buyer_nip      = excluded.buyer_nip,
    buyer_name     = excluded.buyer_name,
    net_amount     = excluded.net_amount,
    vat_amount     = excluded.vat_amount,
    gross_amount   = excluded.gross_amount,
    currency       = excluded.currency,
    invoice_type   = excluded.invoice_type;
"""

def upsert(conn: sqlite3.Connection, invoices: list[dict], direction: str) -> None:
    rows = [to_row(inv, direction) for inv in invoices]
    conn.executemany(UPSERT, rows)
    conn.commit()


def dataframe(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM invoices", conn)
    df["issue_date"] = pd.to_datetime(df["issue_date"]).dt.tz_localize("Europe/Warsaw")
    df["invoicing_date"] = pd.to_datetime(df["invoicing_date"], utc=True).dt.tz_convert("Europe/Warsaw")
    return df