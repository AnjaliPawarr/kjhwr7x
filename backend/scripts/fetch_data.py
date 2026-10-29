"""Download raw Elexon data for the January 2026 decisions.

Writes data/forecasts_raw.csv (ALL publications, nothing de-duplicated) and
data/actuals_raw.csv (FUELHH, WIND only). Selection of the "latest forecast
before the cutoff" happens later in app/analysis.py so the cutoff can change.

Verify the query parameter names against the Elexon API docs if a call fails.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
OUT = Path(__file__).resolve().parent.parent / "data"


def get(dataset: str, params: dict) -> list:
    r = requests.get(f"{BASE}/{dataset}/stream", params={**params, "format": "json"}, timeout=120)
    r.raise_for_status()
    js = r.json()
    return js["data"] if isinstance(js, dict) else js


def daterange(a: date, b: date):
    while a <= b:
        yield a
        a += timedelta(days=1)


def main():
    OUT.mkdir(exist_ok=True)
    fc = []
    # Forecasts for 1 Jan are published from ~mid-December; for 31 Jan until 30 Jan.
    for d in daterange(date(2025, 12, 28), date(2026, 1, 30)):
        rows = get("WINDFOR", {"publishDateTimeFrom": f"{d}T00:00:00Z",
                               "publishDateTimeTo": f"{d}T23:59:59Z"})
        print("WINDFOR", d, len(rows))
        fc += rows
    pd.DataFrame(fc)[["startTime", "publishTime", "generation"]].to_csv(OUT / "forecasts_raw.csv", index=False)

    ac = []
    for d in daterange(date(2026, 1, 1), date(2026, 1, 31)):
        rows = get("FUELHH", {"settlementDateFrom": str(d), "settlementDateTo": str(d), "fuelType": "WIND"})
        print("FUELHH", d, len(rows))
        ac += rows
    df = pd.DataFrame(ac)
    df = df[df["fuelType"] == "WIND"][["startTime", "fuelType", "generation"]]
    df.to_csv(OUT / "actuals_raw.csv", index=False)
    print("Done:", OUT)


if __name__ == "__main__":
    sys.exit(main())
