import { NavLink, Navigate, Route, Routes, useParams } from "react-router-dom";
import { MarketContext } from "./market";
import Live from "./pages/Live";
import Watchlist from "./pages/Watchlist";
import Positions from "./pages/Positions";
import Scanner from "./pages/Scanner";
import History from "./pages/History";
import Model from "./pages/Model";
import RiskControls from "./pages/RiskControls";
import Logs from "./pages/Logs";
import Guide from "./pages/Guide";

const SECTION_LINKS = [
  ["live", "Live"],
  ["watchlist", "Watchlist"],
  ["positions", "Positions"],
  ["scanner", "Scanner"],
  ["history", "History"],
  ["model", "Model"],
  ["risk", "Risk & Controls"],
  ["logs", "Logs"],
];

function MarketSection() {
  const { market } = useParams();
  const m = market === "crypto" ? "crypto" : "equities";
  const label = m === "crypto" ? "Crypto" : "Equities";
  const hint = m === "crypto" ? "Kraken spot · long-only · 24/7" : "Alpaca US stocks · long & short · RTH";

  return (
    <MarketContext.Provider value={m}>
      <div className="market-banner">
        <strong>{label}</strong>
        <span className="muted">{hint}</span>
      </div>
      <Routes>
        <Route path="live" element={<Live />} />
        <Route path="watchlist" element={<Watchlist />} />
        <Route path="positions" element={<Positions />} />
        <Route path="scanner" element={<Scanner />} />
        <Route path="history" element={<History />} />
        <Route path="model" element={<Model />} />
        <Route path="risk" element={<RiskControls />} />
        <Route path="logs" element={<Logs />} />
        <Route path="*" element={<Navigate to="live" replace />} />
      </Routes>
    </MarketContext.Provider>
  );
}

export default function App() {
  return (
    <div className="layout">
      <nav className="nav">
        <h1>Trade Probability</h1>
        <NavLink to="/guide">Guide</NavLink>

        <div className="nav-group">Equities</div>
        {SECTION_LINKS.map(([slug, label]) => (
          <NavLink key={`eq-${slug}`} to={`/equities/${slug}`}>
            {label}
          </NavLink>
        ))}

        <div className="nav-group">Crypto</div>
        {SECTION_LINKS.map(([slug, label]) => (
          <NavLink key={`cr-${slug}`} to={`/crypto/${slug}`}>
            {label}
          </NavLink>
        ))}
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/equities/live" replace />} />
          <Route path="/guide" element={<Guide />} />
          <Route path="/:market/*" element={<MarketSection />} />
        </Routes>
      </main>
    </div>
  );
}
