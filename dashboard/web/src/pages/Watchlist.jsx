import { useEffect, useState } from "react";
import { api, fmtNum, fmtPct, fmtProb, withMarket } from "../api";
import { statusBadge } from "../badge";
import { PageHeader } from "../HelpPanel";
import { SECTION_HELP } from "../helpContent";
import { useMarket } from "../market";

export default function Watchlist() {
  const market = useMarket();
  const [data, setData] = useState({ manual: [], cards: [] });
  const [symbol, setSymbol] = useState("");

  async function refresh() {
    setData(await api(withMarket("/api/watchlist", market)));
  }
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, [market]);

  async function add() {
    if (!symbol.trim()) return;
    await api(withMarket("/api/control/watchlist", market), {
      method: "POST",
      body: JSON.stringify({ symbol, action: "add" }),
    });
    setSymbol("");
    refresh();
  }
  async function remove(sym) {
    await api(withMarket("/api/control/watchlist", market), {
      method: "POST",
      body: JSON.stringify({ symbol: sym, action: "remove" }),
    });
    refresh();
  }

  const placeholder = market === "crypto" ? "BTC/USD" : "AAPL";

  return (
    <>
      <PageHeader title="Watchlist" help={SECTION_HELP.watchlist} />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3>Manual symbols ({market})</h3>
        <div className="row" style={{ marginBottom: "0.75rem" }}>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder={placeholder}
          />
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
                <td>{fmtProb(d.p_success)}</td><td>{fmtPct(d.expected_edge)}</td>
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
