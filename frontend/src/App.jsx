import { useEffect, useState } from "react";
import {
  ResponsiveContainer, ComposedChart, LineChart, BarChart, Area, Line, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { api, mw, gw, fmtTime } from "./api.js";

function useApi(path, params, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    api(path, params)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((e) => alive && setState({ data: null, error: e.message, loading: false }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

const Kpi = ({ label, value, unit, hint }) => (
  <div className="kpi">
    <div className="kpi-label">{label}</div>
    <div className="kpi-value">{value}<span>{unit}</span></div>
    {hint && <div className="kpi-hint">{hint}</div>}
  </div>
);

const Status = ({ s }) =>
  s.loading ? <p className="muted">Loading…</p> : s.error ? <p className="error">Error: {s.error}</p> : null;

function Decision({ cutoff, days }) {
  const [day, setDay] = useState(days[days.length - 1] || "2026-01-15");
  const s = useApi("/api/decision", { day, cutoff }, [day, cutoff]);
  const d = s.data;
  const rows = d ? d.rows.map((r) => ({
    ...r, label: String(r.hour).padStart(2, "0") + ":00",
    band: r.band_low != null ? [r.band_low, r.band_high] : null,
  })) : [];

  return (
    <section>
      <div className="controls">
        <label>Delivery day
          <select value={day} onChange={(e) => setDay(e.target.value)}>
            {days.map((x) => <option key={x}>{x}</option>)}
          </select>
        </label>
      </div>
      <Status s={s} />
      {d && (
        <>
          <p className="callout">
            Using forecasts published up to <b>{fmtTime(d.summary.cutoff)}</b> (London) on the day before delivery.
            Latest publication used: <b>{fmtTime(d.summary.latest_publish)}</b>.
          </p>
          <div className="kpis">
            <Kpi label="Average forecast wind" value={gw(d.summary.mean_forecast)} unit="GW" />
            <Kpi label="Lowest hour" value={gw(d.summary.min_forecast)} unit="GW" />
            <Kpi label="Highest hour" value={gw(d.summary.max_forecast)} unit="GW" />
            <Kpi label="Hours covered" value={d.summary.hours_covered} unit="/ 24" />
          </div>
          <div className="card">
            <h3>Forecast with typical error range (P10–P90, from other days)</h3>
            <ResponsiveContainer width="100%" height={340}>
              <ComposedChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis tickFormatter={(v) => gw(v)} unit=" GW" width={80} />
                <Tooltip formatter={(v) => (Array.isArray(v) ? v.map(mw).join(" – ") : mw(v)) + " MW"} />
                <Legend />
                <Area dataKey="band" name="Likely actual range" fill="#9fd8cc" stroke="none" />
                <Line dataKey="forecast" name="Forecast" stroke="#0b6e5b" strokeWidth={2} dot={false} />
                <Line dataKey="actual" name="Actual (for reference)" stroke="#d9480f" strokeWidth={2} dot={false} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="card">
            <h3>Hour-by-hour</h3>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Hour</th><th>Forecast (MW)</th><th>Likely range (MW)</th><th>Published</th><th>Lead (h)</th><th>Actual (MW)</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.startTime}>
                      <td>{r.label}</td><td>{mw(r.forecast)}</td>
                      <td>{r.band ? `${mw(r.band_low)} – ${mw(r.band_high)}` : "–"}</td>
                      <td>{fmtTime(r.publishTime)}</td><td>{r.lead_hours}</td><td>{mw(r.actual)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function BarCard({ title, data, xKey }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis tickFormatter={(v) => gw(v)} unit=" GW" width={80} />
          <Tooltip formatter={(v) => mw(v) + " MW"} />
          <Legend />
          <Bar dataKey="mae" name="MAE" fill="#0b6e5b" />
          <Bar dataKey="p90_abs" name="P90 abs error" fill="#9fd8cc" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Accuracy({ cutoff }) {
  const a = useApi("/api/accuracy", { cutoff }, [cutoff]);
  const t = useApi("/api/timeseries", { cutoff }, [cutoff]);
  const o = a.data?.overall;
  return (
    <section>
      <Status s={a} />
      {o && (
        <>
          <div className="kpis">
            <Kpi label="Matched hours" value={o.n} unit="" />
            <Kpi label="MAE" value={mw(o.mae)} unit="MW" hint="average miss" />
            <Kpi label="RMSE" value={mw(o.rmse)} unit="MW" hint="punishes big misses" />
            <Kpi label="Bias" value={(o.bias > 0 ? "+" : "") + mw(o.bias)} unit="MW" hint={o.bias > 0 ? "forecast above actual" : "forecast below actual"} />
            <Kpi label="P90 error" value={mw(o.p90_abs)} unit="MW" hint="9 in 10 hours within" />
            <Kpi label="P95 error" value={mw(o.p95_abs)} unit="MW" hint="19 in 20 hours within" />
            <Kpi label="MAPE" value={o.mape_pct == null ? "–" : o.mape_pct.toFixed(1)} unit="%" hint="hours with actual > 0.5 GW" />
          </div>
          {t.data && (
            <div className="card">
              <h3>Forecast vs actual – January 2026</h3>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={t.data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="startTime" tickFormatter={(v) => v.slice(5, 10)} minTickGap={40} />
                  <YAxis tickFormatter={(v) => gw(v)} unit=" GW" width={80} />
                  <Tooltip labelFormatter={fmtTime} formatter={(v) => mw(v) + " MW"} />
                  <Legend />
                  <Line dataKey="actual" name="Actual" stroke="#d9480f" dot={false} strokeWidth={1.5} />
                  <Line dataKey="forecast" name="Forecast" stroke="#0b6e5b" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          <BarCard title="Error by forecast lead time (how far ahead it was published)" data={a.data.by_horizon} xKey="key" />
          <BarCard title="Error by hour of day" data={a.data.by_hour} xKey="key" />
          <BarCard title="Error by actual wind level" data={a.data.by_wind_level} xKey="key" />
          <BarCard title="Error by delivery day" data={a.data.by_day} xKey="day" />
        </>
      )}
    </section>
  );
}

export default function App() {
  const [tab, setTab] = useState("decision");
  const [cutoff, setCutoff] = useState("09:00");
  const meta = useApi("/api/meta", { cutoff }, [cutoff]);

  return (
    <div className="page">
      <header>
          <div>
            <h1>WindWise Forecast Portal</h1>
            <p className="muted">
              GB Day-Ahead Wind Generation Analytics · January 2026
            </p>
          </div>
      </header>
      <nav>
        <button className={tab === "decision" ? "on" : ""} onClick={() => setTab("decision")}>Decision view</button>
        <button className={tab === "accuracy" ? "on" : ""} onClick={() => setTab("accuracy")}>Forecast accuracy</button>
      </nav>
      <Status s={meta} />
      {meta.data && (tab === "decision"
        ? <Decision key={cutoff} cutoff={cutoff} days={meta.data.days} />
        : <Accuracy cutoff={cutoff} />)}
      <footer className="muted">
        Source: Elexon BMRS (WINDFOR forecasts, FUELHH actuals, wind only). Forecast = latest publication at or before the cutoff.
        Error = forecast − actual. Actuals averaged to hourly.
      </footer>
    </div>
  );
}
