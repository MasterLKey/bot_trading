import { useEffect, useMemo, useState } from "react";
import { fmtNum, fmtPct } from "../api";
import { statusBadge } from "../badge";

export default function Live() {
  const [decisions, setDecisions] = useState([]);
  const [positions, setPositions] = useState([]);
  const [kill, setKill] = useState(false);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.decisions) setDecisions(msg.decisions);
      if (msg.positions) setPositions(msg.positions);
      if (typeof msg.kill === "boolean") setKill(msg.kill);
    };
    return () => ws.close();
  }, []);

  const counts = useMemo(() => {
    const c = { APPROVED: 0, WATCHLIST: 0, REJECTED: 0 };
    for (const d of decisions) c[d.status] = (c[d.status] || 0) + 1;
    return c;
  }, [decisions]);

  return (
    <>
      <h2>Live decisions {connected ? "●" : "○"} {kill && <span className="badge REJECTED">KILL</span>}</h2>
      <div className="grid cols-3" style={{ marginBottom: "1rem" }}>
        <div className="card"><h3>Approved</h3><div className="stat" style={{ color: "var(--green)" }}>{counts.APPROVED || 0}</div></div>
        <div className="card"><h3>Watchlist</h3><div className="stat" style={{ color: "var(--amber)" }}>{counts.WATCHLIST || 0}</div></div>
        <div className="card"><h3>Rejected</h3><div className="stat" style={{ color: "var(--red)" }}>{counts.REJECTED || 0}</div></div>
      </div>
      <div className="card">
        <h3>Decision stream</h3>
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Status</th><th>Symbol</th><th>Side</th>
              <th>P(success)</th><th>Edge</th><th>Entry</th><th>Target</th><th>Stop</th><th>Stake</th><th>Reasons</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((d, i) => (
              <tr key={`${d.timestamp}-${d.symbol}-${d.side}-${i}`}>
                <td className="muted">{String(d.timestamp).slice(11, 19)}</td>
                <td>{statusBadge(d.status)}</td>
                <td>{d.symbol}</td>
                <td>{d.side}</td>
                <td>{fmtNum(d.p_success, 3)}</td>
                <td>{fmtPct(d.expected_edge)}</td>
                <td>{fmtNum(d.entry)}</td>
                <td>{fmtNum(d.target)}</td>
                <td>{fmtNum(d.stop)}</td>
                <td>${fmtNum(d.stake, 0)}</td>
                <td className="muted">{(d.reasons || []).join("; ")}</td>
              </tr>
            ))}
            {!decisions.length && <tr><td colSpan={11} className="muted">Waiting for stream…</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Open positions ({positions.length})</h3>
        <table>
          <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Avg</th><th>Price</th><th>uPnL</th></tr></thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.symbol}>
                <td>{p.symbol}</td><td>{p.side}</td><td>{p.qty}</td>
                <td>{fmtNum(p.avg_entry)}</td><td>{fmtNum(p.current_price)}</td>
                <td>{fmtNum(p.unrealized_pl)}</td>
              </tr>
            ))}
            {!positions.length && <tr><td colSpan={6} className="muted">No open positions</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
