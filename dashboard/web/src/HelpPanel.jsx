import { useState } from "react";

export default function HelpPanel({ help, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!help) return null;

  return (
    <div className={`help-panel ${open ? "open" : ""}`}>
      <button
        type="button"
        className="help-toggle ghost"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="help-icon">?</span>
        {open ? "Hide help" : "Help — what is this page?"}
      </button>
      {open && (
        <div className="help-body">
          <p className="help-summary">{help.summary}</p>
          {(help.paragraphs || []).map((p) => (
            <p key={p}>{p}</p>
          ))}
          {help.bullets?.length > 0 && (
            <dl className="help-dl">
              {help.bullets.map((b) => (
                <div key={b.label} className="help-dl-row">
                  <dt>{b.label}</dt>
                  <dd>{b.text}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
    </div>
  );
}

export function PageHeader({ title, help, extra }) {
  return (
    <div className="page-header">
      <div className="page-header-top">
        <h2>{title}</h2>
        {extra}
      </div>
      <HelpPanel help={help} />
    </div>
  );
}
