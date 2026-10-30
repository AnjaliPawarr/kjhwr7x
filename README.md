WindWise: GB Day-Ahead Wind Forecast Portal

A decision-support web app for a UK electricity utility's day-ahead trading desk. It shows which national wind forecast was actually available when the purchase decision had to be made, and measures how accurate those forecasts were across January 2026.

Data comes only from Elexon BMRS: WINDFOR (forecasts) and FUELHH (actual generation, fuelType = WIND).

	
Live app	<https://kjhwr7x.vercel.app/>
Demo video	<>

The backend runs on a free Render instance that sleeps when idle. The first request after a quiet period can take 30 to 60 seconds. If the page shows an error, wait a moment and refresh.

1. Problem

A buying team must commit day-ahead volumes before the auction closes on the morning of day D-1. Wind output is weather-dependent, so the team relies on published forecasts and needs to know two things:

What is the latest wind forecast available at decision time?
How wrong have those forecasts been, in numbers? (so the error can be priced into the purchase)
2. What the app does
Decision view: pick a delivery day and see the 24-hour forecast that was available at the chosen cutoff, the publication time of each forecast, how many hours ahead it was made, an error band, and (for reference) what actually happened.
Forecast accuracy view: MAE, RMSE, bias, P90 and P95 absolute error and MAPE for the month, a forecast-vs-actual chart, and error broken down by forecast lead time, hour of day, wind level and delivery day.
Configurable decision cutoff: the time on D-1 (London time) after which newer forecasts are ignored. Default is 09:00. Changing it recalculates both views.
3. Key logic

For each delivery hour on day D, the forecast used is the one with the latest publishTime that is at or before the decision cutoff on day D-1 (London time). Forecasts published after the cutoff were not available to the desk, so using them would make the accuracy look better than it really was (look-ahead leakage).

The core function is select_forecasts() in backend/app/analysis.py. All raw forecast publications are stored; selection happens at request time, which is what lets the cutoff be changed from the UI.

Assumptions
Decision cutoff: 09:00 London time on D-1 by default (day-ahead auctions close in the morning). This is an assumption and is adjustable in the UI.
FUELHH is half-hourly and WINDFOR is hourly, so actuals are averaged to hourly values.
Error = forecast − actual. Positive bias means the forecast was higher than actual output.
MAPE ignores hours where actual generation is 500 MW or less, to avoid dividing by near-zero values.
The "likely range" band in the Decision view is the P10 to P90 of historical forecast error by hour of day, computed from the other days of the month (the displayed day is excluded).
Scope is national-level wind only and January 2026 only.
4. Results (January 2026, 09:00 cutoff)
Metric	Value
Hours evaluated	744 / 744
MAE	2,142 MW
RMSE	2,612 MW
Bias (forecast − actual)	+1,852 MW (forecast higher than actual)
P90 absolute error	4,300 MW
P95 absolute error	5,307 MW
MAPE	22.4 %

What stands out: the forecasts follow the shape of actual output well, but overstate it, mainly on windy days, and errors are larger in the early-morning hours. The cause of the upward bias has not been established here (see Limitations).

5. Architecture
Elexon BMRS API
   │  scripts/fetch_data.py  (run once, saves raw CSVs)
   ▼
backend/data/forecasts_raw.csv + actuals_raw.csv
   │
   ▼
FastAPI  ──  analysis.py  (select forecast ≤ cutoff, join actuals, metrics)
   │  JSON over HTTP (CORS-restricted)
   ▼
React (Vite + Recharts)  ──  Decision view / Accuracy view
6. Repository layout
.
├── backend/
│   ├── app/
│   │   ├── analysis.py          # forecast selection, hourly actuals, joins, error metrics
│   │   └── main.py              # FastAPI endpoints and CORS config
│   ├── scripts/
│   │   └── fetch_data.py        # downloads raw Elexon data into backend/data/
│   ├── tests/
│   │   └── test_selection.py    # unit tests for the selection and error logic
│   ├── data/                    # forecasts_raw.csv, actuals_raw.csv (committed so deployment needs no network)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Decision and Accuracy views, cutoff state
│   │   ├── api.js               # API client and number/time formatting
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile               # Node build, served by Nginx
├── docker-compose.yml
└── README.md
API endpoints
Endpoint	Purpose
GET /api/health	Liveness check
GET /api/meta?cutoff=HH:MM	Available delivery days for the cutoff
GET /api/decision?day=YYYY-MM-DD&cutoff=HH:MM	Hour-by-hour forecast, publish time, lead time, error band, actuals
GET /api/accuracy?cutoff=HH:MM	Overall metrics plus breakdowns by hour, lead time, wind level and day
GET /api/timeseries?cutoff=HH:MM	Full-month forecast vs actual series
7. Run locally

Prerequisites: Python 3.12 (recommended), Node.js 20+, and Docker Desktop for the Docker route.

Step 1: get the data (once)

The repository already includes the CSVs in backend/data/. To regenerate them from Elexon:

bash
cd backend
pip install -r requirements.txt
python scripts/fetch_data.py
Option A: Docker Compose
bash
docker compose up --build
App: http://localhost:8080
API: http://localhost:8000 (health: http://localhost:8000/api/health)
Option B: without Docker
bash
# terminal 1: backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# terminal 2: frontend
cd frontend
npm install
npm run dev

Open http://localhost:5173.

8. Tests
bash
cd backend
pip install -r requirements.txt
pytest

The tests cover the central rules: the latest eligible forecast is chosen, forecasts published after the cutoff are ignored, a missing forecast yields no row, the selection changes when the cutoff changes, and actuals are averaged to hourly before the error is computed.

9. Deployment

Backend (Render, Docker): New Web Service, connect the repo, Root Directory backend, Language Docker. Set the environment variable:

CORS_ORIGINS = the front-end URL (no trailing slash). Several origins can be given, separated by commas.

Frontend (Vercel): New Project, import the repo, Root Directory frontend, framework preset Vite. Set the environment variable before the first build:

VITE_API_URL = the Render backend URL (no trailing slash).

VITE_API_URL is baked in at build time, so change it, then redeploy.

10. Limitations and next steps
One month only. The conclusions are about January 2026, not a general statement about forecast quality.
Cutoff is an assumption. Results depend on it; the UI lets you test other times.
The upward bias is unexplained. Possible causes include differences between what the forecast and the metered output represent (for example, output reduced by grid constraints), but this has not been verified. Next step: read the Elexon dataset definitions and compare against additional data.
No demand or price data, by design of the brief. The app shows the wind side only, not the residual demand the desk has to buy.
Error band is based on the other days of one month, so it is a rough guide, not a statistical guarantee.
Free hosting means slow first loads after idle periods.
11. AI tools disclosure

AI tools were used in building this project: Claude (Anthropic) helped design the architecture and write parts of the backend, frontend and documentation. All code was run, reviewed and tested by me. <EDIT THIS LINE to describe in your own words what you reviewed or changed.>

12. Data attribution

Contains BMRS data © Elexon Limited copyright and database right 2026.
