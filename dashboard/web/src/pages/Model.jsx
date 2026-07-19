import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";
import { api, fmtNum } from "../api";
import { PageHeader } from "../HelpPanel";
import { SECTION_HELP } from "../helpContent";

export default function ModelPage() {
  const [data, setData] = useState({ ready: false, metrics: null });
  useEffect(() => {
    api("/api/model/metrics").then(setData);
  }, []);

  const m = data.metrics || {};
  const buckets = m.calibration_buckets || [];

  return (
    <>
      <PageHeader title="Model" help={SECTION_HELP.model} />
      <div className="grid cols-3" style={{ marginBottom: "1rem" }}>
        <div className="card"><h3>Ready</h3><div className="stat">{data.ready ? "Yes" : "No"}</div></div>
        <div className="card"><h3>Brier</h3><div className="stat">{fmtNum(m.brier, 4)}</div></div>
        <div className="card"><h3>Beats baseline</h3><div className="stat">{m.beats_baseline ? "Yes" : "No"}</div></div>
      </div>
      <div className="grid cols-2" style={{ marginBottom: "1rem" }}>
        <div className="card">
          <h3>Base rate vs no-skill</h3>
          <p>Empirical: <strong>{fmtNum(m.base_rate, 3)}</strong></p>
          <p>No-skill baseline: <strong>{fmtNum(m.no_skill_baseline, 3)}</strong></p>
          <p>Hit rate when p≥0.5: <strong>{fmtNum(m.hit_rate_when_p_ge_50, 3)}</strong></p>
          <p className="muted">Artifact age: {data.model_mtime || "—"}</p>
        </div>
        <div className="card">
          <h3>Predicted vs realized edge</h3>
          <p>Mean predicted: <strong>{fmtNum(m.mean_predicted_edge, 5)}</strong></p>
          <p>Mean realized: <strong>{fmtNum(m.mean_realized_edge, 5)}</strong></p>
          <p>Train/test: {m.n_train}/{m.n_test}</p>
        </div>
      </div>
      <div className="card">
        <h3>Calibration buckets</h3>
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={buckets}>
              <CartesianGrid stroke="#243049" />
              <XAxis dataKey="lo" stroke="#93a0b8" />
              <YAxis stroke="#93a0b8" />
              <Tooltip />
              <Bar dataKey="hit_rate" fill="#5b8cff" name="hit_rate" />
              <Bar dataKey="avg_p" fill="#3dd68c" name="avg_p" />
              {m.no_skill_baseline != null && (
                <ReferenceLine y={m.no_skill_baseline} stroke="#f5c542" strokeDasharray="4 4" />
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}
