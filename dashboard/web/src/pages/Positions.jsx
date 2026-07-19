import { useEffect, useRef, useState } from "react";
import { createChart } from "lightweight-charts";
import { api, fmtNum, withMarket } from "../api";
import { PageHeader } from "../HelpPanel";
import { SECTION_HELP } from "../helpContent";
import { useMarket } from "../market";

export default function Positions() {
  const market = useMarket();
  const [positions, setPositions] = useState([]);
  const chartRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    async function load() {
      setPositions(await api(withMarket("/api/positions", market)));
    }
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [market]);

  useEffect(() => {
    if (!containerRef.current) return;
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 280,
      layout: { background: { color: "#121a2b" }, textColor: "#93a0b8" },
      grid: { vertLines: { color: "#243049" }, horzLines: { color: "#243049" } },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#3dd68c",
      downColor: "#ff6b7a",
      borderVisible: false,
      wickUpColor: "#3dd68c",
      wickDownColor: "#ff6b7a",
    });
    // Placeholder candles from position entries when no bar history in browser
    const now = Math.floor(Date.now() / 1000);
    const candles = positions.length
      ? positions.map((p, i) => {
          const c = Number(p.current_price || p.avg_entry || 100);
          return { time: now - (positions.length - i) * 60, open: c * 0.998, high: c * 1.004, low: c * 0.996, close: c };
        })
      : [{ time: now - 120, open: 100, high: 101, low: 99, close: 100.5 }, { time: now - 60, open: 100.5, high: 101.2, low: 100.1, close: 100.8 }];
    series.setData(candles);
    if (positions[0]) {
      const p = positions[0];
      series.createPriceLine({ price: Number(p.avg_entry), color: "#5b8cff", title: "entry" });
    }
    chartRef.current = chart;
    const onResize = () => chart.applyOptions({ width: containerRef.current.clientWidth });
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [positions]);

  return (
    <>
      <PageHeader title="Positions" help={SECTION_HELP.positions} />
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3>Price overlay</h3>
        <div ref={containerRef} />
      </div>
      <div className="card">
        <table>
          <thead>
            <tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Avg entry</th><th>Price</th><th>Market value</th><th>uPnL</th></tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.symbol}>
                <td>{p.symbol}</td><td>{p.side}</td><td>{p.qty}</td>
                <td>{fmtNum(p.avg_entry)}</td><td>{fmtNum(p.current_price)}</td>
                <td>{fmtNum(p.market_value)}</td><td>{fmtNum(p.unrealized_pl)}</td>
              </tr>
            ))}
            {!positions.length && <tr><td colSpan={7} className="muted">No positions (advisory or flat)</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
