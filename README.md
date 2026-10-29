# WindWise – GB day-ahead wind forecast portal

Web app for a day-ahead power-buying team. It shows (1) the latest wind forecast that was
available at decision time and (2) how accurate those forecasts were in January 2026.
Data: Elexon BMRS only – `WINDFOR` (forecasts) and `FUELHH` (actuals, `fuelType = WIND`).

**Live app:** <ADD VERCEL / HEROKU / RENDER LINK>  
**Demo video:** <ADD UNLISTED YOUTUBE LINK>

## AI tool disclosure
AI tools (Claude) were used to help design and write parts of this code, and the code was reviewed and
tested by the author.

## Key logic (read this first)
For each delivery hour on day D, the forecast used is the one with the **latest `publishTime` that is
at or before the decision cutoff on day D-1** (London time, default 09:00, configurable in the UI).
Forecasts published later were not available when the decision was made, so using them would flatter
the accuracy. See `select_forecasts()` in `backend/app/analysis.py` and its tests.

Assumptions: cutoff 09:00 London time on D-1 (GB day-ahead auctions close in the morning; change it in the UI);
FUELHH half-hourly actuals are averaged to hourly to match hourly forecasts; error = forecast − actual;
MAPE ignores hours with actual ≤ 500 MW; the P10–P90 band on the Decision view is built from the other days of the month.

## Files
```
backend/
  app/analysis.py      forecast selection, joins, error metrics (core logic)
  app/main.py          FastAPI endpoints
  scripts/fetch_data.py  downloads raw Elexon data into backend/data/
  tests/test_selection.py unit tests for the selection logic
  data/                forecasts_raw.csv, actuals_raw.csv (commit these so deployment needs no network)
frontend/src/          React (Vite + Recharts): Decision view and Accuracy view
docker-compose.yml     runs both services
```
API: `/api/meta`, `/api/decision?day=&cutoff=`, `/api/accuracy?cutoff=`, `/api/timeseries?cutoff=`.

## Run it
```bash
# 1. get the data (once, needs internet)
cd backend && pip install -r requirements.txt && python scripts/fetch_data.py

# 2a. Docker
cd .. && docker compose up --build      # app on http://localhost:8080, API on :8000

# 2b. or without Docker
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev   # http://localhost:5173

# tests
cd backend && pytest
```

## Deploy
- Backend: any container host (Render/Heroku) using `backend/Dockerfile`; set `CORS_ORIGINS` to the front-end URL.
- Frontend: Vercel, root directory `frontend`, env var `VITE_API_URL` = backend URL.
