import random
from datetime import datetime, timedelta, timezone

import store

DEMO_DB = "data/demo.db"
COMPANIES = [(f"{random.Random(i).randint(1000000000, 9999999999)}", f"Firma Demo {i} Sp. z o.o.")
             for i in range(1, 16)]
START = datetime(2026, 2, 1, tzinfo=timezone.utc)


def fake_invoice(i: int, rng: random.Random) -> dict:
    nip, name = rng.choice(COMPANIES)
    issued = START + timedelta(days=rng.randint(0, 268))
    net = round(rng.uniform(100, 20000), 2)
    vat = round(net*0.23,2)          # your turn: 23% of net, rounded to 2 decimals
    gross = net+vat        # your turn

    return {
        "ksefNumber": f"DEMO-{i:05d}",
        "invoiceNumber": f"FV/{i:05d}/2026",
        "issueDate": issued.date().isoformat(),
        "invoicingDate": issued.isoformat(),
        "seller": {"nip": nip, "name": name},
        "buyer": {"identifier": {"type": "Nip", "value": "0000000000"}, "name": "My Company"},
        "netAmount": net, "vatAmount": vat, "grossAmount": gross,
        "currency": "PLN", "invoiceType": "Vat",
    }


if __name__ == "__main__":
    rng = random.Random(42)                      # same "random" data every run
    conn = store.connect(DEMO_DB)
    invoices = [fake_invoice(i, rng) for i in range(500)]
    store.upsert(conn, invoices[:300], "sent")
    store.upsert(conn, invoices[300:], "received")
    df = store.dataframe(conn)
    print(len(df), "rows")
    print(df["direction"].value_counts())