import { useState, useEffect } from "react";
import { api } from "../api.js";

const CITIES = ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Stuttgart", "Potsdam", "Augsburg", "Bremen", "Wiesbaden", "Düsseldorf"];
const SPECIALTIES = ["rodents", "roaches", "bedbugs", "termites", "ants", "wasps", "spiders", "fleas", "general"];

const EMPTY = { full_name: "", email: "", phone: "", service_areas: [], specialties: [] };

export default function AdminPanel() {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  const [techs, setTechs] = useState([]);
  const [techsLoading, setTechsLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [techError, setTechError] = useState("");

  const [deleteRequests, setDeleteRequests] = useState([]);
  const [drLoading, setDrLoading] = useState(true);
  const [drError, setDrError] = useState("");
  const [drActing, setDrActing] = useState(null);

  async function loadTechs() {
    setTechsLoading(true);
    try { const d = await api.technicians(); setTechs(d.items || []); }
    catch { /* ignore */ } finally { setTechsLoading(false); }
  }

  async function loadDeleteRequests() {
    setDrLoading(true);
    try { const d = await api.listDeleteRequests(); setDeleteRequests(d.items || []); }
    catch { /* ignore */ } finally { setDrLoading(false); }
  }

  useEffect(() => { loadTechs(); loadDeleteRequests(); }, []);

  async function handleDrAction(userId, action) {
    setDrActing(userId);
    setDrError("");
    try {
      if (action === "approve") await api.approveDeleteRequest(userId);
      else await api.rejectDeleteRequest(userId);
      await Promise.all([loadDeleteRequests(), loadTechs()]);
    } catch (e) {
      setDrError(e.message);
    } finally {
      setDrActing(null);
    }
  }

  async function toggleStatus(tech) {
    setTogglingId(tech.id);
    setTechError("");
    try {
      await api.setTechnicianStatus(tech.id, !tech.is_available);
      await loadTechs();
    } catch (e) { setTechError(e.message); }
    finally { setTogglingId(null); }
  }

  async function deleteTech(tech) {
    setTechError("");
    try {
      await api.deleteTechnician(tech.id);
      setDeleteConfirm(null);
      await loadTechs();
    } catch (e) { setTechError(e.message); }
  }

  function toggle(field, value) {
    setForm(f => ({
      ...f,
      [field]: f[field].includes(value) ? f[field].filter(v => v !== value) : [...f[field], value],
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    if (form.service_areas.length === 0) { setError("Select at least one service area"); return; }
    if (form.specialties.length === 0)   { setError("Select at least one specialty"); return; }
    setSaving(true);
    try {
      const data = await api.createTechnician(form);
      setResult(data);
      setForm(EMPTY);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function copy(text, key) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key);
      setTimeout(() => setCopied(""), 2000);
    });
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Admin Panel</div>
          <div className="page-subtitle">Create technician accounts · Manage access</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>

        {/* Create form */}
        <div className="card">
          <div className="card-header">Create Technician Account</div>
          <div className="card-body">
            {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}

            <form className="form" onSubmit={handleSubmit}>
              <div className="field">
                <label>Full Name *</label>
                <input value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                  placeholder="e.g. Jane Smith" required />
              </div>
              <div className="field">
                <label>Email (used as login ID) *</label>
                <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="jane@pestguard.com" required />
              </div>
              <div className="field">
                <label>Phone</label>
                <input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                  placeholder="+49 30 00000000" />
              </div>

              <div className="field">
                <label>Service Areas *</label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
                  {CITIES.map(c => (
                    <button key={c} type="button"
                      className={`btn btn-sm ${form.service_areas.includes(c) ? "btn-primary" : "btn-secondary"}`}
                      style={{ borderRadius: 20, fontSize: 12 }}
                      onClick={() => toggle("service_areas", c)}>
                      {c}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field">
                <label>Pest Specialties *</label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
                  {SPECIALTIES.map(s => (
                    <button key={s} type="button"
                      className={`btn btn-sm ${form.specialties.includes(s) ? "btn-primary" : "btn-secondary"}`}
                      style={{ borderRadius: 20, fontSize: 12, textTransform: "capitalize" }}
                      onClick={() => toggle("specialties", s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <button className="btn btn-primary" type="submit" disabled={saving} style={{ marginTop: 8 }}>
                {saving ? "Creating…" : "Create Account & Generate OTP"}
              </button>
            </form>
          </div>
        </div>

        {/* Result / instructions */}
        <div>
          {result ? (
            <div className="card" style={{ border: "2px solid #86efac" }}>
              <div className="card-header" style={{ color: "#166534", background: "#f0fdf4" }}>
                ✅ Account Created
              </div>
              <div className="card-body">
                <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
                  Share these credentials with <strong>{result.full_name}</strong>. The OTP is valid for one login only — they will be forced to set a new password immediately.
                </p>

                {/* Login ID */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>Login Email</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#f8fafc", borderRadius: 8, padding: "8px 12px", border: "1px solid var(--border)" }}>
                    <code style={{ flex: 1, fontSize: 14 }}>{result.email}</code>
                    <button className="btn btn-secondary btn-sm" style={{ fontSize: 11 }}
                      onClick={() => copy(result.email, "email")}>
                      {copied === "email" ? "✓ Copied" : "Copy"}
                    </button>
                  </div>
                </div>

                {/* OTP */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 4 }}>One-Time Password (OTP)</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#f0fdf4", borderRadius: 8, padding: "8px 12px", border: "1px solid #86efac" }}>
                    <code style={{ flex: 1, fontSize: 22, fontWeight: 800, letterSpacing: 6, color: "#166534" }}>
                      {result.generated_password}
                    </code>
                    <button className="btn btn-secondary btn-sm" style={{ fontSize: 11 }}
                      onClick={() => copy(result.generated_password, "otp")}>
                      {copied === "otp" ? "✓ Copied" : "Copy"}
                    </button>
                  </div>
                </div>

                <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8, padding: 12, fontSize: 12, color: "#92400e" }}>
                  ⚠️ This OTP will <strong>not be shown again</strong>. Copy it now and send it to the technician securely.
                </div>

                <button className="btn btn-secondary" style={{ marginTop: 14, width: "100%" }}
                  onClick={() => setResult(null)}>
                  Create Another
                </button>
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="card-header">How it works</div>
              <div className="card-body" style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.7 }}>
                <ol style={{ paddingLeft: 18, margin: 0 }}>
                  <li>Fill in the technician's details and click <strong>Create Account</strong>.</li>
                  <li>An 8-digit OTP is generated — share it with the technician along with their login email.</li>
                  <li>The technician logs in using their email and the OTP.</li>
                  <li>They are immediately prompted to set a personal password.</li>
                  <li>All future logins use their email + new password.</li>
                </ol>
                <div style={{ marginTop: 12, padding: "10px 12px", background: "#f8fafc", borderRadius: 8, border: "1px solid var(--border)" }}>
                  Technicians can only view their own assigned jobs. They cannot access leads, reports, or admin settings.
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Pending delete requests */}
      <div className="card" style={{ marginTop: 24, border: deleteRequests.length ? "2px solid #fcd34d" : undefined }}>
        <div className="card-header">
          Account Deletion Requests
          {deleteRequests.length > 0 && (
            <span style={{ background: "#dc2626", color: "#fff", borderRadius: 20, padding: "2px 10px", fontSize: 12, marginLeft: 8 }}>
              {deleteRequests.length}
            </span>
          )}
          <button className="btn btn-secondary btn-sm" onClick={loadDeleteRequests}>↻</button>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {drError && <div className="error-msg" style={{ margin: "12px 16px 0" }}>{drError}</div>}
          {drLoading ? (
            <div className="loading" style={{ padding: 20 }}>Loading…</div>
          ) : deleteRequests.length === 0 ? (
            <div style={{ padding: "20px 16px", fontSize: 13, color: "var(--text-muted)" }}>No pending deletion requests.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Name</th><th>Email</th><th>Role</th><th>Active Jobs</th><th>Actions</th></tr>
                </thead>
                <tbody>
                  {deleteRequests.map(u => (
                    <tr key={u.id}>
                      <td><div className="td-name">{u.full_name}</div></td>
                      <td><div className="td-muted text-sm">{u.email}</div></td>
                      <td><span className="badge badge-new" style={{ textTransform: "capitalize" }}>{u.role}</span></td>
                      <td>
                        {u.active_jobs > 0
                          ? <span style={{ color: "#dc2626", fontWeight: 600 }}>{u.active_jobs} active</span>
                          : <span style={{ color: "#16a34a" }}>None</span>}
                      </td>
                      <td>
                        <div className="btn-group" style={{ flexWrap: "nowrap" }}>
                          <button
                            className="btn btn-sm btn-primary"
                            disabled={drActing === u.id || u.active_jobs > 0}
                            title={u.active_jobs > 0 ? "Cannot approve — active jobs exist" : ""}
                            onClick={() => handleDrAction(u.id, "approve")}
                          >
                            {drActing === u.id ? "…" : "✓ Approve"}
                          </button>
                          <button
                            className="btn btn-sm btn-secondary"
                            disabled={drActing === u.id}
                            onClick={() => handleDrAction(u.id, "reject")}
                          >
                            ✕ Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Technician management */}
      <div className="card" style={{ marginTop: 24 }}>
        <div className="card-header">
          Manage Technicians
          <button className="btn btn-secondary btn-sm" onClick={loadTechs}>↻ Refresh</button>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {techError && <div className="error-msg" style={{ margin: "12px 16px 0" }}>{techError}</div>}
          {techsLoading ? (
            <div className="loading" style={{ padding: 20 }}>Loading technicians…</div>
          ) : techs.length === 0 ? (
            <div className="empty-state" style={{ padding: 32 }}>No technicians yet</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Name</th><th>Email</th><th>Service Areas</th><th>Specialties</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>
                  {techs.map(t => (
                    <tr key={t.id}>
                      <td><div className="td-name">{t.name}</div></td>
                      <td><div className="td-muted text-sm">{t.email}</div></td>
                      <td>
                        <div className="pill-group">
                          {t.service_areas.map(a => <span key={a} className="pill" style={{ fontSize: 11 }}>{a}</span>)}
                        </div>
                      </td>
                      <td>
                        <div className="pill-group">
                          {t.specialties.map(s => <span key={s} className="pill" style={{ fontSize: 11 }}>{s}</span>)}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${t.is_available ? "badge-qualified" : "badge-cancelled"}`}>
                          {t.is_available ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>
                        <div className="btn-group" style={{ flexWrap: "nowrap" }}>
                          <button
                            className={`btn btn-sm ${t.is_available ? "btn-amber" : "btn-primary"}`}
                            disabled={togglingId === t.id}
                            onClick={() => toggleStatus(t)}
                          >
                            {togglingId === t.id ? "…" : t.is_available ? "Deactivate" : "Activate"}
                          </button>
                          <button
                            className="btn btn-sm"
                            style={{ background: "#fee2e2", color: "#dc2626", border: "none" }}
                            onClick={() => setDeleteConfirm(t)}
                          >
                            🗑 Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Delete technician confirm modal */}
      {deleteConfirm && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "var(--card)", borderRadius: 12, padding: 28, minWidth: 360, boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}>
            <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>Delete Technician</div>
            <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 8 }}>
              This will permanently delete <strong>{deleteConfirm.name}</strong> and their login account.
              All jobs assigned to them will be unassigned.
            </div>
            <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8, padding: 10, fontSize: 12, color: "#92400e", marginBottom: 20 }}>
              ⚠️ This action cannot be undone.
            </div>
            <div className="btn-group" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-secondary" onClick={() => setDeleteConfirm(null)}>Cancel</button>
              <button
                className="btn"
                style={{ background: "#dc2626", color: "#fff", border: "none" }}
                onClick={() => deleteTech(deleteConfirm)}
              >
                Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
