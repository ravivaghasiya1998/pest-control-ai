import { useState, useEffect } from "react";
import { api } from "../api.js";

function timeAgo(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function Reports() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState("");
  const [selected, setSelected] = useState(null);
  const [customQ, setCustomQ] = useState("");

  async function load() {
    setLoading(true);
    try { const d = await api.reports(); setReports(d.items || []); } catch { /* ignore */ } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function generate(type, question = "") {
    setGenerating(type);
    try {
      const report = await api.generateReport(type, question);
      setReports(r => [report, ...r]);
      setSelected(report);
    } catch { /* ignore */ } finally { setGenerating(""); }
  }

  const REPORT_TYPES = [
    { type: "weekly", label: "📊 Weekly Report", hint: "Jobs, revenue, top pest types, technician utilisation" },
    { type: "upsell", label: "💰 Upsell Opportunities", hint: "Customers due for re-treatment or contract renewal" },
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">AI Reports</div>
          <div className="page-subtitle">LLM-generated business intelligence — powered by your chosen AI provider</div>
        </div>
        <button className="btn btn-secondary" onClick={load}>↻</button>
      </div>

      {/* Generate buttons */}
      <div className="card section-gap">
        <div className="card-header">Generate Report</div>
        <div className="card-body">
          <div className="btn-group" style={{ marginBottom: 12 }}>
            {REPORT_TYPES.map(r => (
              <button key={r.type} className="btn btn-primary" disabled={!!generating}
                onClick={() => generate(r.type)}>
                {generating === r.type ? "Generating…" : r.label}
              </button>
            ))}
          </div>
          <p className="text-sm text-muted" style={{ marginBottom: 12 }}>
            {REPORT_TYPES.map(r => <span key={r.type} style={{ marginRight: 16 }}><strong>{r.label.split(" ").slice(1).join(" ")}:</strong> {r.hint}</span>)}
          </p>
        </div>
      </div>

      <div className="grid-2">
        {/* Reports list */}
        <div className="card" style={{ maxHeight: 500, overflow: "auto" }}>
          <div className="card-header">Report History</div>
          {loading ? <div className="loading">Loading…</div> : (
            <div>
              {reports.length === 0 ? (
                <div className="empty-state"><div className="empty-icon">📈</div>No reports yet — generate one above</div>
              ) : reports.map(r => (
                <div key={r.id}
                  style={{
                    padding: "12px 16px", cursor: "pointer", borderBottom: "1px solid var(--border)",
                    background: selected?.id === r.id ? "var(--green-light)" : "transparent",
                    transition: "background .15s",
                  }}
                  onClick={() => setSelected(r)}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{r.title}</div>
                  <div className="flex gap-8" style={{ marginTop: 4 }}>
                    <span className={`badge badge-${r.report_type === "weekly" ? "scheduled" : r.report_type === "upsell" ? "hot" : "new"}`}>{r.report_type}</span>
                    <span className="text-sm text-muted">{timeAgo(r.generated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Report detail */}
        <div className="card">
          <div className="card-header">
            {selected ? selected.title : "Select a report"}
          </div>
          <div className="card-body">
            {!selected ? (
              <div className="empty-state" style={{ padding: 24 }}>
                <div className="empty-icon">📄</div>
                Click a report to view the full analysis
              </div>
            ) : (
              <>
                {selected.content?.metrics && (
                  <div style={{ marginBottom: 16 }}>
                    <div className="text-sm text-muted" style={{ marginBottom: 6 }}>Key Metrics</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      {Object.entries(selected.content.metrics).filter(([, v]) => typeof v === "number").slice(0, 6).map(([k, v]) => (
                        <div key={k} style={{ padding: "8px 10px", background: "var(--bg)", borderRadius: 7 }}>
                          <div style={{ fontSize: 18, fontWeight: 800, color: "var(--green)" }}>{typeof v === "number" && v > 1000 ? `€${v.toLocaleString()}` : v}</div>
                          <div className="text-sm text-muted">{k.replace(/_/g, " ")}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selected.content?.summary && (
                  <div style={{ marginBottom: 16 }}>
                    <div className="text-sm text-muted" style={{ marginBottom: 6 }}>Summary</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      {Object.entries(selected.content.summary).map(([k, v]) => (
                        <div key={k} style={{ padding: "8px 10px", background: "var(--bg)", borderRadius: 7 }}>
                          <div style={{ fontSize: 18, fontWeight: 800, color: "var(--green)" }}>
                            {typeof v === "number" && v > 1000 ? `€${v.toLocaleString()}` : v}
                          </div>
                          <div className="text-sm text-muted">{k.replace(/_/g, " ")}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selected.content?.narrative && (
                  <div>
                    <div className="text-sm text-muted" style={{ marginBottom: 6 }}>AI Analysis</div>
                    <div className="report-narrative">{selected.content.narrative}</div>
                  </div>
                )}

                {selected.content?.opportunities?.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div className="text-sm text-muted" style={{ marginBottom: 8 }}>Opportunities ({selected.content.opportunities.length})</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {selected.content.opportunities.slice(0, 5).map((o, i) => (
                        <div key={i} style={{ padding: "10px 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13 }}>
                          <div style={{ fontWeight: 600 }}>{o.customer_name}</div>
                          <div className="text-muted text-sm">{o.reason}</div>
                          <div style={{ marginTop: 4, color: "var(--green)", fontWeight: 600 }}>→ {o.recommended_action}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
