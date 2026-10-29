import pandas as pd
from app import analysis as an


def _fc(rows):
    df = pd.DataFrame(rows, columns=["startTime", "publishTime", "generation"])
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    return df


def test_picks_latest_publication_before_cutoff():
    fc = _fc([
        ("2026-01-10T12:00Z", "2026-01-08T10:00Z", 1000),
        ("2026-01-10T12:00Z", "2026-01-09T08:00Z", 2000),  # latest before 09:00 cutoff
        ("2026-01-10T12:00Z", "2026-01-09T09:30Z", 3000),  # too late
    ])
    sel = an.select_forecasts(fc, "09:00")
    assert len(sel) == 1 and sel.iloc[0]["forecast"] == 2000


def test_no_forecast_if_nothing_before_cutoff():
    fc = _fc([("2026-01-10T12:00Z", "2026-01-09T10:00Z", 5)])
    assert an.select_forecasts(fc, "09:00").empty


def test_cutoff_changes_selection():
    fc = _fc([
        ("2026-01-10T12:00Z", "2026-01-09T08:00Z", 2000),
        ("2026-01-10T12:00Z", "2026-01-09T09:30Z", 3000),
    ])
    assert an.select_forecasts(fc, "10:00").iloc[0]["forecast"] == 3000


def test_error_and_hourly_actual_mean():
    fc = _fc([("2026-01-10T12:00Z", "2026-01-09T08:00Z", 1000)])
    ac = pd.DataFrame({
        "startTime": pd.to_datetime(["2026-01-10T12:00Z", "2026-01-10T12:30Z"], utc=True),
        "fuelType": "WIND", "generation": [800, 900]})
    df = an.build_comparison(fc, ac, "09:00")
    assert df.iloc[0]["actual"] == 850 and df.iloc[0]["error"] == 150
