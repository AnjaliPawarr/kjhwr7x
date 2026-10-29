"""Core logic: pick the forecast known at decision time, join with actuals, compute errors.

Key rule: for each delivery hour on day D we use the forecast with the LATEST
publishTime that is <= the decision cutoff on day D-1 (London time). Anything
published later was not available when the purchase decision was made.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TZ = "Europe/London"
MONTH_START = "2026-01-01"
MONTH_END = "2026-01-31"
DEFAULT_CUTOFF = "09:00"  # London time on D-1; configurable in the UI


def _parse_hm(cutoff: str) -> tuple[int, int]:
    h, m = cutoff.split(":")
    h, m = int(h), int(m)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("cutoff must be HH:MM")
    return h, m


def load_raw(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    fc = pd.read_csv(data_dir / "forecasts_raw.csv")
    ac = pd.read_csv(data_dir / "actuals_raw.csv")
    fc["startTime"] = pd.to_datetime(fc["startTime"], utc=True)
    fc["publishTime"] = pd.to_datetime(fc["publishTime"], utc=True)
    fc["generation"] = pd.to_numeric(fc["generation"], errors="coerce")
    ac["startTime"] = pd.to_datetime(ac["startTime"], utc=True)
    ac["generation"] = pd.to_numeric(ac["generation"], errors="coerce")
    return fc, ac


def hourly_actuals(ac: pd.DataFrame) -> pd.DataFrame:
    """FUELHH is half-hourly; WINDFOR is hourly -> average actuals per hour."""
    if "fuelType" in ac.columns:
        ac = ac[ac["fuelType"] == "WIND"]
    ac = ac.assign(hour=ac["startTime"].dt.floor("h"))
    out = ac.groupby("hour", as_index=False)["generation"].mean()
    return out.rename(columns={"hour": "startTime", "generation": "actual"})


def select_forecasts(fc: pd.DataFrame, cutoff: str = DEFAULT_CUTOFF) -> pd.DataFrame:
    """Latest forecast per delivery hour published at or before the D-1 cutoff."""
    h, m = _parse_hm(cutoff)
    fc = fc.dropna(subset=["generation"]).copy()
    local = fc["startTime"].dt.tz_convert(TZ).dt.tz_localize(None)
    day = local.dt.normalize()
    cutoff_local = day - pd.Timedelta(days=1) + pd.Timedelta(hours=h, minutes=m)
    fc["cutoff"] = cutoff_local.dt.tz_localize(
        TZ, ambiguous="NaT", nonexistent="shift_forward"
    ).dt.tz_convert("UTC")
    fc["delivery_day"] = day.dt.strftime("%Y-%m-%d")
    fc = fc[fc["publishTime"] <= fc["cutoff"]]
    fc = fc.sort_values("publishTime").groupby("startTime", as_index=False).tail(1)
    fc = fc[(fc["delivery_day"] >= MONTH_START) & (fc["delivery_day"] <= MONTH_END)]
    fc["lead_hours"] = (fc["startTime"] - fc["publishTime"]).dt.total_seconds() / 3600
    return fc.rename(columns={"generation": "forecast"}).sort_values("startTime")


def build_comparison(fc: pd.DataFrame, ac: pd.DataFrame, cutoff: str = DEFAULT_CUTOFF) -> pd.DataFrame:
    sel = select_forecasts(fc, cutoff)
    df = sel.merge(hourly_actuals(ac), on="startTime", how="left")
    df["error"] = df["forecast"] - df["actual"]
    df["hour_of_day"] = df["startTime"].dt.tz_convert(TZ).dt.hour
    return df


def metrics(err: pd.Series, actual: pd.Series | None = None) -> dict:
    e = err.dropna()
    if e.empty:
        return {"n": 0}
    out = {
        "n": int(len(e)),
        "mae": float(e.abs().mean()),
        "rmse": float(np.sqrt((e**2).mean())),
        "bias": float(e.mean()),
        "p90_abs": float(e.abs().quantile(0.90)),
        "p95_abs": float(e.abs().quantile(0.95)),
    }
    if actual is not None:
        a = actual.loc[e.index]
        mask = a > 500  # avoid dividing by near-zero generation
        out["mape_pct"] = float((e[mask].abs() / a[mask]).mean() * 100) if mask.any() else None
    return out


def accuracy_report(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["actual", "forecast"]).copy()
    d["error"] = d["forecast"] - d["actual"]

    def group(col, bins=None, labels=None):
        key = pd.cut(d[col], bins=bins, labels=labels, right=False) if bins else d[col]
        rows = []
        for k, g in d.groupby(key, observed=True):
            rows.append({"key": str(k), **metrics(g["error"], g["actual"])})
        return rows

    return {
        "overall": metrics(d["error"], d["actual"]),
        "by_hour": group("hour_of_day"),
        "by_horizon": group(
            "lead_hours",
            bins=[0, 12, 18, 24, 30, 36, 48, 1000],
            labels=["0-12h", "12-18h", "18-24h", "24-30h", "30-36h", "36-48h", "48h+"],
        ),
        "by_wind_level": group(
            "actual",
            bins=[0, 5000, 10000, 15000, 1e9],
            labels=["<5 GW", "5-10 GW", "10-15 GW", ">15 GW"],
        ),
        "by_day": [
            {"day": day, **metrics(g["error"], g["actual"])}
            for day, g in d.groupby("delivery_day")
        ],
    }


def day_view(df: pd.DataFrame, day: str) -> dict:
    """Decision view for one delivery day, with an empirical error band
    built from all OTHER days (so the band is not fitted on the day shown)."""
    today = df[df["delivery_day"] == day].sort_values("startTime")
    others = df[(df["delivery_day"] != day)].dropna(subset=["error"])
    q = others.groupby("hour_of_day")["error"].quantile([0.1, 0.9]).unstack()
    rows = []
    for _, r in today.iterrows():
        lo = hi = None
        if r["hour_of_day"] in q.index:
            # error = forecast - actual  => actual ~ forecast - error
            lo = float(r["forecast"] - q.loc[r["hour_of_day"], 0.9])
            hi = float(r["forecast"] - q.loc[r["hour_of_day"], 0.1])
        rows.append({
            "startTime": r["startTime"].isoformat(),
            "hour": int(r["hour_of_day"]),
            "forecast": float(r["forecast"]),
            "publishTime": r["publishTime"].isoformat(),
            "lead_hours": round(float(r["lead_hours"]), 1),
            "actual": None if pd.isna(r["actual"]) else float(r["actual"]),
            "band_low": lo,
            "band_high": hi,
        })
    fvals = today["forecast"]
    return {
        "day": day,
        "rows": rows,
        "summary": {
            "mean_forecast": None if fvals.empty else float(fvals.mean()),
            "min_forecast": None if fvals.empty else float(fvals.min()),
            "max_forecast": None if fvals.empty else float(fvals.max()),
            "latest_publish": None if today.empty else today["publishTime"].max().isoformat(),
            "cutoff": None if today.empty else today["cutoff"].iloc[0].isoformat(),
            "hours_covered": int(len(today)),
        },
    }
