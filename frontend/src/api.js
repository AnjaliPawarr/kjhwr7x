const BASE = import.meta.env.VITE_API_URL || "https://kjhwr7x.onrender.com";

export async function api(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${BASE}${path}${qs ? "?" + qs : ""}`);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

export const mw = (v) => (v == null ? "–" : Math.round(v).toLocaleString("en-GB"));
export const gw = (v) => (v == null ? "–" : (v / 1000).toFixed(2));
export const fmtTime = (iso) =>
  new Date(iso).toLocaleString("en-GB", { timeZone: "Europe/London", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
