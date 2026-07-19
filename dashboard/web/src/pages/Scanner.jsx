import { useEffect, useState } from "react";
import { api, fmtNum, withMarket } from "../api";
import { PageHeader } from "../HelpPanel";
import { SECTION_HELP } from "../helpContent";
import { useMarket } from "../market";

export default function Scanner() {
  const market = useMarket();
  const [data, setData] = useState({ candidates: [], ws_symbols: [] });
  useEffect(() => {
    async function load() { setData(await api(withMarket("/api/scan", market))); }
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [market]);

  return (
    <>
      <PageHeader title="Scanner" help={SECTION_HELP.scanner} />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3>
          {market === "crypto" ? "Hot pairs" : "WebSocket slots"} ({data.ws_symbols.length}
          {market === "equities" ? "/30" : ""})
        </h3>
        <div className="row">
          {data.ws_symbols.map((s) => <span key={s} className="badge APPROVED">{s}</span>)}
          {!data.ws_symbols.length && <span className="muted">None allocated yet — start the {market} stream</span>}
        </div>
      </div>
      <div className="card">
        <h3>Latest SCAN ranking ({market})</h3>
        <table>
          <thead>
            <tr><th>#</th><th>Symbol</th><th>Price</th><th>$-vol</th><th>Liq score</th><th>News</th><th>Shortable</th><th>Why</th></tr>
          </thead>
          <tbody>
            {data.candidates.map((c, i) => (
              <tr key={c.symbol}>
                <td>{i + 1}</td>
                <td>{c.symbol}</td>
                <td>{fmtNum(c.last_price)}</td>
                <td>{fmtNum(c.dollar_volume, 0)}</td>
                <td>{fmtNum(c.liquidity_score, 2)}</td>
                <td>{fmtNum(c.news_heat, 2)}</td>
                <td>{c.shortable && c.easy_to_borrow ? "ETB" : "—"}</td>
                <td className="muted">{(c.why || []).join(", ")}</td>
              </tr>
            ))}
            {!data.candidates.length && <tr><td colSpan={8} className="muted">No scan snapshot yet</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
