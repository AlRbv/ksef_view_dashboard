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