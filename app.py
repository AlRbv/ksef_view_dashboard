import os
import streamlit as st
from dotenv import load_dotenv
from periods import period_range

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import store
import sync
from ksef_auth import KsefClient

load_dotenv()
URLS = {
    "Test": "https://api-test.ksef.mf.gov.pl/v2",
    "Production": "https://api.ksef.mf.gov.pl/v2",
}
WARSAW = ZoneInfo("Europe/Warsaw")

st.set_page_config(page_title="KSeF Dashboard", layout="wide")

with st.sidebar:
    source = st.radio("Data", ["KSeF", "Demo"])
    env = st.selectbox("Environment", list(URLS))
    nip = st.text_input("NIP", value=os.getenv("KSEF_NIP", ""))
    token = st.text_input("KSeF token", value=os.getenv("KSEF_TOKEN", ""), type="password")

    db_path = "data/demo.db" if source == "Demo" else f"data/ksef_{env.lower()}.db"
    conn = store.connect(db_path)

    if st.button("Sync now", disabled=(source == "Demo")):
        with st.spinner("Syncing with KSeF..."):
            client = KsefClient(URLS[env], nip, token)
            result = sync.sync(client, conn)
        st.success(f"{result['received']} received, {result['sent']} sent")
    last = store.get_last_sync(conn, "sent")
    st.caption(f"Last sync: {last:%Y-%m-%d %H:%M} UTC" if last else "Never synced")

st.title("KSeF Dashboard")
df = store.dataframe(conn)
period = st.selectbox("Period", ["Last 7 days", "This month", "Last month", "All time","Custom range"])
now = datetime.now(WARSAW)
if period == "Custom range":
    today = now.date()
    picked = st.date_input(
        "From - to",
        value=(today - timedelta(days=30), today),
        max_value= today,
        format = "DD.MM.YYYY"
    )
    if len(picked) < 2:
        st.info("Pick an end date")
        st.stop()
    d_from, d_to = picked
    start = datetime.combine(d_from, time.min, tzinfo=WARSAW)
    end = datetime.combine(d_to + timedelta(days=1), time.min, tzinfo=WARSAW)
else:
    start, end = period_range(period, now)

in_period = df[(df["issue_date"] >= start) & (df["issue_date"] < end)]

for direction, label in [("sent", "Sent"), ("received", "Received")]:
    part = in_period[in_period["direction"] == direction]
    pln = part[part["currency"] == "PLN"]

    st.subheader(label)
    c1, c2, c3 = st.columns(3)
    c1.metric("Invoices", len(part))
    c2.metric("Gross (PLN)", f"{pln['gross_amount'].sum():,.2f}")
    c3.metric("VAT (PLN)", f"{part['vat_amount'].sum():,.2f}")

st.subheader("All invoices")
query = st.text_input("Search: NIP, name or invoice number")

table = in_period.copy()
if query:
    q = query.strip().lower()
    search_cols = ["invoice_number", "seller_nip", "seller_name", "buyer_nip", "buyer_name"]
    haystack = table[search_cols].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    table = table[haystack.str.contains(q, regex=False)]

table = table.sort_values("issue_date", ascending=False)

st.dataframe(
    table[["issue_date", "direction", "invoice_number",
           "seller_name", "seller_nip", "buyer_name", "buyer_nip",
           "net_amount", "vat_amount", "gross_amount", "currency",
           "invoice_type", "ksef_number"]],
    hide_index=True,
    column_config={
        "issue_date": st.column_config.DateColumn("Issue date", format="DD.MM.YYYY"),
        "net_amount": st.column_config.NumberColumn("Net", format="%.2f"),
        "vat_amount": st.column_config.NumberColumn("VAT", format="%.2f"),
        "gross_amount": st.column_config.NumberColumn("Gross", format="%.2f"),
    },
)
st.caption(f"{len(table)} invoices")