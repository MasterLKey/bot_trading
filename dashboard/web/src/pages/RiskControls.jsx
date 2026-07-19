import { useEffect, useState } from "react";
import { api, fmtNum } from "../api";
import { PageHeader } from "../HelpPanel";
import { SECTION_HELP } from "../helpContent";

export default function RiskControls() {
  const [state, setState] = useState(null);
  const [knobs, setKnobs] = useState({});
  const [msg, setMsg] = useState("");

  async function refresh() {
    const s = await api("/api/risk/state");
    setState(s);
    setKnobs(s.knobs || {});
  }
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, []);

  async function toggleKill() {
    await api("/api/control/kill", {
      method: "POST",
      body: JSON.stringify({ engage: !state.kill, reason: "dashboard" }),
    });
    refresh();
  }

  async function saveKnobs() {
    const body = {};
    for (const k of ["target_pct", "stop_pct", "stake_quote", "horizon_minutes", "p_min", "edge_approve", "fee_buffer_pct"]) {
      if (knobs[k] != null && knobs[k] !== "") body[k] = Number(knobs[k]);
    }
    await api("/api/control/knobs", { method: "POST", body: JSON.stringify(body) });
    setMsg("Knobs saved");
    refresh();
  }

  if (!state) {
    return (
      <>
        <PageHeader title="Risk & Controls" help={SECTION_HELP.risk} />
        <p className="muted">Loading…</p>
      </>
    );
  }
  const p = state.portfolio || {};

  return (
    <>
      <PageHeader title="Risk & Controls" help={SECTION_HELP.risk} />
      <div className="grid cols-3" style={{ marginBottom: "1rem" }}>
        <div className="card">
          <h3>Mode</h3>
          <div className="stat">{state.mode}</div>
          <p className="muted">Change mode via .env + restart</p>
        </div>
        <div className="card">
          <h3>Kill switch</h3>
          <div className="stat" style={{ color: state.kill ? "var(--red)" : "var(--green)" }}>
            {state.kill ? "ENGAGED" : "clear"}
          </div>
          <button className={state.kill ? "ghost" : "danger"} onClick={toggleKill} style={{ marginTop: "0.5rem" }}>
            {state.kill ? "Clear kill" : "Engage kill"}
          </button>
        </div>
        <div className="card">
          <h3>Gross exposure</h3>
          <div className="stat">${fmtNum(p.gross_exposure, 0)}</div>
          <p className="muted">cap ${fmtNum(state.limits.max_gross_exposure, 0)}</p>
        </div>
      </div>
      <div className="grid cols-2">
        <div className="card">
          <h3>Portfolio</h3>
          <p>Equity: ${fmtNum(p.equity, 0)}</p>
          <p>Cash: ${fmtNum(p.cash, 0)}</p>
          <p>Daily PnL: ${fmtNum(p.daily_pnl, 2)}</p>
          <p>Drawdown: {fmtNum(p.drawdown_pct, 2)}% (cap {state.limits.max_drawdown_pct}%)</p>
        </div>
        <div className="card">
          <h3>Knobs</h3>
          {["target_pct", "stop_pct", "stake_quote", "horizon_minutes", "p_min", "edge_approve", "fee_buffer_pct"].map((k) => (
            <div className="row" key={k} style={{ marginBottom: "0.4rem" }}>
              <label style={{ width: 140 }} className="muted">{k}</label>
              <input
                value={knobs[k] ?? ""}
                onChange={(e) => setKnobs({ ...knobs, [k]: e.target.value })}
              />
            </div>
          ))}
          <button onClick={saveKnobs}>Save knobs</button>
          {msg && <span className="muted" style={{ marginLeft: 8 }}>{msg}</span>}
        </div>
      </div>
    </>
  );
}
