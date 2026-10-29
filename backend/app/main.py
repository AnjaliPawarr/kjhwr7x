import os
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import analysis as an

app = FastAPI(title="Wind Forecast Portal API")

origins = [o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",") if o]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"])

CUTOFF_RE = r"^\d{2}:\d{2}$"


@lru_cache(maxsize=1)
def _raw():
    try:
        return an.load_raw()
    except FileNotFoundError:
        raise HTTPException(503, "Data files missing. Run: python scripts/fetch_data.py")


@lru_cache(maxsize=48)
def _comparison(cutoff: str) -> pd.DataFrame:
    try:
        fc, ac = _raw()
        return an.build_comparison(fc, ac, cutoff)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta(cutoff: str = Query(an.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    df = _comparison(cutoff)
    return {
        "default_cutoff": an.DEFAULT_CUTOFF,
        "timezone": an.TZ,
        "days": sorted(df["delivery_day"].unique().tolist()),
        "note": "Forecast = latest WINDFOR publication at or before the cutoff on the day before delivery.",
    }


@app.get("/api/decision")
def decision(day: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
             cutoff: str = Query(an.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    df = _comparison(cutoff)
    if day not in set(df["delivery_day"]):
        raise HTTPException(404, "No forecast available for that day and cutoff")
    return an.day_view(df, day)


@app.get("/api/accuracy")
def accuracy(cutoff: str = Query(an.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    return an.accuracy_report(_comparison(cutoff))


@app.get("/api/timeseries")
def timeseries(cutoff: str = Query(an.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    df = _comparison(cutoff)
    return [
        {"startTime": r.startTime.isoformat(), "forecast": r.forecast,
         "actual": None if pd.isna(r.actual) else r.actual}
        for r in df.itertuples()
    ]
