import { NavLink, Route, Routes } from "react-router-dom";
import Live from "./pages/Live";
import Watchlist from "./pages/Watchlist";
import Positions from "./pages/Positions";
import Scanner from "./pages/Scanner";
import History from "./pages/History";
import Model from "./pages/Model";
import RiskControls from "./pages/RiskControls";
import Logs from "./pages/Logs";

const links = [
  ["/", "Live"],
  ["/watchlist", "Watchlist"],
  ["/positions", "Positions"],
  ["/scanner", "Scanner"],
  ["/history", "History"],
  ["/model", "Model"],
  ["/risk", "Risk & Controls"],
  ["/logs", "Logs"],
];

export default function App() {
  return (
    <div className="layout">
      <nav className="nav">
        <h1>Trade Probability</h1>
        {links.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"}>
            {label}
          </NavLink>
        ))}
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<Live />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/positions" element={<Positions />} />
          <Route path="/scanner" element={<Scanner />} />
          <Route path="/history" element={<History />} />
          <Route path="/model" element={<Model />} />
          <Route path="/risk" element={<RiskControls />} />
          <Route path="/logs" element={<Logs />} />
        </Routes>
      </main>
    </div>
  );
}
