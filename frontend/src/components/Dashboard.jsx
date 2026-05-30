import { useState, useEffect } from "react";
import { api } from "../api.js";

function ActivityDot({ category }) {
  return <span className={`activity-dot dot-${category}`} />;
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function tierBadge(tier) {
  return <span className={`badge badge-${tier || "new"}`}>{tier || "new"}</span>;
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [qualifying, setQualifying] = useState(false);

  async function load() {
    setLoading(true);
    try { setData(await api.dashboard()); } catch { /* ignore */ } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function runQualifyAll() {
    setQualifying(true);
    try { await api.qualifyAll(); await load(); } catch { /* ignore */ } finally { setQualifying(false); }
  }

  if (loading) return <div className="loading">Loading dashboard…</div>;
  if (!data) return <div className="error-msg">Failed to load dashboard.</div>;

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Welcome back 👋</div>
          <div className="page-subtitle">Here's your pest control pipeline at a glance</div>
        </div>
        <div className="btn-group">
          <button className="btn btn-primary" onClick={runQualifyAll} disabled={qualifying}>
            {qualifying ? "Running…" : "⚡ Qualify All Leads"}
          </button>
          <button className="btn btn-secondary" onClick={load}>↻ Refresh</button>
        </div>
      </div>

      {/* Metrics */}
      <div className="metrics-grid">
        {data.metrics.map(m => (
          <div className="metric-card" key={m.label}>
            <div className="metric-value">{m.value}</div>
            <div className="metric-label">{m.label}</div>
            {m.hint && <div className="metric-hint">{m.hint}</div>}
          </div>
        ))}
      </div>

      <div className="grid-2">
        {/* Recent Activity */}
        <div className="card">
          <div className="card-header">Recent Activity</div>
          <div className="card-body" style={{ padding: "8px 16px" }}>
            {data.recent_activity.length === 0 ? (
              <div className="empty-state" style={{ padding: 20 }}>No activity yet</div>
            ) : data.recent_activity.map((a, i) => (
              <div className="activity-item" key={i}>
                <ActivityDot category={a.category} />
                <div className="activity-msg">{a.message}</div>
                <div className="activity-time">{timeAgo(a.timestamp)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* System Summary */}
        <div className="card">
          <div className="card-header">System Summary</div>
          <div className="card-body">
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[
                ["Qualified leads", data.system_summary.qualified_count],
                ["Hot leads", data.system_summary.hot_count],
                ["Avg qualification score", data.system_summary.avg_score],
                ["Jobs completed", data.system_summary.jobs_completed],
                ["AI Provider", data.system_summary.provider],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between" style={{ padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
                  <span className="text-muted text-sm">{k}</span>
                  <span className="font-bold" style={{ fontSize: 13 }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Top Leads */}
      {data.top_leads.length > 0 && (
        <div className="card section-gap">
          <div className="card-header">Top Leads by Score</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th><th>Pest</th><th>City</th><th>Score</th><th>Tier</th>
                </tr>
              </thead>
              <tbody>
                {data.top_leads.map(l => (
                  <tr key={l.id}>
                    <td><div className="td-name">{l.name}</div><div className="td-muted text-sm">{l.company || l.email}</div></td>
                    <td>{l.pest_type}</td>
                    <td>{l.city}</td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div className="score-bar" style={{ width: 60 }}>
                          <div className={`score-fill ${l.qualification?.tier || "nurture"}`}
                            style={{ width: `${l.qualification?.score || 0}%` }} />
                        </div>
                        <span style={{ fontSize: 13, fontWeight: 700 }}>{l.qualification?.score || 0}</span>
                      </div>
                    </td>
                    <td>{tierBadge(l.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Upcoming Jobs */}
      {data.upcoming_jobs?.length > 0 && (
        <div className="card">
          <div className="card-header">Upcoming Jobs</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Service</th><th>City</th><th>Scheduled</th><th>Technician</th><th>Status</th></tr>
              </thead>
              <tbody>
                {data.upcoming_jobs.map(j => (
                  <tr key={j.id}>
                    <td><span className="td-name">{j.pest_type}</span></td>
                    <td>{j.city}</td>
                    <td className="td-muted">{j.scheduled_at ? new Date(j.scheduled_at).toLocaleString() : "—"}</td>
                    <td>{j.technician_name || <span className="text-muted">Unassigned</span>}</td>
                    <td><span className={`badge badge-${j.status}`}>{j.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
