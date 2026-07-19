import { Link } from "react-router-dom";
import { GUIDE, GLOSSARY, SECTION_HELP } from "../helpContent";

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

export default function Guide() {
  return (
    <>
      <h2>{GUIDE.title}</h2>
      <div className="card guide-intro">
        <p>{GUIDE.intro}</p>
        <p className="help-important">{GUIDE.important}</p>
      </div>

      <div className="grid cols-2" style={{ marginTop: "1rem" }}>
        <div className="card">
          <h3>Equities (US stocks)</h3>
          <p className="muted">
            Alpaca data and optional paper/live stock orders. Supports long and short.
            Hours follow the US stock market (regular session).
          </p>
          <Link to="/equities/live" className="guide-section-link" style={{ marginTop: "0.75rem" }}>
            <strong>Open Equities Live</strong>
            <span className="muted">Start here for stocks &amp; ETFs</span>
          </Link>
        </div>
        <div className="card">
          <h3>Crypto (Kraken spot)</h3>
          <p className="muted">
            Same probability ideas on crypto pairs like BTC/USD. Spot trading is
            <strong> long-only</strong> in this version (no shorting). Markets run 24/7.
          </p>
          <Link to="/crypto/live" className="guide-section-link" style={{ marginTop: "0.75rem" }}>
            <strong>Open Crypto Live</strong>
            <span className="muted">Start here for crypto pairs</span>
          </Link>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: "1rem" }}>
        {GUIDE.steps.map((s) => (
          <div className="card" key={s.title}>
            <h3>{s.title}</h3>
            <p>{s.body}</p>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Pages at a glance (same layout in each market)</h3>
        <p className="muted" style={{ marginBottom: "0.75rem" }}>
          Use the left nav: Equities and Crypto each have their own Live, Watchlist, Risk, etc.
          Click <strong>Help</strong> on any page for beginner field explanations.
        </p>
        <div className="guide-sections">
          {SECTION_LINKS.map(([slug, label]) => (
            <div key={slug} className="guide-section-link">
              <strong>{label}</strong>
              <span className="muted">{SECTION_HELP[slug === "risk" ? "risk" : slug]?.summary}</span>
              <span className="row" style={{ marginTop: "0.35rem" }}>
                <Link to={`/equities/${slug}`}>Equities</Link>
                <span className="muted">·</span>
                <Link to={`/crypto/${slug}`}>Crypto</Link>
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Beginner glossary</h3>
        <dl className="help-dl">
          {GLOSSARY.map((g) => (
            <div key={g.term} className="help-dl-row">
              <dt>{g.term}</dt>
              <dd>{g.meaning}</dd>
            </div>
          ))}
          <div className="help-dl-row">
            <dt>P(success)</dt>
            <dd>
              Shown as a percent in the tables (e.g. 25.7%). Under the hood it is a probability
              from 0 to 1 — 0.257 means about a 26% chance of hitting the target before the stop.
            </dd>
          </div>
        </dl>
      </div>
    </>
  );
}
