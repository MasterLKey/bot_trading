import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api, fmtNum } from "../api";
import { statusBadge } from "../badge";
import { PageHeader } from "../HelpPanel";
import { SECTION_HELP } from "../helpContent";

export default function History() {
  const [data, setData] = useState({ daily: [], fills: [], decisions: [] });
  const [status, setStatus] = useState("");

  useEffect(() => {
    async function load() { setData(await api("/api/history/pnl")); }
    load();
  }, []);

  const filtered = status
    ? data.decisions.filter((d) => d.status === status)
    : data.decisions;

  return (
    <>
      <PageHeader title="History" help={SECTION_HELP.history} />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3>Daily PnL</h3>
        <div style={{ width: "100%", height: 240 }}>
          <ResponsiveContainer>
            <LineChart data={data.daily}>
              <CartesianGrid stroke="#243049" />
              <XAxis dataKey="day" stroke="#93a0b8" />
              <YAxis stroke="#93a0b8" />
              <Tooltip />
              <Line type="monotone" dataKey="pnl" stroke="#5b8cff" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="row" style={{ marginBottom: "0.75rem" }}>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option>APPROVED</option>
          <option>WATCHLIST</option>
          <option>REJECTED</option>
        </select>
      </div>
      <div className="card">
        <h3>Decisions</h3>
        <table>
          <thead><tr><th>Time</th><th>Status</th><th>Symbol</th><th>Side</th><th>P</th><th>Edge $</th></tr></thead>
          <tbody>
            {filtered.slice(0, 100).map((d, i) => (
              <tr key={i}>
                <td className="muted">{String(d.timestamp).slice(0, 19)}</td>
                <td>{statusBadge(d.status)}</td>
                <td>{d.symbol}</td><td>{d.side}</td>
                <td>{fmtNum(d.p_success, 3)}</td>
                <td>{fmtNum(d.expected_dollar)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
