import os
import streamlit as st
from dotenv import load_dotenv
from periods import period_range

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import altair as alt
import pandas as pd

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

st.subheader("Gross PLN per period: sent vs received")

span = end - start
if span <= timedelta(days=31):
    freq, fmt, unit = "D", "%d.%m", "day"
elif span <= timedelta(days=92):
    freq, fmt, unit = "W-MON", "%d.%m", "week"
else:
    freq, fmt, unit = "MS", "%b %Y", "month"

pln_period = in_period[in_period["currency"] == "PLN"]

tab_all, tab_trend, tab_top = st.tabs(["📄 All invoices", "📈 Trend", "🏆 Top 10"])

long = (
    pln_period.groupby([pd.Grouper(key="issue_date", freq=freq, label="left", closed="left"), "direction"])
    ["gross_amount"].sum()
    .reset_index()
)
long["bucket"] = long["issue_date"].dt.strftime(fmt)
long["direction"] = long["direction"].map({"sent": "Sent", "received": "Received"})

chart = (
    alt.Chart(long)
    .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
    .encode(
        x=alt.X("bucket:O", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        xOffset="direction:N",
        y=alt.Y("gross_amount:Q", title="Gross PLN", axis=alt.Axis(format="~s")),
        color=alt.Color("direction:N", title=None,
                        scale=alt.Scale(domain=["Sent", "Received"], range=["#4C9BE8", "#F2A541"]),
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("bucket:O", title=unit.capitalize()),
                 alt.Tooltip("direction:N", title=" "),
                 alt.Tooltip("gross_amount:Q", title="Gross PLN", format=",.2f")],
    )
    .properties(height=320)
)
with tab_trend:
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"One bar pair per {unit}. Hover a bar for the exact amount.")

with tab_top:
    st.subheader("Top 10 counterparties (gross PLN)")
    is_sent = pln_period["direction"] == "sent"
    cp = pln_period.assign(
        nip=pln_period["buyer_nip"].where(is_sent, pln_period["seller_nip"]),
        name=pln_period["buyer_name"].where(is_sent, pln_period["seller_name"]),
    )
    top = (
        cp.groupby(["direction", "nip"], dropna=False)
        .agg(name=("name", "first"), invoices=("ksef_number", "count"), gross=("gross_amount", "sum"))
        .reset_index()
        .sort_values("gross", ascending=False)
    )
    left, right = st.columns(2)
    for col, direction, label in [(left, "sent", "Buyers (you sold to)"), (right, "received", "Sellers (you bought from)")]:
        col.markdown(f"**{label}**")
        col.dataframe(
            top[top["direction"] == direction].head(10)[["name", "nip", "invoices", "gross"]],   
            hide_index=True,
            use_container_width=True,
            column_config={
                "name": "Name",
                "nip": "NIP",
                "invoices": "Invoices",
                "gross": st.column_config.NumberColumn("Gross PLN", format="%.2f"),
            },
        )
with tab_all:
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

