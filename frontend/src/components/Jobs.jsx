import { useState, useEffect } from "react";
import { api } from "../api.js";

const STATUS_ORDER = ["scheduled", "in-progress", "completed", "cancelled"];
const STATUS_COLORS = { scheduled: "badge-scheduled", "in-progress": "badge-in-progress", completed: "badge-completed", cancelled: "badge-cancelled" };

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [techs, setTechs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [opsResults, setOpsResults] = useState(null);
  const [opsLoading, setOpsLoading] = useState({});
  const [editing, setEditing] = useState(null);
  const [completeModal, setCompleteModal] = useState(null); // job being completed
  const [completePrice, setCompletePrice] = useState("");
  const [startError, setStartError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [jData, tData] = await Promise.all([api.jobs(statusFilter ? { status: statusFilter } : {}), api.technicians()]);
      setJobs(jData.items || []);
      setTechs(tData.items || []);
    } catch { /* ignore */ } finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [statusFilter]);

  async function runOp(name, fn) {
    setOpsLoading(o => ({ ...o, [name]: true }));
    try {
      const result = await fn();
      setOpsResults({ op: name, ...result });
      await load();
    } catch (e) {
      setOpsResults({ op: name, error: e.message });
    } finally {
      setOpsLoading(o => ({ ...o, [name]: false }));
    }
  }

  async function updateStatus(job, status) {
    const data = { status };
    if (status === "completed") data.completed_at = new Date().toISOString();
    await api.updateJob(job.id, data);
    load();
  }

  function openCompleteModal(job) {
    setCompletePrice(job.price != null ? String(job.price) : "");
    setCompleteModal(job);
  }

  async function confirmComplete() {
    const price = parseFloat(completePrice);
    await api.updateJob(completeModal.id, {
      status: "completed",
      completed_at: new Date().toISOString(),
      ...(Number.isFinite(price) && { price }),
    });
    setCompleteModal(null);
    load();
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Job Operations</div>
          <div className="page-subtitle">{jobs.length} jobs · Auto-scheduling & comms powered by AI</div>
        </div>
        <button className="btn btn-secondary" onClick={load}>↻ Refresh</button>
      </div>

      {/* Operations actions */}
      <div className="card section-gap">
        <div className="card-header">Automation Actions</div>
        <div className="card-body">
          <div className="ops-action-bar">
            <button className="btn btn-primary" disabled={opsLoading.assign} onClick={() => runOp("assign", api.assignJobs)}>
              {opsLoading.assign ? "Assigning…" : "🤖 Auto-Assign Techs"}
            </button>
            <button className="btn btn-amber" disabled={opsLoading.reminders} onClick={() => runOp("reminders", api.sendReminders)}>
              {opsLoading.reminders ? "Sending…" : "📱 Send Reminders"}
            </button>
            <button className="btn btn-secondary" disabled={opsLoading.followups} onClick={() => runOp("followups", api.sendFollowups)}>
              {opsLoading.followups ? "Sending…" : "📧 Send Follow-ups"}
            </button>
          </div>
          {opsResults && (
            <div className={opsResults.error ? "error-msg" : "success-msg"} style={{ marginTop: 8, marginBottom: 0 }}>
              {opsResults.error
                ? `Error in ${opsResults.op}: ${opsResults.error}`
                : opsResults.assigned !== undefined
                  ? `✓ Assigned ${opsResults.assigned} of ${opsResults.total_unassigned} unassigned jobs`
                  : opsResults.reminders_sent !== undefined
                    ? `✓ Sent ${opsResults.reminders_sent} reminder(s)`
                    : `✓ Sent ${opsResults.followups_sent} follow-up(s)`
              }
            </div>
          )}
        </div>
      </div>

      {/* Filter */}
      <div className="pill-group mb-12">
        {["", ...STATUS_ORDER].map(s => (
          <button key={s || "all"} className={`btn btn-sm ${statusFilter === s ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setStatusFilter(s)}>
            {s || "All"}
          </button>
        ))}
      </div>

      {startError && (
        <div className="error-msg" style={{ marginBottom: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>⚠️ {startError}</span>
          <button style={{ background: "none", border: "none", cursor: "pointer", fontWeight: 700 }} onClick={() => setStartError("")}>✕</button>
        </div>
      )}

      {loading ? <div className="loading">Loading jobs…</div> : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Service</th><th>City / Address</th><th>Scheduled</th><th>Technician</th><th>Price</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {jobs.length === 0 && <tr><td colSpan={7}><div className="empty-state"><div className="empty-icon">🔧</div>No jobs found</div></td></tr>}
                {jobs.map(j => (
                  <tr key={j.id}>
                    <td>
                      <div className="td-name">{j.pest_type}</div>
                      <div className="td-muted text-sm">{j.service_type}</div>
                    </td>
                    <td>
                      <div>{j.city}</div>
                      <div className="td-muted text-sm" style={{ maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{j.address}</div>
                    </td>
                    <td className="td-muted">{j.scheduled_at ? new Date(j.scheduled_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "—"}</td>
                    <td>
                      {j.technician_name
                        ? <span style={{ fontWeight: 600 }}>{j.technician_name}</span>
                        : <select style={{ fontSize: 12, padding: "3px 6px" }} defaultValue=""
                            onChange={async e => { if (e.target.value) { await api.updateJob(j.id, { technician_id: parseInt(e.target.value) }); load(); }}}>
                            <option value="">Assign…</option>
                            {techs.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                          </select>
                      }
                    </td>
                    <td>€{j.price?.toFixed(0) || 0}</td>
                    <td><span className={`badge ${STATUS_COLORS[j.status] || ""}`}>{j.status}</span></td>
                    <td>
                      <div className="btn-group" style={{ flexWrap: "nowrap" }}>
                        {j.status === "scheduled" && (
                          <button
                            className="btn btn-sm btn-amber"
                            onClick={() => {
                              if (!j.technician_id) {
                                setStartError(`Job ${j.id}: assign a technician before starting.`);
                                return;
                              }
                              setStartError("");
                              updateStatus(j, "in-progress");
                            }}
                          >Start</button>
                        )}
                        {j.status === "in-progress" && (
                          <button className="btn btn-sm btn-primary" onClick={() => openCompleteModal(j)}>Complete</button>
                        )}
                        {j.status === "scheduled" && (
                          <button className="btn btn-sm btn-secondary" onClick={() => updateStatus(j, "cancelled")}>Cancel</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Complete job modal */}
      {completeModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "var(--card)", borderRadius: 12, padding: 28, minWidth: 340, boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}>
            <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>Complete Job</div>
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 20 }}>
              {completeModal.pest_type} · {completeModal.city} · {completeModal.service_type}
            </div>
            <div className="field">
              <label>Final Price (€)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="0.00"
                value={completePrice}
                onChange={e => setCompletePrice(e.target.value)}
                autoFocus
                onKeyDown={e => { if (e.key === "Enter") confirmComplete(); if (e.key === "Escape") setCompleteModal(null); }}
              />
            </div>
            <div className="btn-group" style={{ marginTop: 20, justifyContent: "flex-end" }}>
              <button className="btn btn-secondary" onClick={() => setCompleteModal(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={confirmComplete}>Confirm & Complete</button>
            </div>
          </div>
        </div>
      )}

      {/* Technician overview */}
      {techs.length > 0 && (
        <div className="card mt-8">
          <div className="card-header">Technicians</div>
          <div className="card-body">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px,1fr))", gap: 12 }}>
              {techs.map(t => (
                <div key={t.id} style={{ padding: 12, border: "1px solid var(--border)", borderRadius: 8, background: t.is_available ? "var(--green-light)" : "#f8fafc" }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{t.name}</div>
                  <div className="text-sm text-muted">{t.service_areas.join(", ")}</div>
                  <div className="pill-group" style={{ marginTop: 6 }}>
                    {t.specialties.map(s => <span key={s} className="pill">{s}</span>)}
                  </div>
                  <div style={{ marginTop: 6 }}>
                    <span className={`badge ${t.is_available ? "badge-qualified" : "badge-cancelled"}`}>
                      {t.is_available ? "Available" : "Busy"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
