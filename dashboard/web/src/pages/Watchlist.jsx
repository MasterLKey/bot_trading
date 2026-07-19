import { useEffect, useState } from "react";
import { api, fmtNum, fmtPct } from "../api";
import { statusBadge } from "../badge";
import { PageHeader } from "../HelpPanel";
import { SECTION_HELP } from "../helpContent";

export default function Watchlist() {
  const [data, setData] = useState({ manual: [], cards: [] });
  const [symbol, setSymbol] = useState("");

  async function refresh() {
    setData(await api("/api/watchlist"));
  }
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, []);

  async function add() {
    if (!symbol.trim()) return;
    await api("/api/control/watchlist", { method: "POST", body: JSON.stringify({ symbol, action: "add" }) });
    setSymbol("");
    refresh();
  }
  async function remove(sym) {
    await api("/api/control/watchlist", { method: "POST", body: JSON.stringify({ symbol: sym, action: "remove" }) });
    refresh();
  }

  return (
    <>
      <PageHeader title="Watchlist" help={SECTION_HELP.watchlist} />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3>Manual symbols</h3>
        <div className="row" style={{ marginBottom: "0.75rem" }}>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="SYMBOL" />
          <button onClick={add}>Add</button>
        </div>
        <div className="row">
          {data.manual.map((s) => (
            <button key={s} className="ghost" onClick={() => remove(s)}>{s} ×</button>
          ))}
          {!data.manual.length && <span className="muted">Empty</span>}
        </div>
      </div>
      <div className="card">
        <h3>WATCHLIST decision cards</h3>
        <table>
          <thead><tr><th>Status</th><th>Symbol</th><th>Side</th><th>P</th><th>Edge</th><th>Entry</th><th>Reasons</th></tr></thead>
          <tbody>
            {data.cards.map((d, i) => (
              <tr key={i}>
                <td>{statusBadge(d.status)}</td>
                <td>{d.symbol}</td><td>{d.side}</td>
                <td>{fmtNum(d.p_success, 3)}</td><td>{fmtPct(d.expected_edge)}</td>
                <td>{fmtNum(d.entry)}</td>
                <td className="muted">{(d.reasons || []).join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
