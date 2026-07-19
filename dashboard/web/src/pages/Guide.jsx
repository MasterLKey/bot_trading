import { Link } from "react-router-dom";
import { GUIDE, GLOSSARY, SECTION_HELP } from "../helpContent";

const SECTION_LINKS = [
  ["/", "live", "Live"],
  ["/watchlist", "watchlist", "Watchlist"],
  ["/positions", "positions", "Positions"],
  ["/scanner", "scanner", "Scanner"],
  ["/history", "history", "History"],
  ["/model", "model", "Model"],
  ["/risk", "risk", "Risk & Controls"],
  ["/logs", "logs", "Logs"],
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
        {GUIDE.steps.map((s) => (
          <div className="card" key={s.title}>
            <h3>{s.title}</h3>
            <p>{s.body}</p>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Pages at a glance</h3>
        <p className="muted" style={{ marginBottom: "0.75rem" }}>
          Open any page, then click <strong>Help — what is this page?</strong> for a beginner explanation of every field.
        </p>
        <div className="guide-sections">
          {SECTION_LINKS.map(([to, key, label]) => (
            <Link key={key} to={to} className="guide-section-link">
              <strong>{label}</strong>
              <span className="muted">{SECTION_HELP[key]?.summary}</span>
            </Link>
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
        </dl>
      </div>
    </>
  );
}
